"""Datos y transportes SINTÉTICOS B2. IDs arbitrarios; cero llamadas a proveedores."""
import copy
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import pytest
from contexto.almacen import Archivo
from contexto.operaciones import Operaciones
from contexto.contratos import SCHEMA, ahora, canonico, utc
from contexto.conectores import Captura, NoDisponible
from contexto.cliente import Cliente, clasificar, retry_seconds
from contexto.politica import Politica, LIGAS
from contexto.descubrimiento import Descubrimiento
from contexto.evidencia_contextual import Contexto, validar_dataset
from contexto.cli_b2 import main

KEY = 'SYNTHETIC_PRIVATE_CREDENTIAL_NOT_REAL_49387'
KICK = '2099-01-02T01:00:00Z'


def capture(body, endpoint='/fixtures', captured=None, provider='api-football', remaining=None):
    raw = canonico(body).encode()
    host = 'https://v3.football.api-sports.io' if provider == 'api-football' else 'https://api.open-meteo.com'
    return Captura(raw, {'schema_version': SCHEMA, 'provider': provider, 'source_url':host + endpoint,
        'sha256':sha256(raw).hexdigest(), 'captured_at_utc':captured or ahora(), 'published_at_utc':None,
        'publication_basis':'unknown', 'content_type':'application/json'}, {} if remaining is None else {'remaining':remaining})


def row(lid=9001, fid=7001, kickoff=KICK, status='NS', season=2099, home='A', away='B'):
    return {'fixture':{'id':fid, 'date':kickoff, 'timestamp':int(utc(kickoff).timestamp()),
        'status':{'short':status}, 'venue':{'id':5001, 'name':'SYNTHETIC stadium'}},
        'league':{'id':lid, 'season':season}, 'teams':{'home':{'id':lid*10+1, 'name':home}, 'away':{'id':lid*10+2,'name':away}}}


class Fake:
    def __init__(self, replies=None): self.calls = []; self.replies = list(replies or [])
    def obtener(self, provider, endpoint, params, headers):
        self.calls.append((endpoint, copy.deepcopy(params)))
        if self.replies:
            reply = self.replies.pop(0)
            if isinstance(reply, Exception): raise reply
            return reply
        if endpoint == '/leagues':
            index = [c for c,n in LIGAS.values()].index(params['country']); lid = 9001 + index
            return capture({'errors':[], 'response':[{'league':{'id':lid, 'name':params['name'], 'type':'League'},
              'country':{'name':params['country']}, 'seasons':[{'year':2099,'coverage':{'injuries':True,'fixtures':{'lineups':True}, 'players':True}}]}]}, endpoint)
        if endpoint == '/fixtures':
            lid = params['league']; return capture({'errors':[], 'response':[row(lid, 7001+lid-9001)]}, endpoint)
        return capture({'errors':[], 'response':[]}, endpoint)


@pytest.fixture
def setup(tmp_path):
    store = Operaciones(Archivo(tmp_path/'synthetic.sqlite')); fake = Fake()
    policy = Politica(endpoints=('/status','/leagues','/fixtures','/injuries','/fixtures/lineups','/players/squads','/venues'), league_seasons={str(9001+i):[2099] for i in range(6)}, max_window_days=3)
    client = Cliente(KEY, policy, store, fake)
    folder = tmp_path/'datos'; folder.mkdir()
    for league in LIGAS: (folder/('bbdd_'+league+'.csv')).write_text('equipo_local_txt,equipo_visitante_txt\nA,B\n')
    return client, fake, Descubrimiento(client, folder), store


def discovered(setup):
    client,fake,d,store = setup
    result = d.descubrir('2099-01-02','2099-01-02',{k:2099 for k in LIGAS},dry_run=False)
    assert len(result['accepted']) == 6, result
    return store.archivo.verificar()[0]


def add_context(store, receipt, body, label, endpoint, params):
    f = receipt['fixture']
    return store.guardar(capture({'errors':[], 'response':body},endpoint), 'context',
        {'fixture_receipt_id':receipt['receipt_id'], 'fixture_version':f['version'], 'component':label, 'endpoint':endpoint,'params':params})


@pytest.mark.parametrize('endpoint,params', [('/fixtures',{}),('/fixtures',{'league':1,'season':2026}),('/injuries',{'fixture':'1'}),('/fixtures',{'id':True}),('/fixtures',{'date':'2026-10-11','token':'SECRET'}),('/leagues',{'country':'x','name':'x'}),('/fixtures',{'date':'2026-10-1'}),('/fixtures',{'league':9001,'season':2099,'from':'2099-01-01','to':'2099-02-01'})])
def test_invalid_query_rejected(setup,endpoint,params):
    c,f,d,s = setup
    assert c.consultar(endpoint,params,dry_run=False).code == 'invalid_query'
    assert not f.calls and not s.consumo()


def test_default_policy_denies_and_dry_run_no_calls(setup):
    c,f,d,s = setup
    assert Cliente(KEY,Politica(),s,f).consultar('/status',dry_run=False).code == 'endpoint_not_authorized'
    assert c.consultar('/status').status == 'planned'
    assert not f.calls and not s.records()


@pytest.mark.parametrize('field,restriction', [('season','season'),('date','date'),('endpoint','endpoint'),('subscription','subscription')])
def test_subscription_http200_persists_no_fallback(setup,field,restriction):
    c,f,d,s=setup
    f.replies=[capture({'errors':{field:'Free plan does not allow this '+field},'response':[]})]
    q={'league':9001,'season':2099,'from':'2099-01-02','to':'2099-01-02'}
    first=c.consultar('/fixtures',q,dry_run=False)
    assert (first.code,first.restriction)==('subscription_required',restriction)
    assert c.consultar('/fixtures',q,dry_run=False).status=='blocked'
    other=Cliente(KEY,Politica(endpoints=('/fixtures',),strategy='global_date',global_dates={'2099-01-02':10}),s,f)
    assert other.consultar('/fixtures',{'date':'2099-01-02'},dry_run=False).code=='subscription_required'
    assert len(f.calls)==1 and len(s.records())==1
    assert s.consumo()[0]['calls']==1


def test_daily_reserve_persists_after_restart(setup):
    c,f,d,s=setup
    c.policy=Politica(daily_limit=3,reserve=1,cache_seconds=0,endpoints=('/status',))
    assert c.consultar('/status',dry_run=False).status=='ok'
    assert c.consultar('/status',dry_run=False).status=='ok'
    fresh=Cliente(KEY,c.policy,Operaciones(Archivo(s.archivo.path)),f)
    assert fresh.consultar('/status',dry_run=False).code=='daily_budget_exhausted'
    assert fresh.consultar('/status',purpose='verification',dry_run=False).status=='ok'
    assert fresh.consultar('/status',purpose='verification',dry_run=False).code=='daily_budget_exhausted'
    assert len(f.calls)==3


def test_provider_remaining_and_json_daily_quota(setup):
    c,f,d,s=setup
    f.replies=[capture({'errors':[], 'response':[]},'/status',remaining=0)]
    assert c.consultar('/status',dry_run=False).status=='ok'
    assert c.consultar('/leagues',{'country':'Spain','name':'La Liga'},dry_run=False).code=='daily_budget_exhausted'
    assert clasificar({'requests':'daily request limit reached'})==('quota_exhausted','day')


def test_429_retry_after_no_extra_requests(setup):
    c,f,d,s=setup; f.replies=[NoDisponible('unsafe token '+KEY,429,'120')]
    assert c.consultar('/status',dry_run=False).code=='rate_limited'
    assert c.consultar('/status',dry_run=False).code=='rate_limited'
    assert len(f.calls)==1 and KEY not in canonico(s.consumo())
    assert retry_seconds('120')==120 and retry_seconds('invalid')==60


def test_only_transient_retries(setup,monkeypatch):
    c,f,d,s=setup; monkeypatch.setattr('contexto.cliente.time.sleep',lambda x:None)
    f.replies=[NoDisponible('SYNTHETIC',503),capture({'errors':[],'response':[]},'/status')]
    assert c.consultar('/status',dry_run=False).status=='ok'
    assert len(f.calls)==2 and {x['purpose'] for x in s.consumo()}=={'discovery','retry'}


@pytest.mark.parametrize('status,code',[(401,'credentials_invalid'),(403,'access_denied'),(404,'http_error')])
def test_nontransient_no_retry(setup,status,code):
    c,f,d,s=setup; f.replies=[NoDisponible(KEY,status)]
    assert c.consultar('/status',dry_run=False).code==code and len(f.calls)==1


def test_cache_concurrency_original_capture(setup):
    c,f,d,s=setup
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:c.consultar('/status',dry_run=False),range(8)))
    assert len(f.calls)==1 and sum(r.cached for r in results)==7
    assert len({r.capture.metadata['captured_at_utc'] for r in results})==1
    assert s.verificar()=={'fixtures':0,'captures':1}


def test_cancel_before_and_after_transport(setup):
    c,f,d,s=setup; e=threading.Event(); e.set()
    assert c.consultar('/status',dry_run=False,cancel=e).status=='cancelled' and not f.calls
    e.clear(); original=f.obtener
    def cancel(*a,**kw):
        cap=original(*a,**kw); e.set(); return cap
    f.obtener=cancel
    assert c.consultar('/status',dry_run=False,cancel=e).status=='cancelled'
    assert len(f.calls)==1 and sum(x['calls'] for x in s.consumo())==1


def test_credentials_echo_never_archived(setup):
    c,f,d,s=setup; f.replies=[capture({'errors':[], 'response':[{'secret':KEY}]},'/status')]
    assert c.consultar('/status',dry_run=False).code=='credential_echo_rejected'
    assert not s.records() and KEY.encode() not in s.archivo.path.read_bytes()


def test_six_catalog_ids_bulk_dedup_idempotence_backup(setup,tmp_path):
    c,f,d,s=setup
    rec=discovered(setup)
    assert {r['fixture']['league_id'] for r in s.archivo.verificar()}=={str(9001+i) for i in range(6)}
    n=len(f.calls); result=d.descubrir('2099-01-02','2099-01-02',{k:2099 for k in LIGAS},dry_run=False)
    assert len(result['accepted'])==6 and len(f.calls)==n and len(s.archivo.verificar())==6
    assert d.inventario(ahora(),page_size=2)['pages']==3
    backup=tmp_path/'restore.sqlite'; s.backup(backup)
    assert Operaciones(Archivo(backup)).verificar()==s.verificar()
    assert KEY.encode() not in backup.read_bytes()


@pytest.mark.parametrize('variant',['duplicate','conflict','finished','cancelled','wrong_date','wrong_season','unmapped','ambiguous'])
def test_discovery_quarantines_and_excludes_future(setup,variant):
    c,f,d,s=setup
    leagues,states=d.catalogo(dry_run=False)
    r=row(); rows=[r]
    if variant=='duplicate': rows.append(copy.deepcopy(r))
    if variant=='conflict': other=copy.deepcopy(r); other['fixture']['status']['short']='FT'; rows.append(other)
    if variant=='finished': r['fixture']['status']['short']='FT'
    if variant=='cancelled': r['fixture']['status']['short']='CANC'
    if variant=='wrong_date': r['fixture']['date']='2099-01-03T01:00:00Z'
    if variant=='wrong_season': r['league']['season']=2098
    if variant=='unmapped': r['teams']['home']['name']='Unknown team'
    if variant=='ambiguous': (d.folder/'bbdd_laliga.csv').write_text('equipo_local_txt,equipo_visitante_txt\nA,B\na,B\n')
    f.replies=[capture({'errors':[], 'response':rows})]
    result=d.descubrir('2099-01-02','2099-01-02',{k:2099 for k in LIGAS},dry_run=False)
    accepted=[x for x in result['accepted'] if x['fixture_id']=='7001']
    if variant=='duplicate': assert len(accepted)==1 and len(s.archivo.verificar()[0]['evidence'])>0
    elif variant in ('finished','cancelled'):
        assert len(accepted)==1 and not accepted[0]['eligible_future']
        assert all(x['fixture_id']!='7001' for x in d.inventario(ahora())['fixtures'])
    else: assert not accepted and result['rejected']


def test_schedule_version_then_cancellation(setup):
    c,f,d,s=setup; rec=discovered(setup); oldversion=rec['fixture']['version']
    c.policy=Politica(endpoints=('/fixtures','/leagues'),cache_seconds=0,league_seasons={str(9001+i):[2099] for i in range(6)})
    # Expire request cache so updated fixture uses a fresh real-equivalent capture.
    with s.archivo._db() as db: db.execute('DELETE FROM request_cache WHERE fingerprint NOT IN (SELECT fingerprint FROM api_calls WHERE endpoint="/leagues")')
    f.replies=[capture({'errors':[],'response':[row(kickoff='2099-01-02T02:00:00Z')]})]
    result=d.descubrir('2099-01-02','2099-01-02',{k:2099 for k in LIGAS},dry_run=False)
    assert result['accepted'][0]['version']!=oldversion
    assert len([r for r in s.archivo.verificar() if r['fixture']['fixture_id']=='7001'])==2
    f.replies=[capture({'errors':[],'response':[row(status='CANC')]})]
    d.descubrir('2099-01-02','2099-01-02',{k:2099 for k in LIGAS},dry_run=False)
    assert not any(r['fixture_id']=='7001' for r in d.inventario(ahora())['fixtures'])


def test_malformed_catalog_fails_closed(setup):
    c,f,d,s=setup; f.replies=[capture({'errors':[],'response':[{'league':None,'country':None}]},'/leagues')]
    leagues,states=d.catalogo(dry_run=False)
    assert 'laliga' not in leagues and states['laliga']['code']=='catalog_contract_invalid'


def test_global_date_only_explicit_efficient_filter(setup):
    c,f,d,s=setup; d.catalogo(dry_run=False)
    c.policy=Politica(endpoints=('/fixtures','/leagues'),strategy='global_date',global_dates={'2099-01-02':7})
    f.replies=[capture({'errors':[],'response':[row(),row(lid=9999,fid=8888)]})]
    result=d.descubrir('2099-01-02','2099-01-02',{},dry_run=False)
    assert len(result['accepted'])==1
    assert c.consultar('/fixtures',{'date':'2099-01-03'},dry_run=False).code=='date_permission_unverified'


def test_unknown_context_no_calls(setup):
    c,f,d,s=setup; rec=discovered(setup); n=len(f.calls)
    result=Contexto(c).capturar(rec,{},dry_run=False)
    assert all(v['status']=='unknown' for v in result['components'].values()) and len(f.calls)==n
    ds=Contexto(c).dataset(rec,ahora())
    assert not ds['facts'] and 'injuries' in ds['unknown_fields'] and ds['calendar']['home']['calendar_complete'] is False


def test_context_contradictions_partial_lineups_and_asof(setup):
    c,f,d,s=setup; rec=discovered(setup); team=rec['fixture']['home']['provider_team_id']; cutoff_before=ahora()
    injury=add_context(s,rec,[{'fixture':{'id':7001},'team':{'id':int(team)},'player':{'id':123,'type':'Missing Fixture','reason':'SYNTHETIC injury'}}], 'injuries','/injuries',{'fixture':7001})
    add_context(s,rec,[{'team':{'id':int(team)},'startXI':[{'player':{'id':123}}]}], 'confirmed_lineups','/fixtures/lineups',{'fixture':7001})
    ctx=Contexto(c); ds=ctx.dataset(rec,ahora()); validar_dataset(ds)
    assert len(ds['contradictions'])==1 and 'confirmed_lineups' in ds['unknown_fields']
    assert not ctx.dataset(rec,cutoff_before)['facts']
    corrupted=copy.deepcopy(ds); corrupted['sources'][0]['registered_at_utc']=KICK
    with pytest.raises(ValueError): validar_dataset(corrupted)
    corrupted=copy.deepcopy(ds); corrupted['facts'][0]['certainty']='officially_confirmed'
    with pytest.raises(ValueError): validar_dataset(corrupted)


def test_wrong_context_identity_empty_missing_stays_unknown(setup):
    c,f,d,s=setup; rec=discovered(setup)
    add_context(s,rec,[{'fixture':{'id':999},'team':{'id':90011},'player':{'id':1,'type':'x','reason':'x'}}],'injuries','/injuries',{'fixture':7001})
    ds=Contexto(c).dataset(rec,ahora())
    assert not ds['facts'] and ds['validation_errors'] and 'injuries' in ds['unknown_fields']


def test_postkick_capture_abstains_and_cannot_backdate(setup):
    c,f,d,s=setup; d.catalogo(dry_run=False)
    f.replies=[capture({'errors':[], 'response':[row(kickoff='2001-01-02T01:00:00Z')]})]
    d.descubrir('2001-01-02','2001-01-02',{k:2099 for k in LIGAS},dry_run=False)
    rec=s.archivo.verificar()[0]
    assert Contexto(c).capturar(rec,{},dry_run=False)['status']=='abstained'
    with pytest.raises(ValueError): Contexto(c).dataset(rec,'2000-01-01T00:00:00Z')


def test_archive_tamper_and_crash_reservation(setup):
    c,f,d,s=setup; c.consultar('/status',dry_run=False)
    assert s.reservar('/status','a'*64,'verification',100,10) is not None
    assert any(x['status']=='reserved' for x in Operaciones(Archivo(s.archivo.path)).consumo())
    with s.archivo._db() as db:
        db.execute('DROP TRIGGER context_no_update'); db.execute("UPDATE context_records SET body='{}'")
    with pytest.raises(ValueError): s.verificar()


def test_cli_dryrun_no_db_or_credentials(tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('KUOTA_API_FOOTBALL_KEY',KEY)
    dest=tmp_path/'not-created.sqlite'
    main(['--db',str(dest),'descubrir','--desde','2026-10-11','--hasta','2026-10-12'])
    assert not dest.exists() and KEY not in capsys.readouterr().out
    with pytest.raises(SystemExit) as e: main(['--db',str(dest),'--execute','conectividad'])
    assert e.value.code==2 and not dest.exists()


def test_isolation_production_imports():
    root=Path(__file__).parents[1]
    for path in ('api.py','modelo.py','probabilidades.py','kuota.py','cache_analisis.py','experimentos/registro.py'):
        assert 'from contexto' not in (root/path).read_text()


def test_cross_fixture_team_identity_conflict(setup):
    c,f,d,s=setup; discovered(setup)
    c.policy=Politica(endpoints=('/leagues','/fixtures'),cache_seconds=0,league_seasons={str(9001+i):[2099] for i in range(6)})
    with s.archivo._db() as db: db.execute('DELETE FROM request_cache WHERE fingerprint IN (SELECT fingerprint FROM api_calls WHERE endpoint="/fixtures")')
    wrong=row(fid=7010,home='B',away='A')
    f.replies=[capture({'errors':[],'response':[wrong]})]
    result=d.descubrir('2099-01-02','2099-01-02',{k:2099 for k in LIGAS},dry_run=False)
    assert any(r['fixture_id']=='7010' for r in result['rejected'])
    assert not any(r['fixture']['fixture_id']=='7010' for r in s.archivo.verificar())


def test_stale_fixture_cannot_create_current_context(setup):
    c,f,d,s=setup; rec=discovered(setup); oldcutoff=ahora()
    c.policy=Politica(endpoints=('/leagues','/fixtures'),cache_seconds=0,league_seasons={str(9001+i):[2099] for i in range(6)})
    with s.archivo._db() as db: db.execute('DELETE FROM request_cache WHERE fingerprint IN (SELECT fingerprint FROM api_calls WHERE endpoint="/fixtures")')
    f.replies=[capture({'errors':[],'response':[row(status='CANC')]})]
    d.descubrir('2099-01-02','2099-01-02',{k:2099 for k in LIGAS},dry_run=False)
    assert Contexto(c).dataset(rec,oldcutoff)['facts']==[]
    with pytest.raises(ValueError): Contexto(c).dataset(rec,ahora())
    with pytest.raises(ValueError): Contexto(c).capturar(rec,{},dry_run=False)


def test_future_data_perturbation_keeps_asof_identical(setup):
    c,f,d,s=setup; rec=discovered(setup); cutoff=ahora()
    first=Contexto(c).dataset(rec,cutoff)
    add_context(s,rec,[{'fixture':{'id':7001},'team':{'id':90011},'player':{'id':123,'type':'Missing Fixture','reason':'Future perturbation'}}],'injuries','/injuries',{'fixture':7001})
    second=Contexto(c).dataset(rec,cutoff)
    first.pop('generated_at_utc'); second.pop('generated_at_utc')
    assert first==second


@pytest.mark.parametrize('bad',['units','time','coordinates'])
def test_weather_invalid_or_unverified_remains_unknown(setup,bad):
    c,f,d,s=setup; rec=discovered(setup)
    venue=s.guardar(capture({'errors':[], 'response':[{'id':5001,'latitude':10.,'longitude':20.}]},'/venues'),'request',{'endpoint':'/venues','params':{'id':5001},'validation_state':'ok'})
    body={'timezone':'UTC','utc_offset_seconds':0,'hourly_units':{'temperature_2m':'°C','precipitation':'mm','wind_speed_10m':'km/h'},'hourly':{'time':['2099-01-02T01:00'],'temperature_2m':[20.],'precipitation':[0.],'wind_speed_10m':[10.]}}
    if bad=='units': body['hourly_units']['wind_speed_10m']='m/s'
    if bad=='time': body['hourly']['time']=['2099-01-01T01:00']
    scope={'fixture_version':rec['fixture']['version'],'fixture_receipt_id':rec['receipt_id'],'component':'weather','venue_record_id':venue['id'],'latitude':10.,'longitude':20.}
    if bad=='coordinates': scope['latitude']=11.
    s.guardar(capture(body,'/v1/forecast',provider='open-meteo'),'weather',scope)
    ds=Contexto(c).dataset(rec,ahora())
    assert 'weather' in ds['unknown_fields'] and not ds['facts'] and ds['validation_errors']


def test_weather_verified_units_source_and_dedup(setup):
    c,f,d,s=setup; rec=discovered(setup)
    s.guardar(capture({'errors':[], 'response':[{'id':5001,'latitude':10.,'longitude':20.}]},'/venues'),'request',{'endpoint':'/venues','params':{'id':5001},'validation_state':'ok'})
    class Weather:
        calls=0
        def obtener_pronostico(self,lat,lon,kick):
            self.calls+=1
            assert (lat,lon,kick)==(10.,20.,KICK)
            return capture({'timezone':'UTC','utc_offset_seconds':0,'hourly_units':{'temperature_2m':'°C','precipitation':'mm','wind_speed_10m':'km/h'},'hourly':{'time':['2099-01-02T01:00'],'temperature_2m':[20.],'precipitation':[0.],'wind_speed_10m':[10.]}},'/v1/forecast',provider='open-meteo')
    w=Weather(); ctx=Contexto(c,w)
    ctx.capturar(rec,{},dry_run=False,weather_authorized=True)
    ctx.capturar(rec,{},dry_run=False,weather_authorized=True)
    assert w.calls==1
    ds=ctx.dataset(rec,ahora()); assert ds['facts'][0]['certainty']=='forecast' and 'weather' not in ds['unknown_fields']


def test_batch_bad_row_does_not_hide_good_fixture(setup):
    c,f,d,s=setup; d.catalogo(dry_run=False)
    f.replies=[capture({'errors':[],'response':[{'invalid':'SYNTHETIC'},row()]})]
    result=d.descubrir('2099-01-02','2099-01-02',{k:2099 for k in LIGAS},dry_run=False)
    assert any(x['fixture_id']=='7001' for x in result['accepted']) and result['rejected']


def test_oversized_global_and_provider_paging_stop(setup):
    c,f,d,s=setup; d.catalogo(dry_run=False)
    c.policy=Politica(endpoints=('/fixtures','/leagues'),strategy='global_date',global_dates={'2099-01-02':2},max_global_results=2)
    f.replies=[capture({'errors':[],'response':[row(),row(),row()]})]
    result=d.descubrir('2099-01-02','2099-01-02',{},dry_run=False)
    assert not result['accepted'] and result['rejected'][0]['code']=='query_volume_or_pagination_not_supported'


def test_prospective_archive_cannot_receive_future_capture(setup):
    c,f,d,s=setup
    with pytest.raises(ValueError): s.guardar(capture({'errors':[],'response':[]},captured=KICK),'request',{})
    assert not s.records()


def test_no_alternative_fixture_id_after_subscription_denial(setup):
    c,f,d,s=setup
    f.replies=[capture({'errors':{'season':'Free plan access to this season is denied'},'response':[]})]
    c.consultar('/fixtures',{'league':9001,'season':2099,'from':'2099-01-02','to':'2099-01-02'},dry_run=False)
    assert c.consultar('/fixtures',{'id':7001},dry_run=False).status=='blocked'
    assert len(f.calls)==1


def test_explicit_backup_dry_run_does_not_open_or_write(tmp_path,capsys):
    db=tmp_path/'absent.sqlite'; target=tmp_path/'backup.sqlite'
    main(['--db',str(db),'--dry-run','backup','--salida',str(target)])
    assert not db.exists() and not target.exists() and json.loads(capsys.readouterr().out)['storage_opened'] is False


def test_context_capture_uses_shared_budget_and_real_receipts(setup):
    c,f,d,s=setup; rec=discovered(setup)
    report=Contexto(c).capturar(rec,{'injuries':True,'fixtures':{'lineups':True},'players':True},dry_run=False)
    assert len([r for r in s.records() if r['kind']=='context'])==4
    assert all(report['components'][k]['eligible_prekick'] for k in ('injuries','confirmed_lineups','squads_home','squads_away'))
    ds=Contexto(c).dataset(rec,ahora())
    assert not ds['facts'] and 'injuries' in ds['unknown_fields'] and len(ds['sources'])==4


def test_source_captured_before_but_registered_after_cutoff_excluded(setup):
    c,f,d,s=setup; rec=discovered(setup); cutoff=ahora()
    # Original declaration older than cutoff does not undo actual later registration.
    cap=capture({'errors':[],'response':[{'fixture':{'id':7001},'team':{'id':90011},'player':{'id':123,'type':'Missing Fixture','reason':'SYNTHETIC'}}]},'/injuries',captured='2026-01-01T00:00:00Z')
    s.guardar(cap,'context',{'fixture_receipt_id':rec['receipt_id'],'fixture_version':rec['fixture']['version'],'component':'injuries','endpoint':'/injuries','params':{'fixture':7001}})
    assert Contexto(c).dataset(rec,cutoff)['facts']==[]
    assert len(Contexto(c).dataset(rec,ahora())['facts'])==1


def test_cancel_weather_inflight_does_not_publish(setup):
    c,f,d,s=setup; rec=discovered(setup); event=threading.Event()
    s.guardar(capture({'errors':[], 'response':[{'id':5001,'latitude':10.,'longitude':20.}]},'/venues'),'request',{'endpoint':'/venues','params':{'id':5001},'validation_state':'ok'})
    class Weather:
        def obtener_pronostico(self,*args):
            event.set(); return capture({'SYNTHETIC':'cancelled'},'/v1/forecast',provider='open-meteo')
    report=Contexto(c,Weather()).capturar(rec,{},dry_run=False,cancel=event,weather_authorized=True)
    assert report['components']['weather']['status']=='cancelled'
    assert not any(r['kind']=='weather' for r in s.records())
    assert s.control('weather_calls:'+ahora()[:10])==1


def test_ai_dataset_contains_verified_fixture_and_rejects_foreign_facts(setup):
    c,f,d,s=setup; rec=discovered(setup)
    add_context(s,rec,[{'fixture':{'id':7001},'team':{'id':90011},'player':{'id':123,'type':'Missing Fixture','reason':'SYNTHETIC'}}],'injuries','/injuries',{'fixture':7001})
    ds=Contexto(c).dataset(rec,ahora())
    assert ds['fixture']['home']['internal_team']=='A' and ds['fixture']['fixture_id']=='7001'
    assert ds['fixture_registered_at_utc']==rec['registered_at_utc']
    bad=copy.deepcopy(ds); bad['facts'][0]['value']['team_id']='999999'
    with pytest.raises(ValueError): validar_dataset(bad)
    bad=copy.deepcopy(ds); bad['fixture_registered_at_utc']=KICK
    with pytest.raises(ValueError): validar_dataset(bad)
