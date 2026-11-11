"""Piloto SINTÉTICO; nunca utiliza transporte real ni credenciales."""
import runpy,tempfile,time,tracemalloc,json,sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
m=runpy.run_path(str(ROOT/'tests/test_contexto_b2.py'))
Fake, row, capture = m['Fake'],m['row'],m['capture']
from contexto.almacen import Archivo
from contexto.operaciones import Operaciones
from contexto.cliente import Cliente
from contexto.politica import Politica,LIGAS
from contexto.descubrimiento import Descubrimiento
class Batch(Fake):
    def obtener(self,provider,endpoint,params,headers):
        if endpoint=='/fixtures':
            self.calls.append((endpoint,params)); lid=params['league']
            return capture({'errors':[],'response':[row(lid,70000+(lid-9001)*10+i) for i in range(10)]},endpoint)
        return super().obtener(provider,endpoint,params,headers)
with tempfile.TemporaryDirectory() as tmp:
    folder=Path(tmp)
    for league in LIGAS: (folder/('bbdd_'+league+'.csv')).write_text('equipo_local_txt,equipo_visitante_txt\nA,B\n')
    store=Operaciones(Archivo(folder/'synthetic.sqlite')); fake=Batch()
    client=Cliente('SYNTHETIC_PRIVATE_CREDENTIAL_NOT_REAL_49387',Politica(endpoints=('/leagues','/fixtures'),league_seasons={str(9001+i):[2099] for i in range(6)}),store,fake)
    d=Descubrimiento(client,folder); tracemalloc.start(); times=[]; counts=[]
    for _ in range(2):
        start=time.perf_counter(); before=len(fake.calls)
        result=d.descubrir('2099-01-02','2099-01-02',{k:2099 for k in LIGAS},dry_run=False)
        times.append(time.perf_counter()-start); counts.append(len(fake.calls)-before)
        assert len(result['accepted'])==60 and not result['rejected']
    _,peak=tracemalloc.get_traced_memory()
    print(json.dumps({'synthetic':True,'real_provider_calls':0,'fixtures':60,'leagues':6,'discovery_seconds':times[0],'cached_rerun_seconds':times[1],'mock_requests':counts,'peak_python_mib':peak/1024**2,'sqlite_bytes':store.archivo.path.stat().st_size,'verified':store.verificar()},indent=2))
