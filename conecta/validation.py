"""Validación temporal ("backtest") sobre el panel de cortes mensuales.

Para evaluar en el corte E se entrena solo con cortes C <= E - 3 meses (fin de mes). La etiqueta de C se conoce
en C + 90 días, así que con 3 meses de separación toda etiqueta de entrenamiento ya existía en E: es exactamente
lo que tendría el equipo si hubiera entrenado ese día. Un cliente aparece en varios cortes; por eso nunca se
mezclan filas de un mismo corte entre entrenamiento y evaluación, y cualquier validación interna debe agrupar
por cliente.
"""
from __future__ import annotations

import pandas as pd

HORIZON_DAYS = 90


def temporal_folds(cutoffs: list[pd.Timestamp], eval_cutoffs: list[pd.Timestamp],
                   gap_months: int = 3) -> list[tuple[list[pd.Timestamp], pd.Timestamp]]:
    """Para cada corte de evaluación, (cortes de entrenamiento, corte de evaluación)."""
    folds = []
    for ev in eval_cutoffs:
        limit = ev - pd.offsets.MonthEnd(gap_months)
        train = [c for c in cutoffs if c <= limit]
        if not train:
            raise ValueError(f"No hay cortes de entrenamiento para evaluar en {ev:%Y-%m-%d}")
        if max(train) + pd.Timedelta(days=HORIZON_DAYS) > ev:
            raise ValueError(f"Separación insuficiente: la etiqueta de {max(train):%Y-%m-%d} no se conocía en {ev:%Y-%m-%d}")
        folds.append((train, ev))
    return folds
