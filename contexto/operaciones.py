"""Archivo B2 y consumo transaccional sobre volumen B1; sin afirmar durabilidad física."""
from contextlib import contextmanager
from hashlib import sha256
import json
import time
import fcntl
from .almacen import Archivo
from .conectores import Captura
from .contratos import ahora, canonico, utc

DDL = '''
CREATE TABLE IF NOT EXISTS context_records (
 sequence INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, registered TEXT NOT NULL,
 body TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS context_no_update BEFORE UPDATE ON context_records
 BEGIN SELECT RAISE(ABORT,'evidencia inmutable'); END;
CREATE TRIGGER IF NOT EXISTS context_no_delete BEFORE DELETE ON context_records
 BEGIN SELECT RAISE(ABORT,'evidencia inmutable'); END;
CREATE TABLE IF NOT EXISTS api_calls (
 id INTEGER PRIMARY KEY, day TEXT NOT NULL, started TEXT NOT NULL,
 endpoint TEXT NOT NULL, fingerprint TEXT NOT NULL, purpose TEXT NOT NULL,
 status TEXT NOT NULL, code TEXT, restriction TEXT);
CREATE TABLE IF NOT EXISTS api_control (
 name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS request_cache (
 fingerprint TEXT PRIMARY KEY, record_id TEXT NOT NULL, expires REAL NOT NULL);
'''


class Cancelada(RuntimeError): pass


class Operaciones:
    def __init__(self, archivo):
        self.archivo = archivo
        with archivo._db() as db: db.executescript(DDL)

    @contextmanager
    def exclusivo(self, cancel=None, timeout=30):
        # Un consumidor por cuenta/archivo: otros procesos comparten lock y presupuesto.
        path = str(self.archivo.path) + '.lock'
        with open(path, 'a') as lock:
            deadline = time.monotonic() + timeout
            while True:
                if cancel and cancel.is_set(): raise Cancelada('Operación cancelada')
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                except BlockingIOError:
                    if time.monotonic() >= deadline: raise Cancelada('Timeout de concurrencia')
                    if cancel: cancel.wait(.05)
                    else: time.sleep(.05)
            try: yield
            finally: fcntl.flock(lock, fcntl.LOCK_UN)

    def _records(self, db):
        previous = '0' * 64; records = []
        for rid, registered, body, prev, digest in db.execute(
                'SELECT id,registered,body,previous,hash FROM context_records ORDER BY sequence'):
            if (rid != sha256(body.encode()).hexdigest() or prev != previous or
                    digest != sha256((prev + '|' + registered + '|' + body).encode()).hexdigest()):
                raise ValueError('Cadena B2 alterada')
            obj = json.loads(body)
            row = db.execute('SELECT content FROM snapshots WHERE sha256=?', (obj['evidence']['sha256'],)).fetchone()
            if not row: raise ValueError('Snapshot B2 ausente')
            cap = Captura(row[0], obj['evidence']); cap.verificar()
            if utc(cap.metadata['captured_at_utc']) > utc(registered): raise ValueError('Cronología B2 inválida')
            records.append({'id': rid, 'registered_at_utc': registered, **obj})
            previous = digest
        return records

    def records(self):
        with self.archivo._db() as db:
            db.execute('BEGIN'); return self._records(db)

    def guardar(self, cap, kind, scope):
        if kind not in ('catalog', 'request', 'context', 'weather'): raise ValueError('Tipo de captura desconocido')
        e = cap.verificar(); body = canonico({'kind': kind, 'scope': scope, 'evidence': e})
        rid = sha256(body.encode()).hexdigest()
        with self.archivo._db() as db:
            db.execute('BEGIN IMMEDIATE'); records = self._records(db)
            for r in records:
                if r['id'] == rid: return r
            db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)', (e['sha256'], cap.contenido))
            if db.execute('SELECT content FROM snapshots WHERE sha256=?', (e['sha256'],)).fetchone()[0] != cap.contenido:
                raise ValueError('Bytes archivados alterados')
            registered = ahora()
            if utc(e['captured_at_utc']) > utc(registered): raise ValueError('Captura futura')
            last = db.execute('SELECT hash FROM context_records ORDER BY sequence DESC LIMIT 1').fetchone()
            prev = last[0] if last else '0' * 64
            digest = sha256((prev + '|' + registered + '|' + body).encode()).hexdigest()
            db.execute('INSERT INTO context_records(id,registered,body,previous,hash) VALUES(?,?,?,?,?)',
                       (rid, registered, body, prev, digest))
            return {'id': rid, 'registered_at_utc': registered, 'kind': kind, 'scope': scope, 'evidence': e}

    def captura(self, rid):
        record = next((r for r in self.records() if r['id'] == rid), None)
        if record is None: raise KeyError(rid)
        with self.archivo._db() as db:
            content = db.execute('SELECT content FROM snapshots WHERE sha256=?', (record['evidence']['sha256'],)).fetchone()[0]
        return Captura(content, record['evidence']), record

    def control(self, name, value=None):
        with self.archivo._db() as db:
            if value is not None:
                db.execute('INSERT INTO api_control VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value',
                           (name, canonico(value)))
                return value
            r = db.execute('SELECT value FROM api_control WHERE name=?', (name,)).fetchone()
            return json.loads(r[0]) if r else None

    def reservar(self, endpoint, fingerprint, purpose, limit, reserve):
        if purpose not in ('discovery', 'context', 'verification', 'retry'): raise ValueError('Propósito inválido')
        now = ahora(); day = utc(now).date().isoformat()
        with self.archivo._db() as db:
            db.execute('BEGIN IMMEDIATE')
            used = db.execute('SELECT count(*) FROM api_calls WHERE day=?', (day,)).fetchone()[0]
            remaining = db.execute('SELECT value FROM api_control WHERE name=?', ('remaining:' + day,)).fetchone()
            available = json.loads(remaining[0]) if remaining else limit - used
            ceiling = limit if purpose in ('verification', 'retry') else limit - reserve
            if used >= ceiling or available <= (0 if purpose in ('verification', 'retry') else reserve):
                return None
            db.execute('INSERT INTO api_calls(day,started,endpoint,fingerprint,purpose,status) VALUES(?,?,?,?,?,?)',
                       (day, now, endpoint, fingerprint, purpose, 'reserved'))
            if remaining:
                db.execute('UPDATE api_control SET value=? WHERE name=?', (canonico(max(0, available - 1)), 'remaining:' + day))
            return db.execute('SELECT last_insert_rowid()').fetchone()[0]

    def terminar(self, attempt, code, restriction=None):
        with self.archivo._db() as db:
            db.execute('UPDATE api_calls SET status=?,code=?,restriction=? WHERE id=?',
                       ('completed', code, restriction, attempt))

    def consumo(self):
        with self.archivo._db() as db:
            return [{'day': d, 'purpose': p, 'status': s, 'code': c, 'restriction': r, 'calls': n}
                    for d, p, s, c, r, n in db.execute(
                        'SELECT day,purpose,status,code,restriction,count(*) FROM api_calls GROUP BY day,purpose,status,code,restriction')]

    def cache(self, fingerprint, rid=None, ttl=0):
        with self.archivo._db() as db:
            if rid is not None:
                db.execute('INSERT INTO request_cache VALUES(?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET record_id=excluded.record_id,expires=excluded.expires',
                           (fingerprint, rid, time.time() + ttl)); return
            r = db.execute('SELECT record_id,expires FROM request_cache WHERE fingerprint=?', (fingerprint,)).fetchone()
            return r[0] if r and r[1] > time.time() else None

    def verificar(self):
        return {'fixtures': len(self.archivo.verificar()), 'captures': len(self.records())}

    def backup(self, path):
        self.verificar(); info = self.archivo.backup(path)
        Operaciones(Archivo(path)).verificar(); return info
