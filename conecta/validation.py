"""Backtest temporal: para evaluar en E se entrena solo con cortes C <= E - 3 meses.

La etiqueta de C se conoce en C + 90 días, así que toda etiqueta de entrenamiento ya existía en E.
"""
from __future__ import annotations

import pandas as pd

HORIZON_DAYS = 90


def temporal_folds(cutoffs: list[pd.Timestamp], eval_cutoffs: list[pd.Timestamp],
                   gap_months: int = 3) -> list[tuple[list[pd.Timestamp], pd.Timestamp]]:
    folds = []
    for ev in eval_cutoffs:
        train = [c for c in cutoffs if c <= ev - pd.offsets.MonthEnd(gap_months)]
        if not train:
            raise ValueError(f"No hay cortes de entrenamiento para evaluar en {ev:%Y-%m-%d}")
        if max(train) + pd.Timedelta(days=HORIZON_DAYS) > ev:
            raise ValueError(f"Separación insuficiente: la etiqueta de {max(train):%Y-%m-%d} no se conocía en {ev:%Y-%m-%d}")
        folds.append((train, ev))
    return folds
