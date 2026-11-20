"""Etiquetas de churn a 90 días reconstruidas desde `suscripciones`.

Regla (reproduce al 100 % las 4.693 etiquetas de `etiquetas_entrenamiento`):
- Activo en la fecha d: tiene alguna suscripción con fecha_inicio <= d y (fecha_fin vacía o > d).
- churn_90d = 1 si el cliente activo en el corte no tiene ninguna suscripción activa en corte + 90 días.
Un cambio de plan cierra una suscripción y abre otra el mismo día, así que no cuenta como churn.
"""
from __future__ import annotations

import pandas as pd


def monthly_cutoffs(start: str, end: str) -> list[pd.Timestamp]:
    """Fines de mes entre start y end, ambos incluidos."""
    return list(pd.date_range(start, end, freq="ME"))


def active_at(subs: pd.DataFrame, date: pd.Timestamp) -> set[int]:
    """Clientes con alguna suscripción vigente en `date`."""
    mask = (subs["fecha_inicio"] <= date) & (subs["fecha_fin"].isna() | (subs["fecha_fin"] > date))
    return set(subs.loc[mask, "cliente_id"].astype(int))


def build_labels(subs: pd.DataFrame, cutoffs: list[pd.Timestamp], horizon_days: int = 90) -> pd.DataFrame:
    """Una fila por cliente activo en cada corte, con churn_90d."""
    frames = []
    for cutoff in cutoffs:
        active = active_at(subs, cutoff)
        still_active = active_at(subs, cutoff + pd.Timedelta(days=horizon_days))
        ids = sorted(active)
        frames.append(pd.DataFrame({
            "cliente_id": ids,
            "cutoff": cutoff,
            "churn_90d": [int(i not in still_active) for i in ids],
        }))
    return pd.concat(frames, ignore_index=True)
