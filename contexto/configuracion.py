"""Disponibilidad declarada: nunca certifica conexión o durabilidad por una variable."""
from dataclasses import dataclass
import os
from pathlib import Path
from .almacen import Archivo


@dataclass(frozen=True)
class AlmacenConfigurado:
    root: Path
    backup_root: Path
    durability_evidence: str

    def validar(self):
        for path in (self.root, self.backup_root):
            if not path.is_absolute() or not path.is_dir():
                raise ValueError('Volumen persistente/backup no disponible')
            resolved = path.resolve()
            if any(resolved == p or p in resolved.parents for p in map(Path, ('/tmp', '/workspace', '/dev/shm'))):
                raise ValueError('Ruta de ejecución efímera no admite operación prospectiva')
        a, b = self.root.resolve(), self.backup_root.resolve()
        if a == b or a in b.parents or b in a.parents or a.stat().st_dev == b.stat().st_dev:
            raise ValueError('Backup local requiere otro sistema de archivos; staging del mismo disco no es respaldo independiente')
        if not self.durability_evidence.strip():
            raise ValueError('Sin referencia verificable de provisión durable')
        # Referencia operativa, no prueba automática de durabilidad física ni certificación.
        return self

    def abrir(self):
        self.validar()
        return Archivo(self.root / 'contexto-b1.sqlite')


def disponibilidad(env=None):
    env = os.environ if env is None else env
    keys = {'api-football': 'KUOTA_API_FOOTBALL_KEY', 'sportmonks': 'KUOTA_SPORTMONKS_TOKEN'}
    providers = {p: {'credential_configured': bool(env.get(k)), 'connection_verified': False}
                 for p, k in keys.items()}
    providers['open-meteo'] = {'credential_required_noncommercial': False, 'connection_verified': False}
    values = [env.get(k, '') for k in ('KUOTA_CONTEXT_STORAGE_ROOT', 'KUOTA_CONTEXT_BACKUP_ROOT',
                                     'KUOTA_CONTEXT_DURABILITY_EVIDENCE')]
    configured = all(values); valid = False
    if configured:
        try:
            AlmacenConfigurado(Path(values[0]), Path(values[1]), values[2]).validar()
            valid = True
        except ValueError:
            pass
    return {'experimental': True, 'production_enabled': False, 'providers': providers,
            'storage': {'configured': configured, 'configuration_valid': valid,
                        'durability_verified': False, 'restore_verified': False},
            'b2_ready': False,
            'requirements': ['Acceso permitido y prueba real del proveedor por liga/temporada',
                             'Credenciales y autorización de uso/captura',
                             'Volumen persistente con backups externos y restauración verificada',
                             'Mapeos revisados con evidencia y aceptación de cobertura']}
