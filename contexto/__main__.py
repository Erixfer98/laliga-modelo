"""Herramientas B1 sin capturas automáticas, LLM ni cambios de producción."""
import argparse
from pathlib import Path
from .configuracion import disponibilidad
from .contratos import canonico
from .almacen import Archivo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('estado', help='Solo presencia de configuración; nunca muestra secretos')
    verify = sub.add_parser('verificar', help='Verificar archivo existente, no crea uno nuevo')
    verify.add_argument('--db', required=True)
    backup = sub.add_parser('backup', help='Copia consistente de archivo existente')
    backup.add_argument('--db', required=True); backup.add_argument('--salida', required=True)
    args = parser.parse_args()
    if args.command == 'estado':
        print(canonico(disponibilidad()))
    else:
        path = Path(args.db)
        if not path.is_absolute() or not path.is_file():
            parser.error('Se requiere archivo existente y ruta absoluta')
        archive = Archivo(path)
        result = {'receipts_verified': len(archive.verificar()), 'provider_certified': False}
        if args.command == 'backup':
            result['backup'] = archive.backup(args.salida)
        print(canonico(result))


if __name__ == '__main__':
    main()
