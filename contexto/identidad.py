"""Normalización determinista de fixtures. Sin fuzzy matching ni agenda inventada."""
from hashlib import sha256
from datetime import datetime, timezone
from .contratos import SCHEMA, canonico, fixture, identificador, resolver, iso, utc


API_ESTADOS = {'NS': 'scheduled', 'TBD': 'unknown', 'PST': 'postponed', 'CANC': 'cancelled',
               '1H': 'started', 'HT': 'started', '2H': 'started', 'ET': 'started',
               'BT': 'started', 'P': 'started', 'SUSP': 'started', 'INT': 'started',
               'FT': 'finished', 'AET': 'finished', 'PEN': 'finished', 'ABD': 'cancelled',
               'AWD': 'finished', 'WO': 'finished'}
SPORT_ESTADOS = {'NS': 'scheduled', 'TBA': 'unknown', 'POSTP': 'postponed', 'CANCELLED': 'cancelled',
                 'INPLAY_1ST_HALF': 'started', 'HT': 'started', 'INPLAY_2ND_HALF': 'started',
                 'INPLAY_ET': 'started', 'INPLAY_PENALTIES': 'started', 'BREAK': 'started',
                 'SUSPENDED': 'started', 'INTERRUPTED': 'started', 'FT': 'finished',
                 'AET': 'finished', 'FT_PEN': 'finished', 'ABANDONED': 'cancelled',
                 'AWARDED': 'finished', 'WO': 'finished'}


def pid(value):
    if type(value) is not int:
        raise ValueError('ID de proveedor no entero')
    return identificador(str(value))


def normalizar(capture, requested_id, mappings, identity_cutoff=None, deduplicate=False):
    if type(deduplicate) is not bool: raise ValueError('Deduplicación inválida')
    e = capture.verificar(); provider = e['provider']; body = capture.json()
    identificador(requested_id)
    try:
        if provider == 'api-football':
            if body.get('errors') or not isinstance(body['response'], list):
                raise ValueError('Fixture ausente, duplicado o error del proveedor')
            selected_rows = [r for r in body['response'] if isinstance(r, dict) and isinstance(r.get('fixture'), dict) and r['fixture'].get('id') == int(requested_id)]
            if deduplicate:
                selected_rows = list({canonico(r): r for r in selected_rows}.values())
            if len(selected_rows) != 1:
                raise ValueError('Fixture ausente, duplicado o error del proveedor')
            row = selected_rows[0]; f = row['fixture']; league = row['league']
            fid, lid, sid = pid(f['id']), pid(league['id']), pid(league['season'])
            hid, aid = pid(row['teams']['home']['id']), pid(row['teams']['away']['id'])
            kickoff = iso(f['date'])
            # Si hay epoch, debe identificar exactamente el mismo instante.
            if type(f.get('timestamp')) is not int or int(utc(kickoff).timestamp()) != f['timestamp']:
                raise ValueError('Timestamp UTC de fixture incoherente')
            status = API_ESTADOS.get(f['status']['short'], 'unknown')
            raw_venue = f.get('venue'); venue = None
            if raw_venue and raw_venue.get('id') is not None and raw_venue.get('name'):
                venue = {'provider_venue_id': pid(raw_venue['id']), 'name': raw_venue['name'],
                         'latitude': None, 'longitude': None}
        elif provider == 'sportmonks':
            row = body['data']
            fid, lid, sid = pid(row['id']), pid(row['league_id']), pid(row['season_id'])
            parts = row['participants']
            home = [p for p in parts if p['meta']['location'] == 'home']
            away = [p for p in parts if p['meta']['location'] == 'away']
            if len(parts) != 2 or len(home) != 1 or len(away) != 1:
                raise ValueError('Participantes ambiguos')
            hid, aid = pid(home[0]['id']), pid(away[0]['id'])
            epoch = row['starting_at_timestamp']
            if type(epoch) is not int:
                raise ValueError('Timestamp oficial ausente')
            kickoff = datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace('+00:00', 'Z')
            # starting_at es texto UTC documentado: no usa zona local del sistema.
            if row.get('starting_at'):
                if iso(row['starting_at'] + '+00:00') != kickoff:
                    raise ValueError('Timestamp UTC de fixture incoherente')
            state = row.get('state') or {}
            status = SPORT_ESTADOS.get(state.get('short_name'), 'unknown')
            raw_venue = row.get('venue'); venue = None
            if raw_venue and raw_venue.get('id') is not None and raw_venue.get('name'):
                # No atribuir coordenadas sin contrato validado del campo.
                venue = {'provider_venue_id': pid(raw_venue['id']), 'name': raw_venue['name'],
                         'latitude': None, 'longitude': None}
        else:
            raise ValueError('Proveedor sin contrato de fixture')
        if fid != requested_id:
            raise ValueError('El proveedor devolvió otro fixture')
        mapping_cutoff = identity_cutoff or e['captured_at_utc']
        if utc(mapping_cutoff) < utc(e['captured_at_utc']):
            raise ValueError('Revisión de identidad anterior a captura')
        mh = resolver(mappings, provider, lid, sid, hid, kickoff, mapping_cutoff)
        ma = resolver(mappings, provider, lid, sid, aid, kickoff, mapping_cutoff)
        if mh['internal_league'] != ma['internal_league']:
            raise ValueError('Mapeos de ligas distintas')
        result = {'schema_version': SCHEMA, 'provider': provider, 'fixture_id': fid,
            'league_id': lid, 'season_id': sid, 'internal_league': mh['internal_league'],
            'home': {'provider_team_id': hid, 'internal_team': mh['internal_team']},
            'away': {'provider_team_id': aid, 'internal_team': ma['internal_team']},
            'venue': venue, 'kickoff_utc': kickoff, 'status': status,
            'snapshot_sha256': e['sha256'],
            'mapping_sha256': sha256(canonico([mh, ma]).encode()).hexdigest(),
            'captured_at_utc': e['captured_at_utc']}
        result['version'] = sha256(canonico(result).encode()).hexdigest()
        return fixture(result), [mh, ma]
    except (KeyError, TypeError, OverflowError, OSError, IndexError):
        raise ValueError('Contrato de fixture del proveedor incompleto o incompatible') from None


def apto_para_contexto(receipt, cutoff):
    """B1 solo valida agenda previa; no declara elegibilidad estadística de predicción."""
    f = fixture(receipt['fixture'])
    if utc(receipt['registered_at_utc']) > utc(cutoff):
        return False, 'Fixture no registrado al cutoff'
    if utc(f['kickoff_utc']) <= utc(cutoff):
        return False, 'Partido ya iniciado según kickoff'
    if f['status'] != 'scheduled':
        return False, 'Agenda no confirmada como programada'
    return True, 'Identidad del feed y mapeos revisados; certificación del organizador pendiente'
