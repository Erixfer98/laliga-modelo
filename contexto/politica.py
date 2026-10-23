"""Permisos explícitos: catálogo sin IDs precargados, sin fallback de suscripción."""
from dataclasses import dataclass, field
from datetime import date, timedelta
import unicodedata
from .contratos import campos, identificador

# Son selectores de catálogo, NO IDs ni cobertura verificada.
LIGAS = {
 'laliga': ('Spain', ('La Liga',)), 'premier': ('England', ('Premier League',)),
 'seriea': ('Italy', ('Serie A',)), 'bundesliga': ('Germany', ('Bundesliga',)),
 'ligue1': ('France', ('Ligue 1',)), 'ligamx': ('Mexico', ('Liga MX',)),
}
ENDPOINTS = ('/status', '/leagues', '/fixtures', '/injuries', '/fixtures/lineups', '/players/squads', '/venues')
PARAMS = {'/status': set(), '/leagues': {'country', 'name'},
 '/fixtures': {'id', 'league', 'season', 'from', 'to', 'date'}, '/injuries': {'fixture'},
 '/fixtures/lineups': {'fixture'}, '/players/squads': {'team'}, '/venues': {'id'}}


def nombre(value):
    if not isinstance(value, str): raise ValueError('Nombre inválido')
    # Solo equivalencia ortográfica, nunca distancia/fuzzy/abreviaciones adivinadas.
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                           if not unicodedata.combining(c)).split())


@dataclass(frozen=True)
class Politica:
    daily_limit: int = 100
    reserve: int = 10
    cache_seconds: int = 300
    max_retries: int = 1
    max_window_days: int = 3
    max_global_results: int = 100
    max_results: int = 200
    strategy: str = 'league_range'
    endpoints: tuple = ()
    league_seasons: dict = field(default_factory=dict)
    global_dates: dict = field(default_factory=dict)

    def __post_init__(self):
        limits = {'daily_limit': (1, 1000000), 'reserve': (0, self.daily_limit - 1),
                  'cache_seconds': (0, 86400), 'max_retries': (0, 2), 'max_window_days': (1, 31),
                  'max_global_results': (1, 100), 'max_results': (1, 1000)}
        for key, (lo, hi) in limits.items():
            if type(getattr(self, key)) is not int or not lo <= getattr(self, key) <= hi:
                raise ValueError('Límite inválido: ' + key)
        if self.strategy not in ('league_range', 'global_date') or not set(self.endpoints) <= set(ENDPOINTS):
            raise ValueError('Estrategia/endpoint no admitido')
        for lid, seasons in self.league_seasons.items():
            identificador(lid)
            if not isinstance(seasons, list) or any(type(s) is not int or not 2000 <= s <= 2100 for s in seasons):
                raise ValueError('Permiso de temporada inválido')
        for day, expected in self.global_dates.items():
            date.fromisoformat(day)
            if type(expected) is not int or not 0 <= expected <= self.max_global_results:
                raise ValueError('Consulta global sin estimación eficiente aceptada')

    @classmethod
    def cargar(cls, obj):
        campos(obj, cls.__dataclass_fields__)
        return cls(**{**obj, 'endpoints': tuple(obj['endpoints'])})

    def ventana(self, start, end):
        a, b = date.fromisoformat(start), date.fromisoformat(end)
        if not 0 <= (b - a).days < self.max_window_days: raise ValueError('Ventana fuera del límite')
        return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]

    def permiso(self, endpoint, params):
        if endpoint not in PARAMS or not set(params) <= PARAMS[endpoint]:
            return False, 'invalid_query'
        try:
            keys = set(params)
            shapes = {'/status': [set()], '/leagues': [{'country', 'name'}],
                '/fixtures': [{'id'}, {'date'}, {'league', 'season', 'from', 'to'}, {'league', 'season', 'date'}],
                '/injuries': [{'fixture'}], '/fixtures/lineups': [{'fixture'}],
                '/players/squads': [{'team'}], '/venues': [{'id'}]}
            if keys not in shapes[endpoint]: raise ValueError('Forma inválida')
            for k, v in params.items():
                if k in ('id', 'league', 'fixture', 'team'):
                    if type(v) is not int: raise ValueError('ID inválido')
                    identificador(str(v))
                elif k == 'season':
                    if type(v) is not int or not 2000 <= v <= 2100: raise ValueError('Temporada inválida')
                elif k in ('date', 'from', 'to'):
                    if not isinstance(v, str) or date.fromisoformat(v).isoformat() != v: raise ValueError('Fecha inválida')
                elif not isinstance(v, str) or not v or len(v) > 80: raise ValueError('Selector inválido')
            if endpoint == '/leagues' and (params['country'], params['name']) not in [(c, n[0]) for c,n in LIGAS.values()]:
                raise ValueError('Selector no admitido')
            if 'from' in params: self.ventana(params['from'], params['to'])
        except (ValueError, TypeError, KeyError): return False, 'invalid_query'
        if endpoint not in self.endpoints: return False, 'endpoint_not_authorized' 
        if endpoint == '/fixtures' and 'league' in params:
            if params.get('season') not in self.league_seasons.get(str(params['league']), []):
                return False, 'season_permission_unverified'
        if endpoint == '/fixtures' and 'date' in params and 'league' not in params:
            if self.strategy != 'global_date' or params['date'] not in self.global_dates:
                return False, 'date_permission_unverified'
        return True, None
