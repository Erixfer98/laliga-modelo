"""Archivo B1 SQLite de un nodo: append-only, FULL sync, backup consistente y as-of efectivo.

La durabilidad depende de un volumen persistente y backups configurados externamente.
Nunca declara certificación del proveedor ni registra predicciones: eso sigue en Fase 3.
"""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from .contratos import ahora, canonico, evidencia, fixture, utc, validar_mapeo
from .identidad import normalizar

DDL = '''
CREATE TABLE IF NOT EXISTS snapshots (sha256 TEXT PRIMARY KEY, content BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS receipts (
 sequence INTEGER PRIMARY KEY, receipt_id TEXT UNIQUE NOT NULL,
 registered_at_utc TEXT NOT NULL, payload TEXT NOT NULL,
 previous_hash TEXT NOT NULL, record_hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS snapshot_no_update BEFORE UPDATE ON snapshots
 BEGIN SELECT RAISE(ABORT,'archivo inmutable'); END;
CREATE TRIGGER IF NOT EXISTS snapshot_no_delete BEFORE DELETE ON snapshots
 BEGIN SELECT RAISE(ABORT,'archivo inmutable'); END;
CREATE TRIGGER IF NOT EXISTS receipt_no_update BEFORE UPDATE ON receipts
 BEGIN SELECT RAISE(ABORT,'archivo inmutable'); END;
CREATE TRIGGER IF NOT EXISTS receipt_no_delete BEFORE DELETE ON receipts
 BEGIN SELECT RAISE(ABORT,'archivo inmutable'); END;
'''
APPLICATION_ID = 1263875121  # KCB1; no abrir/modificar bases del registro de Fase 3.


class Archivo:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_absolute() or self.path.name == ':memory:':
            raise ValueError('Archivo requiere ruta absoluta explícita')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        exists = self.path.exists()
        with self._db() as db:
            if exists and (db.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID or
                           db.execute('PRAGMA user_version').fetchone()[0] != 1):
                raise ValueError('Base ajena o versión de archivo incompatible')
            db.execute(f'PRAGMA application_id={APPLICATION_ID}')
            db.execute('PRAGMA user_version=1')
            db.executescript(DDL)

    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA foreign_keys=ON')
        return db

    @staticmethod
    def _verify(db):
        previous = '0' * 64; result = []
        for ident, registered, body, prev, record in db.execute(
                'SELECT receipt_id,registered_at_utc,payload,previous_hash,record_hash FROM receipts ORDER BY sequence'):
            if (ident != sha256(body.encode()).hexdigest() or prev != previous or
                    record != sha256((prev + '|' + registered + '|' + body).encode()).hexdigest()):
                raise ValueError('Cadena de archivo alterada')
            payload = json.loads(body)
            e = evidencia(payload['evidence']); f = fixture(payload['fixture'])
            if utc(e['captured_at_utc']) > utc(registered):
                raise ValueError('Captura posterior a registro')
            archived = db.execute('SELECT content FROM snapshots WHERE sha256=?', (e['sha256'],)).fetchone()
            if not archived or sha256(archived[0]).hexdigest() != e['sha256']:
                raise ValueError('Snapshot ausente o alterado')
            from .conectores import Captura
            identity_cutoff = payload.get('identity_cutoff_utc')
            if identity_cutoff and utc(identity_cutoff) > utc(registered):
                raise ValueError('Revisión de identidad posterior al registro')
            checked, _ = normalizar(Captura(archived[0], e), f['fixture_id'], payload['mappings'], identity_cutoff,
                                    payload.get('deduplicate', False))
            if checked != f:
                raise ValueError('Fixture no corresponde a evidencia')
            for mapping in payload['mappings']:
                m = validar_mapeo(mapping)
                proof = db.execute('SELECT content FROM snapshots WHERE sha256=?', (m['evidence_sha256'],)).fetchone()
                if not proof or sha256(proof[0]).hexdigest() != m['evidence_sha256']:
                    raise ValueError('Evidencia de mapeo ausente o alterada')
            result.append({'receipt_id': ident, 'registered_at_utc': registered, **payload,
                           'provider_availability_certified': False,
                           'organizer_identity_certified': False})
            previous = record
        return result

    def agregar_fixture(self, capture, requested_id, mappings, mapping_proofs, identity_cutoff=None, deduplicate=False):
        """No acepta fixture del cliente: deriva identidad nuevamente de bytes del feed."""
        f, selected = normalizar(capture, requested_id, mappings, identity_cutoff, deduplicate)
        e = capture.verificar()
        proofs = {sha256(x).hexdigest(): x for x in mapping_proofs}
        if set(proofs) != {m['evidence_sha256'] for m in selected}:
            raise ValueError('Se requieren bytes de evidencias de mapeo')
        payload = {'evidence': e, 'fixture': f, 'mappings': selected}
        if identity_cutoff:
            from .contratos import iso
            payload['identity_cutoff_utc'] = iso(identity_cutoff)
        if deduplicate:
            payload['deduplicate'] = True
        body = canonico(payload); identifier = sha256(body.encode()).hexdigest()
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            # Integridad se comprueba bajo el mismo lock; no extender una cadena dañada.
            rows = self._verify(db)
            for old in rows:
                if old['receipt_id'] == identifier:
                    return old
            for digest, content in {**proofs, e['sha256']: capture.contenido}.items():
                db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)', (digest, content))
                if db.execute('SELECT content FROM snapshots WHERE sha256=?', (digest,)).fetchone()[0] != content:
                    raise ValueError('Snapshot archivado alterado')
            registered = ahora()  # servidor, tras lock y archivo
            if utc(e['captured_at_utc']) > utc(registered):
                raise ValueError('Captura futura')
            if identity_cutoff and utc(identity_cutoff) > utc(registered):
                raise ValueError('Revisión de identidad futura')
            previous = db.execute('SELECT record_hash FROM receipts ORDER BY sequence DESC LIMIT 1').fetchone()
            previous = previous[0] if previous else '0' * 64
            record = sha256((previous + '|' + registered + '|' + body).encode()).hexdigest()
            db.execute('INSERT INTO receipts(receipt_id,registered_at_utc,payload,previous_hash,record_hash) VALUES(?,?,?,?,?)',
                       (identifier, registered, body, previous, record))
            return {'receipt_id': identifier, 'registered_at_utc': registered, **payload,
                    'provider_availability_certified': False, 'organizer_identity_certified': False}

    def verificar(self):
        with self._db() as db:
            db.execute('BEGIN')
            return self._verify(db)

    def consultar_asof(self, provider, fixture_id, cutoff):
        """Registro local efectivo, no timestamp de captura declarado, controla elegibilidad."""
        candidates = [r for r in self.verificar() if r['fixture']['provider'] == provider and
                      r['fixture']['fixture_id'] == fixture_id and
                      utc(r['registered_at_utc']) <= utc(cutoff)]
        return candidates[-1] if candidates else None

    def backup(self, destination):
        dest = Path(destination)
        if not dest.is_absolute() or dest.exists() or dest.resolve() == self.path.resolve():
            raise ValueError('Backup debe ser ruta nueva absoluta')
        self.verificar(); dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb'):
            pass
        with self._db() as source, sqlite3.connect(dest) as target:
            source.backup(target)
        restored = Archivo(dest)
        restored.verificar()
        return {'path': str(dest), 'sha256': sha256(dest.read_bytes()).hexdigest()}
