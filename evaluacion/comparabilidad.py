"""Contratos de cohortes: ninguna comparación usa mercados distintos por modelo."""
MODELOS = ('actual', 'sin_dc', 'liga', 'movil_10')
MERCADO = ['fixture_id', 'metrica', 'kind', 'lado', 'linea']


def cohorte(d, modelos=MODELOS, keys=None):
    keys = MERCADO if keys is None else keys
    required = keys + ['modelo']
    if d[required].isna().any().any():
        raise ValueError('Clave de comparación faltante')
    if not set(d.modelo.unique()).issubset(modelos):
        raise ValueError('Modelo inesperado en comparación')
    if d.duplicated(required).any():
        raise ValueError('Predicción duplicada en comparación')
    metadata = [c for c in ('fecha','liga','temporada','local','visitante','y',
                'real_local','real_visitante','maduro','maduro_efectivo','fija','defecto')
                if c in d and c not in keys]
    grouped = d.groupby(keys, observed=True, dropna=False)
    if metadata and (grouped[metadata].nunique(dropna=False) > 1).any().any():
        raise ValueError('Objetivo o metadatos inconsistentes entre modelos')
    complete = grouped.modelo.transform('size') == len(modelos)
    audit = d[keys + ['modelo']].copy()
    audit['completa'] = complete
    audit = audit.groupby(['metrica','modelo','completa'], observed=True).agg(
        filas=('fixture_id','size'), partidos=('fixture_id','nunique')).reset_index()
    return d.loc[complete].copy(), audit


def validar_temporal(d):
    if d[['fecha','train_max_fecha']].isna().any().any() or (d.train_max_fecha >= d.fecha).any():
        raise ValueError('Corte temporal inválido o faltante')
