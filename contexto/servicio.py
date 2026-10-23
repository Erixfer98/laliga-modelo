"""Ciclo B2 reusable por worker/CLI; no consulta al importar y no escribe logs de evidencia."""
from .descubrimiento import Descubrimiento
from .evidencia_contextual import Contexto
from .contratos import ahora
from .politica import LIGAS, nombre


def ciclo(client, start, end, seasons, weather_authorized=False, cancel=None):
    discovery = Descubrimiento(client); context = Contexto(client); store = client.store
    result = discovery.descubrir(start, end, seasons, dry_run=False, cancel=cancel)
    catalog = {}
    # Usar únicamente recibos del catálogo aceptado EN ESTE descubrimiento;
    # capturas HTTP 200 cuyo catálogo fue rechazado no aportan cobertura.
    for internal, state in result['catalog'].items():
        if internal not in LIGAS or state.get('status') != 'ok': continue
        cap, _ = store.captura(state['record_id'])
        country, names = LIGAS[internal]
        candidates = []
        for row in cap.json()['response']:
            if not isinstance(row, dict) or not isinstance(row.get('country'), dict) or not isinstance(row.get('league'), dict): continue
            c, n = row['country'].get('name'), row['league'].get('name')
            if isinstance(c,str) and isinstance(n,str) and nombre(c)==nombre(country) and nombre(n) in {nombre(x) for x in names} and row['league'].get('type')=='League': candidates.append(row)
        if len(candidates)==1: catalog[internal]=candidates[0]
    by_id = {r['receipt_id']:r for r in store.archivo.verificar()}; result['context'] = []
    for selected in result['accepted']:
        if cancel and cancel.is_set(): break
        if not selected['eligible_future']: continue
        receipt = by_id[selected['receipt_id']]; f = receipt['fixture']
        coverage = next((s.get('coverage', {}) for s in catalog.get(f['internal_league'], {}).get('seasons', []) if str(s['year']) == f['season_id']), {})
        captured = context.capturar(receipt, coverage, dry_run=False, cancel=cancel, weather_authorized=weather_authorized)
        captured['fixture_receipt_id'] = receipt['receipt_id']
        try: captured['dataset'] = context.dataset(receipt, ahora())
        except ValueError: captured['dataset_status'] = 'abstained'
        result['context'].append(captured)
    return result
