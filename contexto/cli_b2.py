"""Operación experimental optativa; ningún scheduler o ruta de producción importa este CLI."""
import argparse
import json
import os
from pathlib import Path
from .almacen import Archivo
from .operaciones import Operaciones
from .configuracion import disponibilidad, AlmacenConfigurado
from .politica import Politica, LIGAS
from .cliente import Cliente
from .descubrimiento import Descubrimiento
from .evidencia_contextual import Contexto
from .contratos import ahora, canonico


def configuracion(path):
    obj = json.loads(Path(path).read_text())
    from .contratos import campos
    campos(obj, ('policy', 'seasons', 'live_authorized', 'credential_rotated', 'network_authorized', 'restore_verified', 'weather_authorized'))
    for k in ('live_authorized', 'credential_rotated', 'network_authorized', 'restore_verified', 'weather_authorized'):
        if type(obj[k]) is not bool: raise ValueError('Autorización inválida')
    if not isinstance(obj['seasons'], dict) or not set(obj['seasons']) <= set(LIGAS) or any(type(s) is not int or not 2000 <= s <= 2100 for s in obj['seasons'].values()):
        raise ValueError('Temporadas inválidas')
    return obj, Politica.cargar(obj['policy'])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config'); p.add_argument('--db'); group = p.add_mutually_exclusive_group()
    group.add_argument('--dry-run', action='store_true', help='Modo predeterminado, sin llamadas ni archivos nuevos')
    group.add_argument('--execute', action='store_true', help='Autoriza esta ejecución, requiere configuración operativa adicional')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('estado'); sub.add_parser('conectividad'); sub.add_parser('catalogo'); sub.add_parser('consumo')
    for name in ('descubrir', 'ciclo'):
        cmd = sub.add_parser(name); cmd.add_argument('--desde', required=True); cmd.add_argument('--hasta', required=True)
    inv = sub.add_parser('inventario'); inv.add_argument('--cutoff'); inv.add_argument('--page', type=int, default=1); inv.add_argument('--page-size', type=int, default=25); inv.add_argument('--all-statuses', action='store_true')
    for name in ('evidencia', 'contexto', 'dataset'):
        cmd = sub.add_parser(name); cmd.add_argument('--id', required=True); cmd.add_argument('--cutoff')
    sub.add_parser('verificar'); backup = sub.add_parser('backup'); backup.add_argument('--salida', required=True)
    args = p.parse_args(argv)
    try:
        if args.command == 'estado':
            print(canonico(disponibilidad())); return
        if not args.db or not Path(args.db).is_absolute(): raise ValueError('Se requiere --db absoluto')
        network = args.command in ('conectividad', 'catalogo', 'descubrir', 'contexto', 'ciclo')
        config, policy = configuracion(args.config) if args.config else (None, Politica())
        if network and args.execute:
            if not config or not all(config[k] for k in ('live_authorized', 'credential_rotated', 'network_authorized', 'restore_verified')):
                raise ValueError('Operación real bloqueada: autorización, rotación, red o restauración pendientes')
            store_config = AlmacenConfigurado(Path(os.environ.get('KUOTA_CONTEXT_STORAGE_ROOT', '')), Path(os.environ.get('KUOTA_CONTEXT_BACKUP_ROOT', '')), os.environ.get('KUOTA_CONTEXT_DURABILITY_EVIDENCE', '')).validar()
            if Path(args.db).resolve().parent != store_config.root.resolve(): raise ValueError('Archivo fuera del volumen autorizado')
            if not os.environ.get('KUOTA_API_FOOTBALL_KEY'): raise ValueError('Credencial backend ausente')
        if network and not args.execute:
            # Plan sin abrir/crear el archivo y sin leer credenciales.
            result = {'dry_run': True, 'strategy': policy.strategy, 'endpoints': list(policy.endpoints), 'catalog_selectors': {k:{'country':v[0], 'name':v[1][0], 'id_verified':False} for k,v in LIGAS.items()}, 'requires_execute_and_operational_gates': True}
            if args.command in ('descubrir', 'ciclo'): result['dates'] = policy.ventana(args.desde, args.hasta)
            print(canonico(result)); return
        if args.dry_run:
            print(canonico({'dry_run': True, 'command': args.command, 'network_requests': 0, 'storage_opened': False})); return
        if not Path(args.db).is_file() and not (network and args.execute): raise ValueError('Archivo existente requerido')
        store = Operaciones(Archivo(args.db)); client = Cliente(os.environ.get('KUOTA_API_FOOTBALL_KEY') if network else None, policy, store)
        discovery = Descubrimiento(client); context = Contexto(client)
        if args.command == 'conectividad': result = client.consultar('/status', purpose='verification', dry_run=False).publico()
        elif args.command == 'catalogo':
            leagues, states = discovery.catalogo(dry_run=False); result = {'leagues': leagues, 'states': states}
        elif args.command in ('descubrir', 'ciclo'):
            result = discovery.descubrir(args.desde, args.hasta, config['seasons'], dry_run=False)
            if args.command == 'ciclo':
                # Reutiliza catálogo archivado; no repite seis consultas para obtener cobertura.
                leagues = {}
                for record in store.records():
                    if record['scope'].get('endpoint') != '/leagues' or record['scope'].get('validation_state') != 'ok': continue
                    cap, _ = store.captura(record['id'])
                    for row in cap.json()['response']:
                        if isinstance(row, dict) and 'league' in row: leagues[str(row['league']['id'])] = row
                by_id = {r['receipt_id']: r for r in store.archivo.verificar()}; result['context'] = []
                for selected in result['accepted']:
                    if not selected['eligible_future']: continue
                    receipt = by_id[selected['receipt_id']]; f = receipt['fixture']
                    seasons = leagues.get(f['league_id'], {}).get('seasons', [])
                    coverage = next((s.get('coverage', {}) for s in seasons if str(s['year']) == f['season_id']), {})
                    captured = context.capturar(receipt, coverage, dry_run=False, weather_authorized=config['weather_authorized'])
                    captured['fixture_receipt_id'] = receipt['receipt_id']
                    try: captured['dataset'] = context.dataset(receipt, ahora())
                    except ValueError: captured['dataset_status'] = 'abstained'
                    result['context'].append(captured)
        elif args.command == 'inventario': result = discovery.inventario(args.cutoff or ahora(), args.page, args.page_size, not args.all_statuses)
        elif args.command == 'consumo': result = {'calls': store.consumo(), 'weather_calls_today': store.control('weather_calls:' + ahora()[:10]) or 0}
        elif args.command == 'verificar': result = store.verificar()
        elif args.command == 'backup': result = store.backup(args.salida)
        elif args.command == 'evidencia':
            # Privado: evidencia bruta solo en el backend/archivo, nunca respuesta pública.
            cap, receipt = store.captura(args.id); result = {'receipt':receipt, 'snapshot':cap.json()}
        else:
            receipt = next((r for r in store.archivo.verificar() if r['receipt_id'] == args.id), None)
            if receipt is None: raise ValueError('Receipt desconocido')
            if args.command == 'dataset': result = context.dataset(receipt, args.cutoff or ahora())
            else:
                coverage = {}
                for record in store.records():
                    if record['scope'].get('endpoint') != '/leagues' or record['scope'].get('validation_state') != 'ok': continue
                    cap, _ = store.captura(record['id'])
                    for league in cap.json()['response']:
                        if str(league['league']['id']) == receipt['fixture']['league_id']:
                            coverage = next((s.get('coverage', {}) for s in league['seasons'] if str(s['year']) == receipt['fixture']['season_id']), {})
                result = context.capturar(receipt, coverage, dry_run=False, weather_authorized=config['weather_authorized'])
        print(canonico(result))
    except (ValueError, KeyError, OSError, TypeError):
        # No propagar rutas, configuración cruda, tokens o mensajes del proveedor.
        p.exit(2, 'Configuración o evidencia inválida; operación bloqueada. Consulte la guía B2.\n')


if __name__ == '__main__': main()
