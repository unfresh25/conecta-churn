"""Economía del contacto de retención con los supuestos del enunciado.

Valor esperado de contactar = p · efectividad · 12 · precio − costo. Se contacta si es estrictamente positivo,
es decir, si p > costo / (efectividad · 12 · precio). Las series se alinean por posición.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PRICES = {"Basico": 23_900, "Estandar": 34_900, "Premium": 49_900, "Familiar": 59_900}
CONTACT_COST = 25_000
EFFECTIVENESS = 0.40
VALUE_MONTHS = 12
PROCESS_WINDOW_DAYS = 30


def _price(plan) -> np.ndarray:
    plans = pd.Series(plan).to_numpy()
    unknown = sorted({p for p in plans if p not in PRICES}, key=str)
    if unknown:
        raise KeyError(f"Plan sin precio: {unknown}")
    return np.array([PRICES[p] for p in plans], dtype=float)


def _retained_value(plan, effectiveness: float) -> np.ndarray:
    return effectiveness * VALUE_MONTHS * _price(plan)


def _as_bool(values) -> np.ndarray:
    return pd.Series(values).to_numpy().astype(bool)


def threshold(plan: str, cost: float = CONTACT_COST, effectiveness: float = EFFECTIVENESS) -> float:
    return float(cost / _retained_value([plan], effectiveness)[0])


def expected_value(p: pd.Series, plan: pd.Series, cost: float = CONTACT_COST,
                   effectiveness: float = EFFECTIVENESS) -> pd.Series:
    p = pd.Series(p)
    return pd.Series(p.to_numpy() * _retained_value(plan, effectiveness) - cost, index=p.index)


def decide_contact(p: pd.Series, plan: pd.Series, cost: float = CONTACT_COST,
                   effectiveness: float = EFFECTIVENESS) -> pd.Series:
    p = pd.Series(p)
    limit = cost / _retained_value(plan, effectiveness)
    return pd.Series((p.to_numpy() > limit).astype(int), index=p.index)


def realized_value(contact: pd.Series, churn: pd.Series, plan: pd.Series, cost: float = CONTACT_COST,
                   effectiveness: float = EFFECTIVENESS) -> float:
    """Lo que habría rendido la lista con el churn que de verdad ocurrió."""
    gain = pd.Series(churn).to_numpy() * _retained_value(plan, effectiveness) - cost
    return float(gain[_as_bool(contact)].sum())


def break_even_effectiveness(contact: pd.Series, churn: pd.Series, plan: pd.Series,
                             cost: float = CONTACT_COST) -> float:
    """Efectividad mínima de la llamada para que la lista no pierda plata."""
    selected = _as_bool(contact)
    retained_if_all = (pd.Series(churn).to_numpy() * VALUE_MONTHS * _price(plan))[selected].sum()
    return float(cost * selected.sum() / retained_if_all) if retained_if_all > 0 else float("inf")


def sensitivity(p: pd.Series, plan: pd.Series, effectivenesses=(0.2, 0.4, 0.6),
                cost: float = CONTACT_COST) -> pd.DataFrame:
    rows = []
    for ef in effectivenesses:
        contact = decide_contact(p, plan, cost, ef).astype(bool)
        rows.append({"effectiveness": ef, "n_contacted": int(contact.sum()),
                     "expected_value_total": float(expected_value(p, plan, cost, ef)[contact].sum())})
    return pd.DataFrame(rows)


def in_cancellation_process(X: pd.DataFrame, window_days: int = PROCESS_WINDOW_DAYS) -> pd.Series:
    """Llamado por el equipo de retención en los últimos `window_days` días o con ticket de cancelar en 90 días.

    No se les recomienda contacto: ya los atiende el flujo de baja y casi todos se van igual (sección 6 del
    notebook), así que el 40 % de retención no tiene sustento para ellos.
    """
    return (X["days_since_contact"].le(window_days) | X["topic_cancelar_90d"].gt(0)).astype(bool)
