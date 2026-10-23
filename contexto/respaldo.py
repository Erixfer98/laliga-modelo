"""Backups SQLite consistentes y round-trip S3/R2 privado. Ninguna conexión al importar."""
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import tempfile
import sqlite3
from contextlib import closing
import uuid
from .almacen import Archivo, APPLICATION_ID
from .operaciones import Operaciones, Cancelada
from .contratos import ahora, canonico, campos, digest, utc


class RespaldoBloqueado(RuntimeError):
    """Solo códigos internos: nunca propagar errores SDK con tokens/URLs firmadas."""


def hash_file(path):
    h = sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True, repr=False)
class R2Config:
    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    prefix: str = 'kuota-context/b2/'
    retention_days: int = 30
    keep_min: int = 3
    max_bytes: int = 64 * 1024 * 1024
    max_exports_day: int = 8

    @classmethod
    def desde_env(cls, env):
        if env.get('KUOTA_CONTEXT_BACKUP_ENABLED', 'false') != 'true' or env.get('KUOTA_CONTEXT_R2_PRIVATE_CONFIRMED', 'false') != 'true':
            raise RespaldoBloqueado('external_backup_not_authorized')
        try:
            result = cls(env.get('KUOTA_CONTEXT_R2_ENDPOINT', ''), env.get('KUOTA_CONTEXT_R2_BUCKET', ''),
                env.get('KUOTA_CONTEXT_R2_ACCESS_KEY_ID', ''), env.get('KUOTA_CONTEXT_R2_SECRET_ACCESS_KEY', ''),
                env.get('KUOTA_CONTEXT_R2_PREFIX', 'kuota-context/b2/'),
                int(env.get('KUOTA_CONTEXT_RETENTION_DAYS', '30')), int(env.get('KUOTA_CONTEXT_KEEP_BACKUPS', '3')),
                int(env.get('KUOTA_CONTEXT_MAX_ARCHIVE_MB', '64')) * 1024 * 1024, int(env.get('KUOTA_CONTEXT_MAX_EXPORTS_PER_DAY', '8')))
            result.validar(); return result
        except (ValueError, TypeError): raise RespaldoBloqueado('external_backup_configuration_invalid') from None

    def validar(self):
        if not re.fullmatch(r'https://[a-f0-9]{32}\.r2\.cloudflarestorage\.com', self.endpoint): raise ValueError('Endpoint R2 inválido')
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', self.bucket): raise ValueError('Bucket inválido')
        if not self.access_key or not self.secret_key: raise ValueError('Credenciales ausentes')
        if not re.fullmatch(r'[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*/', self.prefix): raise ValueError('Prefijo privado requerido')
        if type(self.retention_days) is not int or not 1 <= self.retention_days <= 365 or type(self.keep_min) is not int or not 2 <= self.keep_min <= 100:
            raise ValueError('Retención inválida')
        if type(self.max_bytes) is not int or not 1 <= self.max_bytes <= 256 * 1024 * 1024: raise ValueError('Archivo supera piloto')
        if type(self.max_exports_day) is not int or not 1 <= self.max_exports_day <= 100: raise ValueError('Presupuesto de exportación inválido')
        return self

    def identity(self):
        # No credenciales en fingerprint; identidad de namespace, no certificación de privacidad.
        return sha256(canonico({'endpoint':self.endpoint,'bucket':self.bucket,'prefix':self.prefix}).encode()).hexdigest()


class R2:
    def __init__(self, config):
        config.validar(); self.config = config
        import boto3
        from botocore.config import Config
        self.client = boto3.client('s3', endpoint_url=config.endpoint, region_name='auto',
            aws_access_key_id=config.access_key, aws_secret_access_key=config.secret_key,
            config=Config(signature_version='s3v4', s3={'addressing_style':'path'}, connect_timeout=5,
                          read_timeout=10, request_checksum_calculation='when_required', response_checksum_validation='when_required', retries={'total_max_attempts':1}))

    def upload(self, path, key, cancel=None):
        from boto3.s3.transfer import TransferConfig
        def progress(_):
            if cancel and cancel.is_set(): raise Cancelada('Cancelada')
        self.client.upload_file(str(path), self.config.bucket, key, Callback=progress,
            Config=TransferConfig(use_threads=False, max_concurrency=1, multipart_threshold=8*1024*1024))

    def download(self, key, path, max_bytes, cancel=None):
        response = self.client.get_object(Bucket=self.config.bucket, Key=key)
        body = response['Body']
        try:
            if not 0 < response['ContentLength'] <= max_bytes: raise ValueError('Tamaño remoto inválido')
            size = 0
            with open(path, 'xb') as f:
                while True:
                    if cancel and cancel.is_set(): raise Cancelada('Cancelada')
                    chunk = body.read(1024 * 1024)
                    if not chunk: break
                    size += len(chunk)
                    if size > max_bytes: raise ValueError('Descarga excesiva')
                    f.write(chunk)
                f.flush(); os.fsync(f.fileno())
            if size != response['ContentLength']: raise ValueError('Descarga incompleta')
        finally: body.close()

    def objects(self):
        pages = self.client.get_paginator('list_objects_v2').paginate(Bucket=self.config.bucket, Prefix=self.config.prefix)
        for page in pages:
            for row in page.get('Contents', []): yield row['Key']

    def delete(self, key): self.client.delete_object(Bucket=self.config.bucket, Key=key)


class Respaldos:
    def __init__(self, store, staging, config, remote=None):
        self.store = store; self.staging = Path(staging); self.config = config.validar()
        if not self.staging.is_dir() or self.staging.resolve() == store.archivo.path.parent.resolve():
            raise ValueError('Staging temporal explícito requerido')
        self.remote = remote  # Creación del SDK diferida hasta operación explícita.

    def _remote(self):
        if self.remote is None: self.remote = R2(self.config)
        return self.remote

    def _manifest(self, obj, key):
        campos(obj, ('schema_version','created_at_utc','sqlite_key','sha256','size','verified_counts','namespace'))
        digest(obj['sha256'])
        if obj['schema_version'] != 'kuota-backup-v1' or obj['namespace'] != self.config.identity(): raise ValueError('Namespace incompatible')
        utc(obj['created_at_utc'])
        expected = re.escape(self.config.prefix) + r'[0-9]{8}T[0-9]{12}Z-[a-f0-9]{32}/manifest\.json'
        if not re.fullmatch(expected, key) or obj['sqlite_key'] != key.removesuffix('manifest.json') + obj['sha256'] + '.sqlite':
            raise ValueError('Clave de objeto no permitida')
        if type(obj['size']) is not int or not 0 < obj['size'] <= self.config.max_bytes: raise ValueError('Tamaño inválido')
        campos(obj['verified_counts'], ('fixtures','captures'))
        if any(type(v) is not int or v < 0 for v in obj['verified_counts'].values()): raise ValueError('Conteos inválidos')
        return obj

    def _restaurar_temp(self, manifest_key, directory, cancel=None):
        remote = self._remote(); manifest_file = directory/'manifest.json'
        remote.download(manifest_key, manifest_file, 8192, cancel)
        obj = self._manifest(json.loads(manifest_file.read_bytes()), manifest_key)
        restored = directory/'restored.sqlite'; remote.download(obj['sqlite_key'], restored, self.config.max_bytes, cancel)
        if restored.stat().st_size != obj['size'] or hash_file(restored) != obj['sha256']: raise ValueError('Checksum remoto inválido')
        # Abrir base y comprobar cadena/bytes/versiones, no solo existencia de objeto.
        with closing(sqlite3.connect(restored.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            db.execute('BEGIN')
            if db.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID or db.execute('PRAGMA user_version').fetchone()[0] != 1: raise ValueError('Archivo ajeno')
            counts = {'fixtures': len(Archivo._verify(db)), 'captures': len(self.store._records(db))}
        if counts != obj['verified_counts'] or hash_file(restored) != obj['sha256']: raise ValueError('Restauración incompatible')
        return restored, obj

    def exportar(self, cancel=None):
        try:
            if cancel and cancel.is_set(): raise Cancelada('Cancelada')
            if self.store.archivo.path.stat().st_size > self.config.max_bytes: raise ValueError('Archivo excesivo')
            with self.store.exclusivo(cancel), tempfile.TemporaryDirectory(dir=self.staging, prefix='export-') as folder:
                day = utc(ahora()).date().isoformat(); used = self.store.control('worker:exports:' + day) or 0
                if used >= self.config.max_exports_day: raise ValueError('Presupuesto de exportación agotado')
                self.store.control('worker:exports:' + day, used + 1)
                folder = Path(folder); snapshot = folder/'snapshot.sqlite'
                self.store.backup(snapshot); counts = Operaciones(Archivo(snapshot)).verificar()
                if snapshot.stat().st_size > self.config.max_bytes: raise ValueError('Copia excesiva')
                timestamp = utc(ahora()).strftime('%Y%m%dT%H%M%S%fZ')
                key = self.config.prefix + timestamp + '-' + uuid.uuid4().hex + '/'
                h = hash_file(snapshot); manifest_key = key + 'manifest.json'
                manifest = {'schema_version':'kuota-backup-v1','created_at_utc':ahora(),'sqlite_key':key+h+'.sqlite',
                    'sha256':h,'size':snapshot.stat().st_size,'verified_counts':counts,'namespace':self.config.identity()}
                metadata = folder/'manifest.json'; metadata.write_text(canonico(manifest)); os.chmod(metadata, 0o600)
                remote = self._remote(); remote.upload(snapshot, manifest['sqlite_key'], cancel); remote.upload(metadata, manifest_key, cancel)
                check = folder/'check'; check.mkdir()
                _, downloaded_manifest = self._restaurar_temp(manifest_key, check, cancel)
                if downloaded_manifest != manifest: raise ValueError('Round-trip de otro snapshot')
                if cancel and cancel.is_set(): raise Cancelada('Cancelada')
                receipt = {'namespace':self.config.identity(),'manifest_key':manifest_key,'verified_at_utc':ahora(),
                           'sha256':h,'counts':counts, 'roundtrip_verified':True}
                self.store.control('worker:external_backup', receipt)
                self.retencion(manifest_key, cancel)
                return receipt
        except Cancelada: raise
        except Exception: raise RespaldoBloqueado('external_backup_unverified') from None

    def retencion(self, current, cancel=None):
        # Solo manifiestos del namespace y formato propio; no borrar objetos ajenos/huérfanos.
        remote = self._remote(); records = []
        for index, key in enumerate(remote.objects()):
            if index >= 10000: raise ValueError('Namespace supera piloto de retención')
            if cancel and cancel.is_set(): raise Cancelada('Cancelada')
            if not re.fullmatch(re.escape(self.config.prefix) + r'[0-9]{8}T[0-9]{12}Z-[a-f0-9]{32}/manifest\.json', key): continue
            with tempfile.TemporaryDirectory(dir=self.staging, prefix='retention-') as directory:
                path = Path(directory)/'manifest.json'; remote.download(key, path, 8192, cancel)
                try: obj = self._manifest(json.loads(path.read_bytes()), key)
                except (ValueError, TypeError, KeyError): continue
            records.append((utc(obj['created_at_utc']), key, obj['sqlite_key']))
        records.sort(reverse=True); cutoff = utc(ahora()) - timedelta(days=self.config.retention_days)
        for created, key, sqlite_key in records[self.config.keep_min:]:
            if key == current or created >= cutoff: continue
            if cancel and cancel.is_set(): raise Cancelada('Cancelada')
            remote.delete(sqlite_key); remote.delete(key)

    def restaurar(self, manifest_key, destination, cancel=None):
        destination = Path(destination)
        if not destination.is_absolute() or destination.exists() or not destination.parent.is_dir():
            raise ValueError('Restaurar solo a ruta absoluta NUEVA con directorio existente')
        try:
            with self.store.exclusivo(cancel), tempfile.TemporaryDirectory(dir=destination.parent, prefix='restore-') as directory:
                restored, obj = self._restaurar_temp(manifest_key, Path(directory), cancel)
                if cancel and cancel.is_set(): raise Cancelada('Cancelada')
                # Crear sin reemplazar una base viva; la promoción es una acción administrativa separada.
                Operaciones(Archivo(restored)).control('worker:quota_reconciliation_required', True)
                os.link(restored, destination); os.chmod(destination, 0o600)
                fd = os.open(destination.parent, os.O_RDONLY)
                try: os.fsync(fd)
                finally: os.close(fd)
                return {'restored':True,'sha256':obj['sha256'],'restored_sha256':hash_file(destination),'verified_counts':obj['verified_counts'],
                        'promotion_required':True,'provider_quota_reconciliation_required':True}
        except Cancelada: raise
        except Exception: raise RespaldoBloqueado('external_restore_unverified') from None
