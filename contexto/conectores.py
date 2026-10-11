"""GET opt-in, hosts fijos, sin redirecciones ni reintentos ocultos. No consulta al importar."""
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import requests
from .contratos import SCHEMA, HOSTS, ahora, evidencia, identificador, utc

MAX_BYTES = 2 * 1024 * 1024


def _constante_invalida(_):
    raise ValueError('Número JSON no finito')


def _objeto_unico(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Campo JSON duplicado')
        result[key] = value
    return result


class NoDisponible(RuntimeError):
    pass


@dataclass(frozen=True)
class Captura:
    contenido: bytes
    metadata: dict

    def json(self):
        try:
            obj = json.loads(self.contenido, parse_constant=_constante_invalida, object_pairs_hook=_objeto_unico)
        except (ValueError, UnicodeError):
            raise ValueError('JSON del proveedor inválido') from None
        if not isinstance(obj, dict):
            raise ValueError('Se esperaba objeto JSON')
        return obj

    def verificar(self):
        if not isinstance(self.contenido, bytes) or not 0 < len(self.contenido) <= MAX_BYTES:
            raise ValueError('Snapshot vacío o fuera de límite')
        e = evidencia(self.metadata)
        if sha256(self.contenido).hexdigest() != e['sha256']:
            raise ValueError('Bytes no coinciden con procedencia')
        self.json()
        return e


class Transporte:
    def obtener(self, provider, path, params=None, headers=None):
        if provider not in HOSTS or not path.startswith('/') or '?' in path or '#' in path or '..' in path:
            raise ValueError('Destino inválido')
        url = 'https://' + HOSTS[provider] + path
        try:
            with requests.get(url, params=params, headers=headers, timeout=(5, 20),
                              allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise NoDisponible(f'Proveedor no disponible: HTTP {response.status_code}')
                if response.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                    raise NoDisponible('Proveedor no devolvió JSON')
                chunks = []; size = 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise NoDisponible('Respuesta excede límite')
                    chunks.append(chunk)
                content = b''.join(chunks)
        except requests.RequestException:
            # Excepciones requests pueden contener URLs con tokens. No propagarlas ni imprimirlas.
            raise NoDisponible('Fallo de transporte del proveedor') from None
        capture = Captura(content, {'schema_version': SCHEMA, 'provider': provider,
            'source_url': url, 'sha256': sha256(content).hexdigest(), 'captured_at_utc': ahora(),
            'published_at_utc': None, 'publication_basis': 'unknown', 'content_type': 'application/json'})
        capture.verificar()
        return capture


class ApiFootball:
    def __init__(self, key=None, transporte=None):
        self.key = key; self.transporte = transporte or Transporte()

    def obtener_fixture(self, fixture_id):
        identificador(fixture_id)
        if not self.key:
            raise NoDisponible('API-Football sin credenciales')
        return self.transporte.obtener('api-football', '/fixtures', params={'id': fixture_id},
                                       headers={'x-apisports-key': self.key})


class Sportmonks:
    def __init__(self, token=None, transporte=None):
        self.token = token; self.transporte = transporte or Transporte()

    def obtener_fixture(self, fixture_id):
        identificador(fixture_id)
        if not self.token:
            raise NoDisponible('Sportmonks sin credenciales')
        return self.transporte.obtener('sportmonks', '/v3/football/fixtures/' + fixture_id,
            params={'api_token': self.token, 'include': 'participants;venue;state'})


class OpenMeteo:
    def __init__(self, transporte=None):
        self.transporte = transporte or Transporte()

    def obtener_pronostico(self, latitude, longitude, kickoff_utc):
        for value, limit in ((latitude, 90), (longitude, 180)):
            if type(value) not in (float, int) or not math.isfinite(value) or abs(value) > limit:
                raise ValueError('Coordenadas inválidas')
        kickoff = utc(kickoff_utc)
        if kickoff <= utc(ahora()):
            raise ValueError('Solo captura de pronóstico futuro; no replay retrospectivo')
        date = kickoff.date().isoformat()
        return self.transporte.obtener('open-meteo', '/v1/forecast', params={
            'latitude': latitude, 'longitude': longitude, 'timezone': 'UTC',
            'start_date': date, 'end_date': date,
            'hourly': 'temperature_2m,precipitation,wind_speed_10m',
            'temperature_unit': 'celsius', 'wind_speed_unit': 'kmh', 'precipitation_unit': 'mm'})
