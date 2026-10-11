"""Worker experimental de larga duración, sin capturas/scheduler por defecto."""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import threading
import time
from .almacen import Archivo
from .operaciones import Operaciones, Cancelada
from .respaldo import Respaldos, R2Config, RespaldoBloqueado
from .contratos import ahora, canonico, utc
from .cliente import Cliente
from .politica import Politica
from .cli_b2 import validar_configuracion
from .servicio import ciclo


class StopToken:
    """El handler solo asigna un booleano: Event.set() puede deadlock dentro de Event.wait()."""
    def __init__(self):
        self.requested = False
        self.sleeper = threading.Event()

    def set(self): self.requested = True
    def is_set(self): return self.requested

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self.requested:
            remaining = .1 if deadline is None else min(.1, deadline - time.monotonic())
            if remaining <= 0: break
            self.sleeper.wait(remaining)
        return self.requested


def boolean(env, name):
    value = env.get(name, 'false')
    if value not in ('false', 'true'): raise ValueError('Flag inválido')
    return value == 'true'


def integer(env, name, default, low, high):
    value = int(env.get(name, str(default)))
    if not low <= value <= high: raise ValueError('Intervalo/límite inválido')
    return value


@dataclass(frozen=True)
class Settings:
    root: Path = Path('/var/data/kuota-context')
    scheduler: bool = False
    captures: bool = False
    storage_authorized: bool = False
    interval: int = 86400
    heartbeat: int = 60
    window: int = 1
    max_bytes: int = 64 * 1024 * 1024

    @classmethod
    def desde_env(cls, env):
        root = Path(env.get('KUOTA_CONTEXT_STORAGE_ROOT', '/var/data/kuota-context'))
        if not root.is_absolute() or Path('/var/data') not in root.parents or '..' in root.parts: raise ValueError('Ruta fuera del disco')
        return cls(root, boolean(env, 'KUOTA_CONTEXT_SCHEDULER_ENABLED'), boolean(env, 'KUOTA_CONTEXT_CAPTURES_ENABLED'),
            boolean(env, 'KUOTA_CONTEXT_STORAGE_AUTHORIZED'),
            integer(env,'KUOTA_CONTEXT_INTERVAL_SECONDS',86400,60,7*86400),
            integer(env,'KUOTA_CONTEXT_HEARTBEAT_SECONDS',60,5,300),
            integer(env,'KUOTA_CONTEXT_WINDOW_DAYS',1,1,3),
            integer(env,'KUOTA_CONTEXT_MAX_ARCHIVE_MB',64,1,256)*1024*1024)


def abrir(settings):
    if not settings.storage_authorized: raise ValueError('storage_not_authorized')
    mount = Path('/var/data')
    if not mount.is_dir() or not os.path.ismount(mount): raise ValueError('persistent_mount_missing')
    # Rechazar symlinks que escapen del disco; mount real, no dos carpetas como backup.
    if mount.resolve() not in settings.root.resolve().parents: raise ValueError('storage_outside_mount')
    if settings.root.is_symlink(): raise ValueError('storage_symlink_not_allowed')
    settings.root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(settings.root, 0o700)
    staging = settings.root/'staging'; staging.mkdir(exist_ok=True, mode=0o700)
    if staging.is_symlink() or settings.root.resolve() not in staging.resolve().parents: raise ValueError('staging_outside_archive')
    if shutil.disk_usage(settings.root).free < settings.max_bytes*3 + 64*1024*1024: raise ValueError('disk_space_low')
    os.chmod(staging, 0o700)
    archive = settings.root/'contexto.sqlite'
    if archive.is_symlink(): raise ValueError('archive_symlink_not_allowed')
    return Operaciones(Archivo(archive))


@contextmanager
def consumidor_unico(store):
    # Lock distinto del lock por solicitud, mantenido durante TODA la vida del worker.
    with open(str(store.archivo.path)+'.worker.lock', 'a') as f:
        try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('worker_already_running') from None
        try: yield
        finally: fcntl.flock(f, fcntl.LOCK_UN)


class Worker:
    def __init__(self, settings, store=None, backups=None, client=None, config=None, runner=ciclo, stop=None, log=None):
        self.settings=settings; self.store=store; self.backups=backups; self.client=client; self.config=config
        self.runner=runner; self.stop=stop if stop is not None else StopToken(); self.log=log or (lambda obj: print(canonico(obj), flush=True))

    def emit(self, code, **counts):
        self.log({'event':code,'at_utc':ahora(),'experimental':True,**counts})

    def tick(self):
        if not self.settings.scheduler or not self.settings.captures: return 'disabled'
        if self.store is None: return 'storage_blocked'
        if self.stop.is_set(): return 'stopping'
        due = self.store.control('worker:next_due_utc')
        if due and utc(ahora()) < utc(due): return 'waiting'
        if not self.config or not self.client or not all(self.config[k] for k in ('live_authorized','credential_rotated','network_authorized','restore_verified')) or not self.client.key:
            return 'provider_authorization_missing'
        if self.settings.window > self.client.policy.max_window_days: return 'window_policy_invalid'
        if self.store.control('worker:quota_reconciliation_required'): return 'quota_reconciliation_required'
        if not self.backups: return 'external_backup_missing'
        if self.store.archivo.path.stat().st_size > self.settings.max_bytes: return 'archive_pilot_limit'
        # Persistir antes del intento: reinicio/crash no produce ciclo inmediato duplicado.
        start = utc(ahora())
        self.store.control('worker:next_due_utc', (start+timedelta(seconds=self.settings.interval)).isoformat())
        try:
            self.backups.exportar(self.stop)  # Prueba real round-trip ANTES de cualquier captura.
            if self.stop.is_set(): return 'stopping'
            result = self.runner(self.client, start.date().isoformat(), (start.date()+timedelta(days=self.settings.window-1)).isoformat(),
                self.config['seasons'], weather_authorized=self.config['weather_authorized'], cancel=self.stop)
            if self.stop.is_set(): return 'stopping'
            # Exportar también el ledger/capturas nuevas; si falla no repetir consultas antes de next_due.
            self.backups.exportar(self.stop)
            self.store.control('worker:last_completed_at_utc', ahora())
            self.emit('cycle_completed', accepted=len(result['accepted']), rejected=len(result['rejected']))
            return 'completed'
        except Cancelada: return 'stopping'
        except RespaldoBloqueado: return 'external_backup_unverified'
        except Exception: return 'cycle_failed'  # No mensaje/traceback que pueda exponer configuración/SDK.

    def limpiar_staging(self):
        # Solo temporales propios, bajo ambos locks; no borrar archivos SQLite o pruebas.
        with self.store.exclusivo(self.stop):
            for path in self.backups.staging.iterdir():
                if path.name.startswith(('export-', 'retention-')) and path.is_dir() and not path.is_symlink(): shutil.rmtree(path)

    def run(self):
        self.emit('worker_started', scheduler_enabled=self.settings.scheduler, captures_enabled=self.settings.captures)
        def loop():
            while not self.stop.is_set():
                self.emit(self.tick())
                self.stop.wait(self.settings.heartbeat)
        try:
            if self.store:
                with consumidor_unico(self.store):
                    if self.backups: self.limpiar_staging()
                    loop()
            else: loop()  # Deshabilitado sin disco/secretos: sigue vivo, no abre archivos ni red.
        finally:
            # SQLite usa commits transaccionales por operación; no dependemos de un flush al morir.
            self.emit('worker_stopped')


def build(settings, env, stop=None):
    store=None; backups=None; client=None; config=None
    if settings.storage_authorized: store=abrir(settings)
    if store:
        if env.get('KUOTA_CONTEXT_POLICY_JSON'):
            config, policy = validar_configuracion(json.loads(env['KUOTA_CONTEXT_POLICY_JSON']))
            client=Cliente(env.get('KUOTA_API_FOOTBALL_KEY'),policy,store)
        try: backups=Respaldos(store,settings.root/'staging',R2Config.desde_env(env))
        except RespaldoBloqueado: pass
    return Worker(settings,store,backups,client,config,stop=stop)


def diagnostico(worker, env, connectivity=False, external=False, reconcile=False):
    result={'experimental':True,'captures_started':False,'scheduler_enabled':worker.settings.scheduler,
        'storage_available':worker.store is not None,'external_connected':False,'provider_connected':False}
    policy = worker.client.policy if worker.client else Politica()
    result['budget_limits'] = {'daily_limit_local':policy.daily_limit,'reserve':policy.reserve,
                              'calls_today_local':None,'provider_remaining_observed':None}
    if worker.store:
        result['archive']=worker.store.verificar(); result['budget']=worker.store.consumo()
        result['archive_bytes']=worker.store.archivo.path.stat().st_size
        result['disk_free_bytes']=shutil.disk_usage(worker.store.archivo.path.parent).free
        result['budget_limits']['calls_today_local']=sum(r['calls'] for r in result['budget'] if r['day']==ahora()[:10])
        result['budget_limits']['provider_remaining_observed']=worker.store.control('remaining:'+ahora()[:10])
        result['exports_today_local']=worker.store.control('worker:exports:'+ahora()[:10]) or 0
    if external:
        if not worker.backups: raise ValueError('external_backup_missing')
        worker.backups.exportar(worker.stop); result['external_connected']=True; result['restore_roundtrip_verified']=True
    if reconcile and not connectivity: raise ValueError('reconciliation_requires_live_status')
    if connectivity:
        if not worker.store or not boolean(env,'KUOTA_CONTEXT_PROVIDER_DIAGNOSTICS_AUTHORIZED') or not worker.config or not all(worker.config[k] for k in ('credential_rotated','network_authorized')) or not env.get('KUOTA_API_FOOTBALL_KEY'):
            raise ValueError('diagnostic_not_authorized')
        policy=Politica(endpoints=('/status',),daily_limit=worker.client.policy.daily_limit,reserve=worker.client.policy.reserve,cache_seconds=0)
        client=Cliente(env['KUOTA_API_FOOTBALL_KEY'],policy,worker.store,worker.client.transporte)
        status=client.consultar('/status',purpose='verification',cancel=worker.stop,dry_run=False)
        result['provider_status']=status.publico(); result['provider_connected']=status.status=='ok'
        if reconcile:
            if status.status!='ok' or type(status.capture.http_info.get('remaining')) is not int: raise ValueError('quota_not_verified')
            worker.store.control('worker:quota_reconciliation_required',False); result['quota_reconciled']=True
        result['budget']=worker.store.consumo()
        result['budget_limits']['calls_today_local']=sum(r['calls'] for r in result['budget'] if r['day']==ahora()[:10])
        result['budget_limits']['provider_remaining_observed']=worker.store.control('remaining:'+ahora()[:10])
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('run','diagnostico','exportar','restaurar'))
    parser.add_argument('--connectivity',action='store_true'); parser.add_argument('--external',action='store_true')
    parser.add_argument('--reconcile-quota',action='store_true'); parser.add_argument('--execute',action='store_true')
    parser.add_argument('--manifest'); parser.add_argument('--destination')
    args=parser.parse_args(argv); os.umask(0o077); stop=StopToken()
    def shutdown(_signum,_frame): stop.set()  # Nada de red/SQLite dentro del manejador.
    signal.signal(signal.SIGTERM,shutdown); signal.signal(signal.SIGINT,shutdown)
    try:
        settings=Settings.desde_env(os.environ); worker=build(settings,os.environ,stop)
        if args.command=='run': worker.run(); return
        if args.command=='diagnostico':
            if (args.connectivity or args.external or args.reconcile_quota) and not args.execute: raise ValueError('explicit_authorization_required')
            # Diagnósticos administrativos se serializan mediante el lock por operación,
            # no compiten por el lock de vida del scheduler deshabilitado.
            result=diagnostico(worker,os.environ,args.connectivity,args.external,args.reconcile_quota)
        elif not args.execute: result={'dry_run':True,'network_requests':0,'command':args.command}
        else:
            if not worker.backups or not worker.store: raise ValueError('external_backup_missing')
            if args.command=='exportar': result=worker.backups.exportar(stop)
            else: result=worker.backups.restaurar(args.manifest,args.destination,stop)
        print(canonico(result),flush=True)
    except Cancelada: parser.exit(0,'Operación detenida.\n')
    except Exception: parser.exit(2,'Worker bloqueado: configuración, exclusión, almacenamiento o respaldo no verificados.\n')


if __name__=='__main__': main()
