"""Contratos de datos y procedencia de una evaluación retrospectiva."""
from pathlib import Path
import hashlib

import numpy as np
import pandas as pd
import modelo as mo

METRICAS = tuple(m for m in mo.METRICAS if m != 'faltas')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cargar(path):
    d = pd.read_csv(path)
    required = {'fecha_dt', 'temporada_txt', 'equipo_local_txt', 'equipo_visitante_txt'}
    required.update(c for m in METRICAS for c in mo.METRICAS[m][:2])
    if required - set(d):
        raise ValueError(f'Columnas faltantes: {sorted(required-set(d))}')
    if d[list(required)].isna().any().any():
        raise ValueError('Datos faltantes: no se imputan ceros')
    d['fecha'] = pd.to_datetime(d.fecha_dt, format='%d/%m/%Y', errors='raise')
    if d.duplicated(['fecha', 'equipo_local_txt', 'equipo_visitante_txt']).any():
        raise ValueError('Partidos duplicados')
    if (d.equipo_local_txt == d.equipo_visitante_txt).any():
        raise ValueError('Un equipo no puede jugar consigo mismo')
    cols = sorted({c for m in METRICAS for c in mo.METRICAS[m][:2]})
    a = d[cols].to_numpy(dtype=float)
    if not np.isfinite(a).all() or (a < 0).any() or (a != np.floor(a)).any():
        raise ValueError('Conteos inválidos')
    for side in ('local', 'visitante'):
        if (d[f'goles_{side}_val'] != d[f'goles_{side}_primer_tiempo_val'] + d[f'goles_{side}_segundo_tiempo_val']).any():
            raise ValueError('Goles por tiempo incoherentes')
        if (d[f'tiros_a_puerta_{side}_val'] > d[f'tiros_{side}_val']).any():
            raise ValueError('Tiros a puerta mayores que tiros')
    liga = Path(path).stem.removeprefix('bbdd_')
    d['liga'] = liga
    d['fixture_id'] = [hashlib.sha256(f'{liga}|{dt:%Y-%m-%d}|{h}|{v}'.encode()).hexdigest()[:24]
                       for dt,h,v in zip(d.fecha,d.equipo_local_txt,d.equipo_visitante_txt)]
    return d.sort_values(['fecha', 'fixture_id']).reset_index(drop=True)


def inventario(path, d):
    return {'archivo': str(path), 'sha256': sha256(path), 'liga': str(d.liga.iloc[0]),
            'partidos': len(d), 'desde': str(d.fecha.min().date()), 'hasta': str(d.fecha.max().date()),
            'temporadas': d.temporada_txt.value_counts().to_dict(),
            'cuotas_verificables': False, 'disponibilidad_historica_verificable': False}
