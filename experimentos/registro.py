"""Registro prospectivo opt-in, SQLite append-only. No se conecta a producción."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import math


def canonico(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def utc(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('Timestamp sin zona horaria')
    return dt.astimezone(timezone.utc)


def validar(payload):
    required={'fixture_id','liga','kickoff_utc','generated_at_utc','modelo_version','codigo_commit',
              'metrica','kind','lado','linea','lambdas','probabilidades','datos','alcance','experimental','configuracion'}
    if set(payload)!=required: raise ValueError('Contrato de predicción incompleto o campos desconocidos')
    if payload['experimental'] is not True or payload['alcance']!='regulation':
        raise ValueError('Solo registro experimental de tiempo reglamentario')
    for name in ('fixture_id','liga','modelo_version','metrica'):
        if not isinstance(payload[name],str) or not payload[name].strip(): raise ValueError('Identificador vacío')
    if not isinstance(payload['configuracion'],dict) or not payload['configuracion']:
        raise ValueError('Configuración reproducible ausente')
    if not re.fullmatch('[0-9a-f]{40}',payload['codigo_commit']): raise ValueError('Commit inválido')
    generated,kickoff=utc(payload['generated_at_utc']),utc(payload['kickoff_utc'])
    if generated>=kickoff or generated>datetime.now(timezone.utc): raise ValueError('Predicción no prospectiva')
    from probabilidades import validar_regla
    kind=payload['kind'];side=payload['lado'];line=payload['linea']
    if kind=='ou': validar_regla({'tipo':'ou','lado':side,'linea':line,'over':True})
    elif kind in ('btts','1x2'):
        if side!='total' or line!=-1: raise ValueError('Mercado diagnóstico inválido')
    else: raise ValueError('Mercado desconocido')
    lambdas=payload['lambdas'];p=payload['probabilidades']
    if len(lambdas)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in lambdas):
        raise ValueError('Lambdas inválidas')
    if len(p)!=3 or not all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in p) or abs(sum(p)-1)>1e-12:
        raise ValueError('Probabilidades inválidas')
    if (kind=='btts' or (kind=='ou' and line%1==.5)) and p[1]!=0:
        raise ValueError('Push imposible en mercado binario')
    if not payload['datos']: raise ValueError('Sin procedencia')
    for source in payload['datos']:
        if set(source)!={'snapshot_sha256','source','captured_at_utc','available_at_utc','as_of_utc'}:
            raise ValueError('Contrato de procedencia inválido')
        if not re.fullmatch('[0-9a-f]{64}',source['snapshot_sha256']) or not source['source']:
            raise ValueError('Snapshot inválido')
        captured,available,asof=[utc(source[c]) for c in ('captured_at_utc','available_at_utc','as_of_utc')]
        if not (available<=captured<=generated and available<=asof<=generated):
            raise ValueError('Datos posteriores o disponibilidad incoherente')
    canonico(payload)


class Registro:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS predicciones (
                    secuencia INTEGER PRIMARY KEY, prediction_id TEXT UNIQUE NOT NULL,
                    registered_at_utc TEXT NOT NULL, payload TEXT NOT NULL,
                    previous_hash TEXT NOT NULL, record_hash TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS sin_update BEFORE UPDATE ON predicciones
                    BEGIN SELECT RAISE(ABORT,'registro inmutable'); END;
                CREATE TRIGGER IF NOT EXISTS sin_delete BEFORE DELETE ON predicciones
                    BEGIN SELECT RAISE(ABORT,'registro inmutable'); END;
            ''')

    def agregar(self,payload,snapshots):
        validar(payload)
        actual={hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in snapshots}
        if actual!={d['snapshot_sha256'] for d in payload['datos']}:
            raise ValueError('Hashes de snapshots no coinciden con los archivos')
        normalized=json.loads(canonico(payload))
        for key in ('generated_at_utc','kickoff_utc'):
            normalized[key]=utc(normalized[key]).isoformat()
        for source in normalized['datos']:
            for key in ('captured_at_utc','available_at_utc','as_of_utc'):
                source[key]=utc(source[key]).isoformat()
        body=canonico(normalized);identifier=hashlib.sha256(body.encode()).hexdigest()
        with sqlite3.connect(self.path,timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT prediction_id FROM predicciones WHERE prediction_id=?',(identifier,)).fetchone()
            if old: return old[0]
            now=datetime.now(timezone.utc).isoformat()
            if utc(now)>=utc(payload['kickoff_utc']): raise ValueError('Registro después del kickoff')
            previous=db.execute('SELECT record_hash FROM predicciones ORDER BY secuencia DESC LIMIT 1').fetchone()
            previous=previous[0] if previous else '0'*64
            digest=hashlib.sha256((previous+'|'+now+'|'+body).encode()).hexdigest()
            db.execute('INSERT INTO predicciones(prediction_id,registered_at_utc,payload,previous_hash,record_hash) VALUES(?,?,?,?,?)',
                       (identifier,now,body,previous,digest))
        return identifier

    def verificar(self):
        previous='0'*64
        with sqlite3.connect(self.path) as db:
            rows=db.execute('SELECT prediction_id,registered_at_utc,payload,previous_hash,record_hash FROM predicciones ORDER BY secuencia').fetchall()
        for ident,now,body,prev,digest in rows:
            if prev!=previous or ident!=hashlib.sha256(body.encode()).hexdigest() or digest!=hashlib.sha256((prev+'|'+now+'|'+body).encode()).hexdigest():
                raise ValueError('Cadena de procedencia alterada')
            previous=digest
        return len(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True);parser.add_argument('--entrada',required=True)
    parser.add_argument('--snapshot',required=True,nargs='+')
    args=parser.parse_args()
    print(Registro(args.db).agregar(json.loads(Path(args.entrada).read_text()),args.snapshot))


if __name__=='__main__': main()
