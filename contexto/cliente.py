"""Cliente API-Football consciente del plan; no consulta fuera de permisos explícitos."""
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import time
from .conectores import Transporte, NoDisponible
from .contratos import canonico, ahora, utc
from .operaciones import Cancelada


@dataclass
class Resultado:
    status: str
    code: str
    restriction: str | None = None
    capture: object = None
    record_id: str | None = None
    cached: bool = False

    def publico(self):
        return {'status': self.status, 'code': self.code, 'restriction': self.restriction,
                'record_id': self.record_id, 'cached': self.cached}


def clasificar(errors):
    if not errors: return None
    text = canonico(errors).casefold()
    restriction = ('season' if 'season' in text else 'date' if 'date' in text else
                   'endpoint' if 'endpoint' in text else 'subscription')
    if any(w in text for w in ('subscription', 'free plan', 'paid plan', 'upgrade', 'access to this', 'plan does not', 'plan do not')):
        return 'subscription_required', restriction
    if 'season' in text: return 'season_restricted', 'season'
    if 'date' in text: return 'date_restricted', 'date'
    if 'limit' in text or 'quota' in text:
        return ('quota_exhausted', 'day') if ('day' in text or 'daily' in text) else ('rate_limited', 'rate')
    return 'provider_error', None


def retry_seconds(value):
    if value is None: return 60.
    try:
        seconds = float(value)
        if seconds >= 0 and seconds < float('inf'): return seconds
    except (ValueError, TypeError): pass
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None: return 60.
        return max(0., (dt - datetime.now(timezone.utc)).total_seconds())
    except (ValueError, TypeError, OverflowError): return 60.


class Cliente:
    def __init__(self, key, policy, store, transporte=None):
        self.key = key; self.policy = policy; self.store = store
        self.transporte = transporte or Transporte()

    def _scope(self, endpoint, params, restriction):
        if restriction == 'season': return endpoint + '|season|' + str(params.get('league')) + '|' + str(params.get('season'))
        if restriction == 'date': return endpoint + '|date|' + str(params.get('date', (params.get('from'), params.get('to'))))
        return endpoint + '|endpoint'

    def consultar(self, endpoint, params=None, purpose='discovery', cancel=None, dry_run=True):
        params = params or {}
        allowed, reason = self.policy.permiso(endpoint, params)
        if not allowed: return Resultado('blocked', reason)
        if dry_run: return Resultado('planned', 'dry_run')
        if not self.key: return Resultado('blocked', 'credentials_missing')
        key = sha256(canonico({'provider': 'api-football', 'endpoint': endpoint, 'params': params}).encode()).hexdigest()
        try:
            with self.store.exclusivo(cancel):
                if cancel and cancel.is_set(): raise Cancelada('Cancelada')
                for scope in (self._scope(endpoint, params, r) for r in ('season', 'date', 'endpoint')):
                    denial = self.store.control('denial:' + scope)
                    if denial: return Resultado('blocked', denial['code'], denial['restriction'])
                # Nunca convertir un rechazo de temporada en consulta global por fecha.
                if endpoint == '/fixtures' and 'league' not in params:
                    if self.store.control('fixture_subscription_denied'):
                        return Resultado('blocked', 'subscription_required', 'no_alternative_query')
                if self.store.control('credentials_invalid'): return Resultado('blocked', 'credentials_invalid')
                if (self.store.control('cooldown') or 0) > time.time(): return Resultado('blocked', 'rate_limited', 'retry_after')
                cached = self.store.cache(key)
                if cached:
                    cap, _ = self.store.captura(cached)
                    return Resultado('ok', 'cached', capture=cap, record_id=cached, cached=True)
                for n in range(self.policy.max_retries + 1):
                    if cancel and cancel.is_set(): raise Cancelada('Cancelada')
                    attempt = self.store.reservar(endpoint, key, 'retry' if n else purpose,
                                                  self.policy.daily_limit, self.policy.reserve)
                    if attempt is None: return Resultado('blocked', 'daily_budget_exhausted')
                    cap = None; restriction = None; wait = 0.
                    try:
                        cap = self.transporte.obtener('api-football', endpoint, params=params,
                                                       headers={'x-apisports-key': self.key})
                        # Incluso un proveedor que refleje la clave no debe archivarla o devolverla.
                        if self.key.encode() in cap.contenido:
                            self.store.terminar(attempt, 'credential_echo_rejected')
                            return Resultado('error', 'credential_echo_rejected')
                        remaining = cap.http_info.get('remaining')
                        if type(remaining) is int and remaining >= 0:
                            day = utc(ahora()).date().isoformat()
                            observed = self.store.control('remaining:' + day)
                            self.store.control('remaining:' + day, min(remaining, observed) if observed is not None else remaining)
                        data = cap.json(); error = clasificar(data.get('errors'))
                        if error: code, restriction = error
                        elif not isinstance(data.get('response'), (list, dict)):
                            code = 'invalid_provider_contract'
                        else: code = 'ok'
                    except NoDisponible as exc:
                        status = exc.status
                        code = ('rate_limited' if status == 429 else 'credentials_invalid' if status == 401 else
                                'access_denied' if status == 403 else 'transient_error' if status is None or status >= 500 else 'http_error')
                        if status == 429: wait = retry_seconds(exc.retry_after)
                    except ValueError:
                        code = 'invalid_provider_contract'
                    self.store.terminar(attempt, code, restriction)
                    record_id = None
                    if cap is not None:
                        record = self.store.guardar(cap, 'request', {'endpoint': endpoint, 'params': params,
                                                                    'validation_state': code})
                        record_id = record['id']
                    if code in ('subscription_required', 'season_restricted', 'date_restricted'):
                        denial = {'code': code, 'restriction': restriction}
                        self.store.control('denial:' + self._scope(endpoint, params, restriction), denial)
                        if endpoint == '/fixtures': self.store.control('fixture_subscription_denied', True)
                        return Resultado('blocked', code, restriction, record_id=record_id)
                    if code == 'credentials_invalid': self.store.control('credentials_invalid', True)
                    if code == 'quota_exhausted': self.store.control('remaining:' + utc(ahora()).date().isoformat(), 0)
                    if code == 'rate_limited':
                        wait = wait or 60.
                        self.store.control('cooldown', time.time() + wait)
                    if cancel and cancel.is_set(): raise Cancelada('Cancelada')
                    if code == 'ok':
                        self.store.cache(key, record_id, self.policy.cache_seconds)
                        return Resultado('ok', 'ok', capture=cap, record_id=record_id)
                    if code not in ('transient_error', 'rate_limited') or n == self.policy.max_retries or wait > 1:
                        return Resultado('error', code, restriction, record_id=record_id)
                    if cancel:
                        if cancel.wait(wait or 1.): raise Cancelada('Cancelada')
                    else: time.sleep(wait or 1.)
        except Cancelada:
            return Resultado('cancelled', 'cancelled')
        return Resultado('error', 'retry_exhausted')
