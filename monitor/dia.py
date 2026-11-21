"""Versión paralela del índice, para ver el efecto puntual de cada día.

    python -m monitor.dia

Pregunta: ¿dónde quedaría el índice si los datos de hoy se repitieran los
próximos 19 días hábiles? El índice publicado es el promedio de 20 días; si
el dato de hoy se repite 19 veces, ese promedio es el dato de hoy. Entonces
cada día de esta versión es el índice sin promediar, llevado a 0-100 con la
MISMA escala que el publicado (el desvío del promedio de 20 días de cada
serie): así un número de esta versión se lee igual que uno del publicado, y
muestra hacia dónde tiraría el índice si nada cambiara.

Recalcula con las series guardadas (no descarga nada) y deja los resultados
en data/dia/, sin tocar el índice publicado.
"""
from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from . import build, config, indicators

DIAS_PUBLICADO = 20
DATA_DIR = config.DATA_DIR / "dia"


def indice_del_dia(ipd: pd.Series) -> tuple[pd.Series, float]:
    """El dato del día (sin promediar) en 0-100, con el desvío del promedio de
    20 días de la misma serie."""
    sigma = float(ipd.rolling(DIAS_PUBLICADO, min_periods=DIAS_PUBLICADO).mean().std())
    if not np.isfinite(sigma) or sigma <= 0:
        return pd.Series(np.nan, index=ipd.index), np.nan
    z = (ipd / sigma).to_numpy()
    phi = 0.5 * (1 + np.vectorize(math.erf, otypes=[float])(z / math.sqrt(2)))
    return pd.Series(phi * 100, index=ipd.index).where(ipd.notna()), sigma


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config.INDICE_SUAVIZADO = 1
    config.INDICE_SIGMA = None
    indicators.pressure_index = indice_del_dia
    config.DATA_DIR = DATA_DIR
    config.OUTPUT_JSON = DATA_DIR / "monitor.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    build.run(offline=True)


if __name__ == "__main__":
    main()
