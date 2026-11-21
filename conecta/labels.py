"""Churn a 90 días reconstruido desde `suscripciones`; reproduce el 100 % de `etiquetas_entrenamiento`.

Un cliente está activo en d si tiene una suscripción con fecha_inicio <= d y fecha_fin vacía o > d.
churn_90d = 1 si está activo en el corte y no en corte + 90 días. Un cambio de plan cierra una suscripción
y abre otra el mismo día, así que no cuenta como churn.
"""
from __future__ import annotations

import pandas as pd


def monthly_cutoffs(start: str, end: str) -> list[pd.Timestamp]:
    return list(pd.date_range(start, end, freq="ME"))


def active_at(subs: pd.DataFrame, date: pd.Timestamp) -> set[int]:
    mask = (subs["fecha_inicio"] <= date) & (subs["fecha_fin"].isna() | (subs["fecha_fin"] > date))
    return set(subs.loc[mask, "cliente_id"].astype(int))


def build_labels(subs: pd.DataFrame, cutoffs: list[pd.Timestamp], horizon_days: int = 90) -> pd.DataFrame:
    frames = []
    for cutoff in cutoffs:
        active = sorted(active_at(subs, cutoff))
        still_active = active_at(subs, cutoff + pd.Timedelta(days=horizon_days))
        frames.append(pd.DataFrame({"cliente_id": active, "cutoff": cutoff,
                                    "churn_90d": [int(i not in still_active) for i in active]}))
    return pd.concat(frames, ignore_index=True)
