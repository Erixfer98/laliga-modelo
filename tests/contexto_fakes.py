"""Objetos y archivo SINTÉTICOS compartidos, sin red o credenciales reales."""
from pathlib import Path
import pytest
from contexto.almacen import Archivo
from contexto.operaciones import Operaciones
from contexto.respaldo import R2Config, Respaldos
from test_contexto_b1 import muestra, PROOF
SECRET='SYNTHETIC_PRIVATE_SECRET_NOT_REAL_298347'

class Remote:
    def __init__(self): self.data={}; self.calls=[]; self.fail=False
    def upload(self,path,key,cancel=None):
        self.calls.append(('upload',key))
        if self.fail: raise RuntimeError('unsafe '+SECRET)
        self.data[key]=Path(path).read_bytes()
    def download(self,key,path,max_bytes,cancel=None):
        self.calls.append(('download',key))
        raw=self.data[key]
        if not 0<len(raw)<=max_bytes: raise ValueError('invalid')
        with open(path,'xb') as f: f.write(raw)
    def objects(self): return list(self.data)
    def delete(self,key): self.calls.append(('delete',key)); self.data.pop(key,None)


@pytest.fixture
def setup(tmp_path):
    store=Operaciones(Archivo(tmp_path/'archive.sqlite'))
    cap,maps=muestra(); store.archivo.agregar_fixture(cap,'123',maps,[PROOF])
    staging=tmp_path/'staging'; staging.mkdir()
    cfg=R2Config('https://'+'a'*32+'.r2.cloudflarestorage.com','synthetic-private',SECRET,SECRET)
    remote=Remote(); backups=Respaldos(store,staging,cfg,remote)
    return store,backups,remote


