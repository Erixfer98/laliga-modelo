"""Cliente B2 aislado; respuestas SINTÉTICAS, sin conexiones reales."""
from hashlib import sha256
import pytest
from contexto.almacen import Archivo
from contexto.operaciones import Operaciones
from contexto.politica import Politica
from contexto.cliente import Cliente
from contexto.conectores import Captura
from contexto.contratos import SCHEMA, ahora, canonico


@pytest.mark.parametrize('errors,expected', [([], 'ok'), ({'season':'Free plan access to this season denied'},'subscription_required'), ({'date':'Free plan date unavailable'},'subscription_required'), ({'requests':'daily quota limit'},'quota_exhausted')])
def test_archived_json_error_and_budget(tmp_path,errors,expected):
    store=Operaciones(Archivo(tmp_path/'synthetic.sqlite'))
    class Synthetic:
        def obtener(self,provider,endpoint,params,headers):
            raw=canonico({'errors':errors,'response':[]}).encode()
            return Captura(raw,{'schema_version':SCHEMA,'provider':provider,'source_url':'https://v3.football.api-sports.io'+endpoint,'sha256':sha256(raw).hexdigest(),'captured_at_utc':ahora(),'published_at_utc':None,'publication_basis':'unknown','content_type':'application/json'})
    client=Cliente('SYNTHETIC_NOT_A_REAL_KEY',Politica(endpoints=('/status',)),store,Synthetic())
    assert client.consultar('/status',dry_run=False).code==expected
    assert store.verificar()=={'fixtures':0,'captures':1}
    assert sum(x['calls'] for x in store.consumo())==1


@pytest.mark.parametrize('field,value', [('reserve',100),('daily_limit',True),('max_retries',3),('strategy','fallback')])
def test_invalid_policy_fails_closed(field,value):
    with pytest.raises(ValueError): Politica(**{field:value})
