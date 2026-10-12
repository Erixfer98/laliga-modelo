"""B1: datos unitarios SINTÉTICOS; no conexiones ni evidencia de partidos reales."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import copy
import json
import sqlite3
import sys
from pathlib import Path
import pytest
import requests
from contexto.contratos import SCHEMA, canonico, evidencia, utc, iso, elegible_asof, fixture
from contexto.conectores import Captura, ApiFootball, Sportmonks, OpenMeteo, Transporte, NoDisponible
from contexto.identidad import normalizar, apto_para_contexto
from contexto.almacen import Archivo
from contexto.configuracion import disponibilidad, AlmacenConfigurado

CAPTURE = '2026-01-01T10:00:00Z'
KICK = '2099-01-02T01:00:00Z'
PROOF = b'SYNTHETIC manual identity review, not real provider evidence'


def muestra(provider='api-football', date=KICK, status='NS'):
    epoch = int(utc(date).timestamp())
    if provider == 'api-football':
        body = {'errors': [], 'response': [{'fixture': {'id': 123, 'date': date,
                'timestamp': epoch, 'status': {'short': status}, 'venue': {'id': 2, 'name': 'Synthetic stadium'}},
                'league': {'id': 140, 'season': 2099}, 'teams': {'home': {'id': 10}, 'away': {'id': 20}}}]}
        source = 'https://v3.football.api-sports.io/fixtures'
    else:
        body = {'data': {'id': 123, 'league_id': 140, 'season_id': 2099,
                'starting_at_timestamp': epoch, 'starting_at': utc(date).strftime('%Y-%m-%d %H:%M:%S'),
                'state': {'short_name': status}, 'participants': [
                    {'id': 10, 'meta': {'location': 'home'}}, {'id': 20, 'meta': {'location': 'away'}}]}}
        source = 'https://api.sportmonks.com/v3/football/fixtures/123'
    raw = canonico(body).encode()
    cap = Captura(raw, {'schema_version': SCHEMA, 'provider': provider, 'source_url': source,
        'sha256': sha256(raw).hexdigest(), 'captured_at_utc': CAPTURE, 'published_at_utc': None,
        'publication_basis': 'unknown', 'content_type': 'application/json'})
    maps = [{'schema_version': SCHEMA, 'provider': provider, 'league_id': '140', 'season_id': '2099',
             'team_id': team, 'internal_team': name, 'internal_league': 'laliga',
             'valid_from_utc': '2025-01-01T00:00:00Z', 'valid_until_utc': '2100-01-01T00:00:00Z',
             'reviewed_at_utc': '2025-12-31T00:00:00Z', 'reviewed_by': 'synthetic-test',
             'evidence_sha256': sha256(PROOF).hexdigest()} for team, name in [('10', 'A'), ('20', 'B')]]
    return cap, maps


def cambiar(cap, transform):
    body = cap.json(); transform(body)
    raw = canonico(body).encode(); metadata = {**cap.metadata, 'sha256': sha256(raw).hexdigest()}
    return Captura(raw, metadata)


@pytest.mark.parametrize('provider', ['api-football', 'sportmonks'])
def test_fixture_ids_order_utc_and_no_guessed_coordinates(provider):
    cap, maps = muestra(provider, '2099-01-01T19:00:00-06:00')
    f, selected = normalizar(cap, '123', maps)
    assert f['kickoff_utc'] == KICK
    assert (f['home']['internal_team'], f['away']['internal_team']) == ('A', 'B')
    assert fixture(f) == f and len(selected) == 2
    if f['venue']: assert f['venue']['latitude'] is None


@pytest.mark.parametrize('date', ['2099-01-02T01:00:00', 'nonsense', None])
def test_utc_requires_zone(date):
    with pytest.raises(ValueError): utc(date)


def test_utc_dst_offsets_same_instant():
    assert iso('2026-10-25T02:30:00+02:00') != iso('2026-10-25T02:30:00+01:00')
    assert iso('2026-01-01T20:00:00-06:00') == '2026-01-02T02:00:00Z'


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'provider', 'season', 'future_review', 'same_name', 'league'])
def test_identity_fails_closed(change):
    cap, maps = muestra()
    if change == 'missing': maps.pop()
    elif change == 'duplicate': maps.append(copy.deepcopy(maps[0]))
    elif change == 'provider': maps[0]['provider'] = 'sportmonks'
    elif change == 'season': maps[0]['season_id'] = '2098'
    elif change == 'future_review': maps[0]['reviewed_at_utc'] = '2099-01-01T00:00:00Z'
    elif change == 'same_name': maps[0]['internal_team'] = maps[1]['internal_team']
    elif change == 'league': maps[0]['internal_league'] = 'premier'
    with pytest.raises(ValueError): normalizar(cap, '123', maps)


@pytest.mark.parametrize('change', ['wrong_fixture', 'timestamp', 'duplicate', 'errors', 'missing'])
def test_provider_contract_rejects_ambiguity(change):
    cap, maps = muestra()
    def mutate(b):
        f = b['response'][0]['fixture']
        if change == 'wrong_fixture': f['id'] = 456
        elif change == 'timestamp': f['timestamp'] += 86400
        elif change == 'duplicate': b['response'].append(copy.deepcopy(b['response'][0]))
        elif change == 'errors': b['errors'] = {'message': 'quota'}
        elif change == 'missing': del f['date']
    with pytest.raises(ValueError): normalizar(cambiar(cap, mutate), '123', maps)


def test_snapshot_temporality_and_unknown_publication():
    cap, _ = muestra()
    assert cap.verificar()['publication_basis'] == 'unknown'
    assert not elegible_asof(cap.metadata, '2026-01-01T09:59:59Z')
    assert elegible_asof(cap.metadata, CAPTURE)
    with pytest.raises(ValueError): evidencia({**cap.metadata, 'published_at_utc': CAPTURE})
    with pytest.raises(ValueError): evidencia({**cap.metadata, 'publication_basis': 'provider_declared',
                                               'published_at_utc': '2026-01-02T00:00:00Z'})
    with pytest.raises(ValueError): evidencia({**cap.metadata, 'registered_at_utc': CAPTURE})
    with pytest.raises(ValueError): Captura(b'altered', cap.metadata).verificar()


@pytest.mark.parametrize('url', ['http://v3.football.api-sports.io/fixtures',
 'https://v3.football.api-sports.io/fixtures?api_token=SECRET', 'https://127.0.0.1/fixtures',
 'https://user:pass@v3.football.api-sports.io/fixtures', 'https://v3.football.api-sports.io:123/fixtures'])
def test_source_urls_exclude_credentials_and_external_hosts(url):
    cap, _ = muestra()
    with pytest.raises(ValueError): evidencia({**cap.metadata, 'source_url': url})


def test_future_data_does_not_change_past_fixture_selection(tmp_path):
    cap, maps = muestra(); db = Archivo(tmp_path / 'b1.sqlite')
    old = db.agregar_fixture(cap, '123', maps, [PROOF]); cutoff = old['registered_at_utc']
    later = cambiar(cap, lambda b: b['response'][0]['fixture']['status'].update(short='PST'))
    db.agregar_fixture(later, '123', maps, [PROOF])
    assert db.consultar_asof('api-football', '123', cutoff) == old
    assert db.consultar_asof('api-football', '123', CAPTURE) is None  # captura declarada no retrodata registro
    assert db.consultar_asof('sportmonks', '123', '2100-01-01T00:00:00Z') is None


def test_append_only_idempotency_reopen_backup_restore(tmp_path):
    cap, maps = muestra(); db = Archivo(tmp_path / 'b1.sqlite')
    receipt = db.agregar_fixture(cap, '123', maps, [PROOF])
    assert db.agregar_fixture(cap, '123', maps, [PROOF]) == receipt
    assert not receipt['provider_availability_certified']
    assert Archivo(db.path).verificar() == [receipt]
    for table in ('receipts', 'snapshots'):
        with sqlite3.connect(db.path) as sql:
            with pytest.raises(sqlite3.IntegrityError): sql.execute(f'DELETE FROM {table}')
    backup = db.backup(tmp_path / 'backup' / 'copy.sqlite')
    assert Archivo(Path(backup['path'])).verificar() == [receipt]
    with pytest.raises(ValueError): db.backup(Path(backup['path']))


def test_concurrent_retry_single_record(tmp_path):
    cap, maps = muestra(); db = Archivo(tmp_path / 'b1.sqlite')
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(lambda _: db.agregar_fixture(cap, '123', maps, [PROOF]), range(4)))
    assert all(r == receipts[0] for r in receipts)
    assert len(db.verificar()) == 1


def test_future_capture_and_missing_proofs_roll_back(tmp_path):
    cap, maps = muestra(); db = Archivo(tmp_path / 'b1.sqlite')
    with pytest.raises(ValueError): db.agregar_fixture(cap, '123', maps, [])
    future = Captura(cap.contenido, {**cap.metadata, 'captured_at_utc': '2099-01-01T00:00:00Z'})
    with pytest.raises(ValueError): db.agregar_fixture(future, '123', maps, [PROOF])
    assert db.verificar() == []
    with sqlite3.connect(db.path) as sql: assert sql.execute('SELECT count(*) FROM snapshots').fetchone()[0] == 0


def test_archive_detects_corruption_and_refuses_new_append(tmp_path):
    cap, maps = muestra(); db = Archivo(tmp_path / 'b1.sqlite'); db.agregar_fixture(cap, '123', maps, [PROOF])
    with sqlite3.connect(db.path) as sql:
        sql.execute('DROP TRIGGER snapshot_no_update')
        sql.execute('UPDATE snapshots SET content=? WHERE sha256=?', (b'corrupt', cap.metadata['sha256']))
    with pytest.raises(ValueError): db.verificar()
    with pytest.raises(ValueError): db.agregar_fixture(cap, '123', maps, [PROOF])


@pytest.mark.parametrize('state,ok', [('NS', True), ('PST', False), ('FT', False), ('MYSTERY', False)])
def test_abstention_for_non_scheduled_states(tmp_path, state, ok):
    cap, maps = muestra(status=state); db = Archivo(tmp_path / 'b1.sqlite')
    receipt = db.agregar_fixture(cap, '123', maps, [PROOF])
    assert apto_para_contexto(receipt, '2098-01-01T00:00:00Z')[0] is ok
    assert not apto_para_contexto(receipt, KICK)[0]
    assert not apto_para_contexto(receipt, CAPTURE)[0]


def test_no_network_without_credentials_and_invalid_id(monkeypatch):
    monkeypatch.setattr(requests, 'get', lambda *a, **k: pytest.fail('No debe abrir red'))
    for connector in (ApiFootball(), Sportmonks()):
        with pytest.raises(NoDisponible): connector.obtener_fixture('123')
        with pytest.raises(ValueError): connector.obtener_fixture('123?token=secret')


def test_transport_errors_redact_secrets(monkeypatch):
    def fail(*args, **kwargs): raise requests.RequestException('https://host/?api_token=SECRET')
    monkeypatch.setattr(requests, 'get', fail)
    with pytest.raises(NoDisponible) as error: Sportmonks('SECRET').obtener_fixture('123')
    assert 'SECRET' not in str(error.value) and error.value.__suppress_context__


def test_forecast_explicit_utc_units_future_and_no_fake_coordinates():
    class Fake:
        def obtener(self, provider, path, params):
            assert provider == 'open-meteo' and path == '/v1/forecast'
            assert params['timezone'] == 'UTC' and params['start_date'] == '2099-01-02'
            assert params['wind_speed_unit'] == 'kmh'
            return 'synthetic transport only'
    assert OpenMeteo(Fake()).obtener_pronostico(40, -3, KICK) == 'synthetic transport only'
    with pytest.raises(ValueError): OpenMeteo(Fake()).obtener_pronostico(None, -3, KICK)
    with pytest.raises(ValueError): OpenMeteo(Fake()).obtener_pronostico(40, -3, CAPTURE)


def test_readiness_does_not_infer_connection_or_durability(monkeypatch, capsys):
    env = {'KUOTA_API_FOOTBALL_KEY': 'SECRET'}
    state = disponibilidad(env)
    assert state['providers']['api-football']['credential_configured']
    assert not state['b2_ready'] and not state['production_enabled']
    assert 'SECRET' not in canonico(state)
    with pytest.raises(ValueError): AlmacenConfigurado(Path('/workspace'), Path('/tmp'), 'claimed').validar()
    from contexto.__main__ import main
    monkeypatch.setattr(sys, 'argv', ['contexto', 'estado']); main()
    assert json.loads(capsys.readouterr().out)['b2_ready'] is False


def test_production_import_isolation_and_mathematics_untouched():
    import ast
    for filename in ('modelo.py', 'probabilidades.py', 'kuota.py', 'api.py', 'app.py'):
        tree = ast.parse(Path(filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): assert not any(a.name.startswith('contexto') for a in node.names)
            if isinstance(node, ast.ImportFrom): assert not (node.module or '').startswith('contexto')
    # B1 no motor de ajustes: no lambda ni probabilidades alternativas añadidas a producción.


class RespuestaSintetica:
    status_code = 200
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    content = b'{"synthetic": true}'
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def iter_content(self, size): yield self.content


@pytest.mark.parametrize('failure', ['redirect', 'quota', 'content_type', 'size', 'invalid_json'])
def test_transport_bounds_and_redirects(monkeypatch, failure):
    response = RespuestaSintetica()
    if failure == 'redirect': response.status_code = 302
    elif failure == 'quota': response.status_code = 429
    elif failure == 'content_type': response.headers = {'Content-Type': 'text/html'}
    elif failure == 'size': response.content = b'x' * (2 * 1024 * 1024 + 1)
    elif failure == 'invalid_json': response.content = b'{"x": NaN}'
    def get(url, **kwargs):
        assert kwargs['allow_redirects'] is False and kwargs['timeout'] == (5, 20)
        assert url == 'https://v3.football.api-sports.io/fixtures'
        return response
    monkeypatch.setattr(requests, 'get', get)
    with pytest.raises((NoDisponible, ValueError)): ApiFootball('SYNTHETIC').obtener_fixture('123')


def test_transport_capture_has_effective_local_time_and_no_secret_url(monkeypatch):
    response = RespuestaSintetica()
    def get(url, **kwargs):
        assert kwargs['params']['api_token'] == 'SYNTHETIC_SECRET'
        return response
    monkeypatch.setattr(requests, 'get', get)
    before = datetime.now(timezone.utc)
    cap = Sportmonks('SYNTHETIC_SECRET').obtener_fixture('123')
    assert before <= utc(cap.metadata['captured_at_utc']) <= datetime.now(timezone.utc)
    assert 'SYNTHETIC_SECRET' not in canonico(cap.metadata)
    assert cap.metadata['published_at_utc'] is None
    assert cap.verificar()['sha256'] == sha256(response.content).hexdigest()


def test_mapping_not_bijective_even_when_other_fixture_team(tmp_path):
    cap, maps = muestra()
    maps.append({**maps[0], 'team_id': '30'})
    with pytest.raises(ValueError, match='biyectivo'): normalizar(cap, '123', maps)


def test_sportmonks_conflicting_participants_and_time():
    cap, maps = muestra('sportmonks')
    altered = cambiar(cap, lambda b: b['data']['participants'][1]['meta'].update(location='home'))
    with pytest.raises(ValueError): normalizar(altered, '123', maps)
    altered = cambiar(cap, lambda b: b['data'].update(starting_at='2099-01-03 01:00:00'))
    with pytest.raises(ValueError): normalizar(altered, '123', maps)


def test_unknown_extra_fields_and_fixture_version_tamper():
    cap, maps = muestra(); f, _ = normalizar(cap, '123', maps)
    with pytest.raises(ValueError): fixture({**f, 'certified': True})
    with pytest.raises(ValueError): fixture({**f, 'kickoff_utc': '2099-01-03T01:00:00Z'})
    with pytest.raises(ValueError): normalizar(cap, '123', [{**maps[0], 'confidence': .99}, maps[1]])


def test_cli_verification_missing_file_does_not_create(tmp_path, monkeypatch):
    from contexto.__main__ import main
    path = tmp_path / 'absent.sqlite'
    monkeypatch.setattr(sys, 'argv', ['contexto', 'verificar', '--db', str(path)])
    with pytest.raises(SystemExit): main()
    assert not path.exists()


def test_existing_phase3_database_is_not_modified(tmp_path):
    from experimentos.registro import Registro
    path = tmp_path / 'fase3.sqlite'; Registro(path)
    original = path.read_bytes()
    with pytest.raises(ValueError, match='Base ajena'): Archivo(path)
    assert path.read_bytes() == original


def test_duplicate_json_fields_and_oversized_import_rejected():
    cap, _ = muestra()
    for raw in (b'{"fixture":1,"fixture":2}', b'x' * (2 * 1024 * 1024 + 1), b''):
        candidate = Captura(raw, {**cap.metadata, 'sha256': sha256(raw).hexdigest()})
        with pytest.raises(ValueError): candidate.verificar()


def test_effective_register_time_is_after_lock_and_snapshot_archive(tmp_path, monkeypatch):
    import contexto.almacen as module
    cap, maps = muestra(); db = Archivo(tmp_path / 'b1.sqlite')
    original = module.ahora
    observed = []
    def clock():
        # Otro escritor no puede adquirir BEGIN IMMEDIATE mientras se asigna el recibo.
        with sqlite3.connect(db.path, timeout=0) as sql:
            with pytest.raises(sqlite3.OperationalError): sql.execute('BEGIN IMMEDIATE')
        observed.append(True)
        return original()
    monkeypatch.setattr(module, 'ahora', clock)
    receipt = db.agregar_fixture(cap, '123', maps, [PROOF])
    assert observed == [True] and utc(receipt['registered_at_utc']) >= utc(CAPTURE)


def test_future_mapping_revision_cannot_change_past_normalization():
    cap, maps = muestra(); original = normalizar(cap, '123', maps)
    future = {**maps[0], 'internal_team': 'Future revised identity',
              'reviewed_at_utc': '2099-01-01T00:00:00Z'}
    assert normalizar(cap, '123', [*maps, future]) == original
