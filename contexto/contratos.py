"""Contratos B1 estrictos. Identidad del feed no equivale a certificación oficial."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re
from urllib.parse import urlsplit

SCHEMA = 'kuota-contexto-b1-v1'
PROVEEDORES = ('api-football', 'sportmonks')
LIGAS = ('laliga', 'premier', 'seriea', 'bundesliga', 'ligue1', 'ligamx')
HOSTS = {'api-football': 'v3.football.api-sports.io',
         'sportmonks': 'api.sportmonks.com', 'open-meteo': 'api.open-meteo.com'}


def canonico(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def utc(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp debe ser texto ISO8601')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('Timestamp ISO8601 inválido') from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('Timestamp sin zona horaria')
    return result.astimezone(timezone.utc)


def iso(value):
    return utc(value).isoformat().replace('+00:00', 'Z')


def ahora():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def campos(obj, expected):
    if not isinstance(obj, dict) or set(obj) != set(expected):
        raise ValueError('Contrato incompleto o campos desconocidos')


def texto(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError('Texto vacío o inválido')
    return value


def identificador(value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,18}', value):
        raise ValueError('ID de proveedor inválido')
    return value


def digest(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Hash SHA256 inválido')
    return value


def url_fuente(value, provider):
    u = urlsplit(value)
    if (provider not in HOSTS or u.scheme != 'https' or u.hostname != HOSTS[provider]
            or u.port not in (None, 443) or u.username or u.password or u.query or u.fragment):
        raise ValueError('Fuente no permitida o URL con parámetros/credenciales')
    return value


def evidencia(obj):
    campos(obj, ('schema_version', 'provider', 'source_url', 'sha256', 'captured_at_utc',
                 'published_at_utc', 'publication_basis', 'content_type'))
    if obj['schema_version'] != SCHEMA:
        raise ValueError('Versión de contrato desconocida')
    url_fuente(obj['source_url'], obj['provider']); digest(obj['sha256'])
    result = dict(obj); result['captured_at_utc'] = iso(obj['captured_at_utc'])
    if obj['publication_basis'] not in ('unknown', 'provider_declared'):
        raise ValueError('No se inventa certificación de publicación')
    if (obj['published_at_utc'] is None) != (obj['publication_basis'] == 'unknown'):
        raise ValueError('Disponibilidad desconocida debe ser explícita')
    if obj['published_at_utc'] is not None:
        result['published_at_utc'] = iso(obj['published_at_utc'])
        if utc(result['published_at_utc']) > utc(result['captured_at_utc']):
            raise ValueError('Publicación posterior a captura')
    if obj['content_type'] != 'application/json':
        raise ValueError('Tipo de evidencia no soportado')
    return result


def elegible_asof(obj, cutoff):
    """Captura previa acredita observación local; publicación declarada sola no basta."""
    e = evidencia(obj)
    return utc(e['captured_at_utc']) <= utc(cutoff)


def validar_mapeo(obj):
    campos(obj, ('schema_version', 'provider', 'league_id', 'season_id', 'team_id',
                 'internal_team', 'internal_league', 'valid_from_utc', 'valid_until_utc',
                 'reviewed_at_utc', 'reviewed_by', 'evidence_sha256'))
    if obj['schema_version'] != SCHEMA or obj['provider'] not in PROVEEDORES or obj['internal_league'] not in LIGAS:
        raise ValueError('Proveedor/liga/versión desconocidos')
    for key in ('league_id', 'season_id', 'team_id'):
        identificador(obj[key])
    texto(obj['internal_team']); texto(obj['reviewed_by']); digest(obj['evidence_sha256'])
    result = dict(obj)
    for key in ('valid_from_utc', 'valid_until_utc', 'reviewed_at_utc'):
        result[key] = iso(obj[key])
    if utc(result['valid_from_utc']) >= utc(result['valid_until_utc']):
        raise ValueError('Vigencia de mapeo inválida')
    return result


def resolver(mappings, provider, league, season, team, kickoff, cutoff):
    validated = [validar_mapeo(m) for m in mappings]
    # Una revisión futura no puede cambiar ni invalidar una identidad pasada.
    validated = [m for m in validated if utc(m['reviewed_at_utc']) <= utc(cutoff)]
    for i, a in enumerate(validated):
        for b in validated[i + 1:]:
            same_scope = (a['provider'], a['league_id'], a['season_id']) == (b['provider'], b['league_id'], b['season_id'])
            overlap = max(utc(a['valid_from_utc']), utc(b['valid_from_utc'])) < min(utc(a['valid_until_utc']), utc(b['valid_until_utc']))
            if same_scope and overlap and (a['team_id'] == b['team_id'] or a['internal_team'] == b['internal_team']):
                raise ValueError('Mapeo duplicado o no biyectivo en vigencias solapadas')
    matches = [m for m in validated if
               (m['provider'], m['league_id'], m['season_id'], m['team_id']) ==
               (provider, league, season, team) and
               utc(m['valid_from_utc']) <= utc(kickoff) < utc(m['valid_until_utc']) and
               utc(m['reviewed_at_utc']) <= utc(cutoff)]
    if len(matches) != 1:
        raise ValueError('Identidad ausente o ambigua; se requiere mapeo revisado')
    return matches[0]


def fixture(obj):
    campos(obj, ('schema_version', 'provider', 'fixture_id', 'league_id', 'season_id',
                 'internal_league', 'home', 'away', 'venue', 'kickoff_utc', 'status',
                 'snapshot_sha256', 'mapping_sha256', 'captured_at_utc', 'version'))
    if obj['schema_version'] != SCHEMA or obj['provider'] not in PROVEEDORES or obj['internal_league'] not in LIGAS:
        raise ValueError('Proveedor/liga/versión desconocidos')
    for key in ('fixture_id', 'league_id', 'season_id'):
        identificador(obj[key])
    for side in ('home', 'away'):
        campos(obj[side], ('provider_team_id', 'internal_team'))
        identificador(obj[side]['provider_team_id']); texto(obj[side]['internal_team'])
    if (obj['home']['provider_team_id'] == obj['away']['provider_team_id'] or
            obj['home']['internal_team'] == obj['away']['internal_team']):
        raise ValueError('Equipos del fixture no distintos')
    if obj['status'] not in ('scheduled', 'postponed', 'cancelled', 'started', 'finished', 'unknown'):
        raise ValueError('Estado desconocido')
    if obj['venue'] is not None:
        campos(obj['venue'], ('provider_venue_id', 'name', 'latitude', 'longitude'))
        identificador(obj['venue']['provider_venue_id']); texto(obj['venue']['name'])
        lat, lon = obj['venue']['latitude'], obj['venue']['longitude']
        if (lat is None) != (lon is None):
            raise ValueError('Coordenadas incompletas')
        if lat is not None and not all(type(x) in (int, float) and math.isfinite(x) and abs(x) <= limit
                                       for x, limit in ((lat, 90), (lon, 180))):
            raise ValueError('Coordenadas inválidas')
    result = json.loads(canonico(obj))
    for key in ('kickoff_utc', 'captured_at_utc'):
        result[key] = iso(obj[key])
    digest(obj['snapshot_sha256']); digest(obj['mapping_sha256']); digest(obj['version'])
    expected = sha256(canonico({k: v for k, v in result.items() if k != 'version'}).encode()).hexdigest()
    if expected != obj['version']:
        raise ValueError('Versión de fixture incoherente')
    return result
