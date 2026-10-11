"""LRU por proceso: límite de bytes/entradas y cálculo único bajo bloqueo.

No persiste resultados ni cambia las fórmulas. Un fallo no se almacena.
El bloqueo serializa los misses: evita duplicados y limita trabajo/memoria en vuelo.
"""
from collections import OrderedDict
from threading import RLock
import sys
import numpy as np
import pandas as pd


def peso(obj, vistos=None):
    vistos = set() if vistos is None else vistos
    if id(obj) in vistos:
        return 0
    vistos.add(id(obj))
    if isinstance(obj, np.ndarray):
        return sys.getsizeof(obj) + (0 if obj.flags.owndata else obj.nbytes)
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        return int(obj.memory_usage(deep=True).sum() if isinstance(obj, pd.DataFrame) else obj.memory_usage(deep=True)) + 1024
    if isinstance(obj, dict):
        return sys.getsizeof(obj) + sum(peso(k, vistos) + peso(v, vistos) for k, v in obj.items())
    if isinstance(obj, (tuple, list)):
        return sys.getsizeof(obj) + sum(peso(v, vistos) for v in obj)
    return sys.getsizeof(obj)


class CacheAnalisis:
    def __init__(self, entradas=16, bytes_max=32 * 1024 * 1024):
        self.entradas, self.bytes_max = entradas, bytes_max
        self.bytes = 0
        self._valores = OrderedDict()
        self._lock = RLock()

    def obtener(self, clave, calcular):
        with self._lock:
            if clave in self._valores:
                valor, tam = self._valores.pop(clave)
                self._valores[clave] = valor, tam
                return valor
            valor = calcular()
            tam = peso(valor)
            if tam <= self.bytes_max:
                while self._valores and (len(self._valores) >= self.entradas or self.bytes + tam > self.bytes_max):
                    _, (_, antiguo) = self._valores.popitem(last=False)
                    self.bytes -= antiguo
                self._valores[clave] = valor, tam
                self.bytes += tam
            return valor

    def limpiar(self):
        with self._lock:
            self._valores.clear()
            self.bytes = 0
