"""Worker/R2 SINTÉTICOS, sin recursos de pago, credenciales reales o tráfico remoto."""
import copy
from dataclasses import replace
from datetime import timedelta
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import pytest
from contexto.almacen import Archivo
from contexto.operaciones import Operaciones, Cancelada
from contexto.respaldo import R2Config, Respaldos, RespaldoBloqueado, hash_file
from contexto.worker import Settings, Worker, consumidor_unico, diagnostico, build, abrir
from contexto.cliente import Cliente
from contexto.politica import Politica
from contexto.contratos import ahora, canonico, utc
from test_contexto_b1 import muestra, PROOF
from test_contexto_b2 import capture

from contexto_fakes import setup, SECRET






def active(setup):
    store,backups,remote=setup
    config={'live_authorized':True,'credential_rotated':True,'network_authorized':True,'restore_verified':True,'seasons':{},'weather_authorized':False}
    client=Cliente(SECRET,Politica(),store)
    reports=[]
    def runner(*args,**kwargs): reports.append(args); return {'accepted':[],'rejected':[]}
    return Worker(Settings(scheduler=True,captures=True,interval=60),store,backups,client,config,runner,log=lambda obj:None),reports


def test_disabled_worker_lives_without_storage_or_network():
    logs=[]; stop=threading.Event()
    def log(obj):
        logs.append(obj)
        if obj['event']=='disabled': stop.set()
    worker=Worker(Settings(),stop=stop,log=log)
    worker.run()
    assert [r['event'] for r in logs]==['worker_started','disabled','worker_stopped']


@pytest.mark.parametrize("termination", [signal.SIGTERM, signal.SIGINT])
def test_subprocess_signal_idle_clean_exit(termination):
    env={k:v for k,v in os.environ.items() if not k.startswith(('KUOTA_CONTEXT_','KUOTA_API_'))}
    proc=subprocess.Popen([sys.executable,'-u','-m','contexto.worker','run'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert json.loads(proc.stdout.readline())['event']=='worker_started'
        assert json.loads(proc.stdout.readline())['event']=='disabled'
        proc.send_signal(termination)
        out,err=proc.communicate(timeout=5)
        assert proc.returncode==0 and 'worker_stopped' in out and not err
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()


@pytest.mark.parametrize('env',[{'KUOTA_CONTEXT_SCHEDULER_ENABLED':'1'},{'KUOTA_CONTEXT_STORAGE_ROOT':'/tmp/context'}, {'KUOTA_CONTEXT_INTERVAL_SECONDS':'0'}, {'KUOTA_CONTEXT_WINDOW_DAYS':'4'}, {'KUOTA_CONTEXT_MAX_ARCHIVE_MB':'999'}])
def test_invalid_worker_settings_fail_closed(env):
    with pytest.raises(ValueError): Settings.desde_env(env)


def test_default_env_does_not_read_key_or_create_archive():
    settings=Settings.desde_env({})
    worker=build(settings,{'KUOTA_API_FOOTBALL_KEY':SECRET})
    assert worker.store is None and worker.client is None and worker.tick()=='disabled'


def test_missing_mount_and_same_disk_not_independent(monkeypatch,tmp_path):
    monkeypatch.setattr('contexto.worker.os.path.ismount',lambda p:False)
    with pytest.raises(ValueError): abrir(Settings(storage_authorized=True))
    from contexto.configuracion import AlmacenConfigurado
    # Ruta autorizada simulada pero dos directorios del MISMO device siguen siendo inválidos.
    a=tmp_path/'a'; b=tmp_path/'b'; a.mkdir(); b.mkdir()
    with pytest.raises(ValueError): AlmacenConfigurado(a,b,'synthetic claim').validar()


def test_single_consumer_and_released_lock(setup):
    store,_,_=setup
    with consumidor_unico(store):
        with pytest.raises(ValueError):
            with consumidor_unico(Operaciones(Archivo(store.archivo.path))): pass
    with consumidor_unico(store): pass


def test_worker_missing_backup_blocks_every_provider_call(setup):
    worker,reports=active(setup); worker.backups=None
    assert worker.tick()=='external_backup_missing' and not reports
    assert worker.store.consumo()==[]


def test_failed_external_export_blocks_and_sanitizes(setup):
    worker,reports=active(setup); setup[2].fail=True
    assert worker.tick()=='external_backup_unverified' and not reports
    assert worker.store.control('worker:external_backup') is None
    assert worker.tick()=='waiting' # No bucle de reintentos o consultas externas.
    assert SECRET not in canonico(worker.store.consumo())


def test_worker_restart_preserves_next_due_and_budget(setup):
    worker,reports=active(setup)
    worker.store.reservar('/status','a'*64,'verification',100,10)
    assert worker.tick()=='completed' and len(reports)==1
    reopened=Operaciones(Archivo(worker.store.archivo.path)); next_due=reopened.control('worker:next_due_utc')
    worker2,_=active(setup); worker2.store=reopened
    assert worker2.tick()=='waiting' and reopened.control('worker:next_due_utc')==next_due
    assert reopened.consumo()[0]['status']=='reserved' and len(reports)==1












def test_cancel_backup_before_network_and_midcycle_shutdown(setup):
    store,b,r=setup; stop=threading.Event(); stop.set()
    with pytest.raises(Cancelada): b.exportar(stop)
    assert not r.calls
    worker,reports=active(setup)
    def runner(*a,**kw): worker.stop.set(); return {'accepted':[],'rejected':[]}
    worker.runner=runner
    assert worker.tick()=='stopping' and worker.store.control('worker:last_completed_at_utc') is None
    assert worker.tick()=='stopping'


def test_diagnostic_offline_no_remote_calls(setup):
    worker,reports=active(setup)
    result=diagnostico(worker,{})
    assert result['captures_started'] is False and not setup[2].calls and not reports
    assert result['storage_available'] and result['provider_connected'] is False
    assert result['budget_limits']=={'daily_limit_local':100,'reserve':10,'calls_today_local':0,'provider_remaining_observed':None}
    assert result['disk_free_bytes'] > 0 and result['archive_bytes'] > 0


def test_diagnostic_status_only_with_explicit_authorization(setup):
    worker,reports=active(setup)
    class StatusOnly:
        calls=[]
        def obtener(self,provider,endpoint,params,headers):
            self.calls.append(endpoint); assert endpoint=='/status'
            return capture({'errors':[],'response':{}},'/status',remaining=90)
    transport=StatusOnly(); worker.client.transporte=transport
    worker.store.control('worker:quota_reconciliation_required',True)
    with pytest.raises(ValueError): diagnostico(worker,{},connectivity=True)
    result=diagnostico(worker,{'KUOTA_CONTEXT_PROVIDER_DIAGNOSTICS_AUTHORIZED':'true','KUOTA_API_FOOTBALL_KEY':SECRET},connectivity=True,reconcile=True)
    assert transport.calls==['/status'] and result['quota_reconciled'] and not reports
    assert worker.store.control('worker:quota_reconciliation_required') is False
    assert SECRET not in canonico(result)


def test_restored_archive_requires_quota_reconciliation(setup):
    worker,reports=active(setup); worker.store.control('worker:quota_reconciliation_required',True)
    assert worker.tick()=='quota_reconciliation_required' and not reports


def test_cleanup_only_orphan_owned_staging(setup):
    worker,_=active(setup); folder=worker.backups.staging
    (folder/'export-SYNTHETIC-orphan').mkdir(); (folder/'export-SYNTHETIC-orphan'/'snapshot').write_text('old')
    (folder/'operator-owned').mkdir(); (folder/'important.sqlite').write_text('preserve')
    worker.limpiar_staging()
    assert not (folder/'export-SYNTHETIC-orphan').exists() and (folder/'operator-owned').exists() and (folder/'important.sqlite').exists()










def test_same_device_backups_rejected_even_with_absolute_durable_paths(monkeypatch):
    from types import SimpleNamespace
    from contexto.configuracion import AlmacenConfigurado
    monkeypatch.setattr(Path,'is_dir',lambda _:True)
    monkeypatch.setattr(Path,'stat',lambda *a,**kw:SimpleNamespace(st_dev=99))
    with pytest.raises(ValueError,match='otro sistema de archivos'):
        AlmacenConfigurado(Path('/synthetic-volume/archive'),Path('/synthetic-volume/staging'),'SYNTHETIC').validar()


def test_single_consumer_across_processes(setup):
    store,_,_=setup
    script='from contexto.almacen import Archivo; from contexto.operaciones import Operaciones; from contexto.worker import consumidor_unico; import sys\ns=Operaciones(Archivo(sys.argv[1]))\ntry:\n with consumidor_unico(s): sys.exit(0)\nexcept ValueError: sys.exit(2)'
    with consumidor_unico(store):
        proc=subprocess.run([sys.executable,'-c',script,str(store.archivo.path)],capture_output=True,text=True,timeout=10)
    assert proc.returncode==2 and not proc.stdout and not proc.stderr


def test_render_proposal_manages_only_experimental_worker():
    # Estructura pequeña sin dependencia YAML en el runtime.
    text=(Path(__file__).parents[1]/'render-context.yaml').read_text()
    assert text.count('  - type:')==1 and 'type: worker' in text and 'name: kuota-api' not in text
    assert 'plan: 0.5c-512mb' in text and 'region: oregon' in text and 'sizeGB: 5' in text
    assert 'branch: feature/fase-5-inteligencia-contextual' in text and 'autoDeployTrigger: "off"' in text
    assert 'python -u -m contexto.worker run' in text and 'name: kuota-context-worker' in text
    assert SECRET not in text and 'NEXT_PUBLIC' not in text and 'envVarGroups:' not in text


def test_admin_diagnostics_can_bootstrap_disabled_running_worker(setup):
    worker,_=active(setup); worker.settings=Settings()
    with consumidor_unico(worker.store):
        result=diagnostico(worker,{},external=True)
    assert result['restore_roundtrip_verified'] and result['captures_started'] is False


def test_sdk_failure_does_not_expose_credentials_on_cli(tmp_path):
    # El CLI sin infraestructura autorizada bloquea antes de SDK o consultas.
    env={k:v for k,v in os.environ.items() if not k.startswith(('KUOTA_CONTEXT_','KUOTA_API_'))}
    env['KUOTA_CONTEXT_R2_SECRET_ACCESS_KEY']=SECRET
    proc=subprocess.run([sys.executable,'-m','contexto.worker','exportar','--execute'],env=env,capture_output=True,text=True,timeout=5)
    assert proc.returncode==2 and SECRET not in proc.stdout+proc.stderr


def test_synthetic_mount_initializes_private_archive_without_network(tmp_path,monkeypatch):
    mount=Path('/var/data'); original_resolve=Path.resolve; original_is_dir=Path.is_dir
    monkeypatch.setattr(Path,'resolve',lambda self,*a,**kw:tmp_path if self==mount else original_resolve(self,*a,**kw))
    monkeypatch.setattr(Path,'is_dir',lambda self:True if self==mount else original_is_dir(self))
    monkeypatch.setattr('contexto.worker.os.path.ismount',lambda p:p==mount)
    settings=Settings(root=tmp_path/'archive',storage_authorized=True)
    worker=build(settings,{})
    assert worker.store.verificar()=={'fixtures':0,'captures':0} and worker.tick()=='disabled'
    assert settings.root.stat().st_mode & 0o777==0o700
    assert (settings.root/'staging').stat().st_mode & 0o777==0o700
    assert worker.client is None and worker.backups is None


def test_cycle_does_not_use_rejected_catalog_captures(setup,monkeypatch):
    from contexto.servicio import ciclo
    store,_,_=setup; rec=store.archivo.verificar()[0]
    store.guardar(capture({'errors':[],'response':[{'league':{}}]},'/leagues'),'request',{'endpoint':'/leagues','validation_state':'ok'})
    class Discovery:
        def __init__(self,client): pass
        def descubrir(self,*a,**kw):
            return {'catalog':{'laliga':{'status':'blocked','code':'catalog_contract_invalid'}},'accepted':[{'receipt_id':rec['receipt_id'],'eligible_future':True}],'rejected':[]}
    monkeypatch.setattr('contexto.servicio.Descubrimiento',Discovery)
    client=Cliente(SECRET,Politica(),store)
    result=ciclo(client,'2099-01-02','2099-01-02',{})
    assert result['context'][0]['dataset']['facts']==[] and store.consumo()==[]
