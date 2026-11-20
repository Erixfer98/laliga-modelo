"""Respaldo R2/SQLite SINTÉTICO: memoria/SDK Stubber, cero conexiones reales."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import pytest
import threading
from contexto.almacen import Archivo
from contexto.operaciones import Operaciones, Cancelada
from contexto.respaldo import R2Config, Respaldos, RespaldoBloqueado
from contexto.contratos import ahora, utc
from contexto_fakes import setup, SECRET

def test_export_roundtrip_and_restore_new_path_preserves_evidence(setup,tmp_path):
    store,backups,remote=setup
    store.reservar('/status','a'*64,'verification',100,10)
    receipt=backups.exportar()
    assert receipt['roundtrip_verified'] and receipt['counts']=={'fixtures':1,'captures':0}
    destination=tmp_path/'restored.sqlite'; info=backups.restaurar(receipt['manifest_key'],destination)
    restored=Operaciones(Archivo(destination))
    assert restored.archivo.verificar()==store.archivo.verificar()
    assert restored.control('worker:quota_reconciliation_required') is True
    assert restored.consumo()==store.consumo()
    assert info['provider_quota_reconciliation_required'] and info['promotion_required']
    with pytest.raises(ValueError): backups.restaurar(receipt['manifest_key'],store.archivo.path)
    assert not list(backups.staging.iterdir())


def test_corrupt_remote_bytes_fail_gate(setup):
    store,backups,remote=setup
    original=remote.upload
    def corrupt(path,key,cancel=None):
        original(path,key,cancel)
        if key.endswith('.sqlite'): remote.data[key]=b'SYNTHETIC corrupted'
    remote.upload=corrupt
    with pytest.raises(RespaldoBloqueado) as error: backups.exportar()
    assert str(error.value)=='external_backup_unverified' and SECRET not in str(error.value)
    assert store.control('worker:external_backup') is None


def test_namespace_change_rejects_restore(setup,tmp_path):
    store,b,r=setup; receipt=b.exportar()
    other=Respaldos(store,b.staging,replace(b.config,bucket='other-private'),r)
    with pytest.raises(RespaldoBloqueado): other.restaurar(receipt['manifest_key'],tmp_path/'restore.sqlite')
    assert not (tmp_path/'restore.sqlite').exists()


def test_retention_keeps_minimum_and_never_deletes_foreign_keys(setup,monkeypatch):
    store,b,r=setup
    now=utc(ahora())
    for i in range(5):
        monkeypatch.setattr('contexto.respaldo.ahora',lambda i=i:(now-timedelta(days=60-i)).isoformat())
        b.exportar()
    r.data['outside/manifest.json']=b'FOREIGN'; r.data[b.config.prefix+'manual.sqlite']=b'FOREIGN'
    monkeypatch.setattr('contexto.respaldo.ahora',lambda:now.isoformat())
    current=b.exportar()
    manifests=[k for k in r.data if k.startswith(b.config.prefix) and k.endswith('/manifest.json')]
    assert len(manifests)==b.config.keep_min and current['manifest_key'] in manifests
    assert r.data['outside/manifest.json']==b'FOREIGN' and r.data[b.config.prefix+'manual.sqlite']==b'FOREIGN'


def test_export_daily_budget_persists_and_counts_failures(setup):
    store,b,r=setup; b.config=replace(b.config,max_exports_day=1)
    r.fail=True
    with pytest.raises(RespaldoBloqueado): b.exportar()
    r.fail=False
    with pytest.raises(RespaldoBloqueado): b.exportar()
    assert len(r.calls)==1 and store.control('worker:exports:'+ahora()[:10])==1


@pytest.mark.parametrize('field,value',[('endpoint','https://example.com'),('bucket','..'),('prefix','../escape/'),('retention_days',0),('keep_min',1),('access_key',''),('max_exports_day',0)])
def test_external_config_strict_and_no_repr_secrets(setup,field,value):
    cfg=replace(setup[1].config,**{field:value})
    with pytest.raises(ValueError): cfg.validar()
    assert SECRET not in repr(cfg)


def test_env_external_default_denied():
    with pytest.raises(RespaldoBloqueado): R2Config.desde_env({})


def test_r2_sdk_stubbed_upload_download_list_delete(setup,tmp_path):
    from botocore.stub import Stubber, ANY
    from botocore.response import StreamingBody
    from io import BytesIO
    from contexto.respaldo import R2
    r2=R2(setup[1].config); stub=Stubber(r2.client); bucket=r2.config.bucket; key=r2.config.prefix+'synthetic'
    raw=b'SYNTHETIC SDK object'; source=tmp_path/'source'; source.write_bytes(raw)
    stub.add_response('put_object', {'ETag':'"synthetic"'}, {'Bucket':bucket,'Key':key,'Body':ANY})
    stub.add_response('get_object', {'ContentLength':len(raw),'Body':StreamingBody(BytesIO(raw),len(raw))}, {'Bucket':bucket,'Key':key})
    stub.add_response('list_objects_v2', {'Contents':[{'Key':key}],'IsTruncated':False}, {'Bucket':bucket,'Prefix':r2.config.prefix})
    stub.add_response('delete_object', {}, {'Bucket':bucket,'Key':key})
    with stub:
        r2.upload(source,key); r2.download(key,tmp_path/'downloaded',100)
        assert (tmp_path/'downloaded').read_bytes()==raw and list(r2.objects())==[key]
        r2.delete(key); stub.assert_no_pending_responses()
    assert r2.client.meta.config.retries['total_max_attempts']==1
    assert r2.client.meta.config.request_checksum_calculation=='when_required'


def test_r2_download_size_cap_and_cancel_no_published_file(setup,tmp_path):
    from botocore.stub import Stubber
    from botocore.response import StreamingBody
    from io import BytesIO
    from contexto.respaldo import R2
    r2=R2(setup[1].config); bucket=r2.config.bucket; key='SYNTHETIC'; event=threading.Event(); event.set()
    with Stubber(r2.client) as stub:
        stub.add_response('get_object',{'ContentLength':10000,'Body':StreamingBody(BytesIO(b'x'),1)}, {'Bucket':bucket,'Key':key})
        with pytest.raises(ValueError): r2.download(key,tmp_path/'oversize',10)
        assert not (tmp_path/'oversize').exists()
        stub.add_response('get_object',{'ContentLength':1,'Body':StreamingBody(BytesIO(b'x'),1)}, {'Bucket':bucket,'Key':key})
        with pytest.raises(Cancelada): r2.download(key,tmp_path/'cancelled',10,event)
        stub.assert_no_pending_responses()


