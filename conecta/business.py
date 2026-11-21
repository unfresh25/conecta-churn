"""Economía del contacto de retención (supuestos del enunciado).

Contactar cuesta 25.000 COP. Si el cliente se iba a ir, el contacto lo retiene con probabilidad 0,40 y se
conservan 12 meses de su mensualidad (precio de lista de su plan). Si no se iba a ir, solo se pierde el costo.
Valor esperado de contactar = p · efectividad · 12 · precio − costo. Se contacta si es estrictamente positivo,
lo que equivale a p > umbral(plan) = costo / (efectividad · 12 · precio).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PRICES = {"Basico": 23_900, "Estandar": 34_900, "Premium": 49_900, "Familiar": 59_900}
CONTACT_COST = 25_000
EFFECTIVENESS = 0.40
VALUE_MONTHS = 12


def _price(plan) -> np.ndarray:
    plans = pd.Series(plan).to_numpy()
    unknown = sorted({p for p in plans if p not in PRICES}, key=str)
    if unknown:
        raise KeyError(f"Plan sin precio: {unknown}")
    return np.array([PRICES[p] for p in plans], dtype=float)


def _retained_value(plan, effectiveness: float) -> np.ndarray:
    return effectiveness * VALUE_MONTHS * _price(plan)


def threshold(plan: str, cost: float = CONTACT_COST, effectiveness: float = EFFECTIVENESS) -> float:
    """Probabilidad de churn por encima de la cual contactar tiene valor esperado positivo."""
    return float(cost / _retained_value([plan], effectiveness)[0])


def expected_value(p: pd.Series, plan: pd.Series, cost: float = CONTACT_COST,
                   effectiveness: float = EFFECTIVENESS) -> pd.Series:
    """Valor esperado (COP) de contactar a cada cliente. Las series se alinean por posición."""
    p = pd.Series(p)
    return pd.Series(p.to_numpy() * _retained_value(plan, effectiveness) - cost, index=p.index)


def decide_contact(p: pd.Series, plan: pd.Series, cost: float = CONTACT_COST,
                   effectiveness: float = EFFECTIVENESS) -> pd.Series:
    """1 si p > umbral del plan (estricto), 0 si no."""
    p = pd.Series(p)
    limit = cost / _retained_value(plan, effectiveness)
    return pd.Series((p.to_numpy() > limit).astype(int), index=p.index)


def realized_value(contact: pd.Series, churn: pd.Series, plan: pd.Series, cost: float = CONTACT_COST,
                   effectiveness: float = EFFECTIVENESS) -> float:
    """Valor (COP) que habría producido la decisión según el churn observado, en esperanza sobre la efectividad."""
    c = pd.Series(contact).to_numpy().astype(bool)
    y = pd.Series(churn).to_numpy()
    gain = y * _retained_value(plan, effectiveness) - cost
    return float(gain[c].sum())


def sensitivity(p: pd.Series, plan: pd.Series, effectivenesses=(0.2, 0.4, 0.6),
                cost: float = CONTACT_COST) -> pd.DataFrame:
    """Cuántos se contactan y el valor esperado total si la efectividad real fuera otra."""
    rows = []
    for ef in effectivenesses:
        contact = decide_contact(p, plan, cost, ef).astype(bool)
        ev = expected_value(p, plan, cost, ef)
        rows.append({"effectiveness": ef, "n_contacted": int(contact.sum()),
                     "expected_value_total": float(ev[contact].sum())})
    return pd.DataFrame(rows)


PROCESS_WINDOW_DAYS = 30


def in_cancellation_process(X: pd.DataFrame, window_days: int = PROCESS_WINDOW_DAYS) -> pd.Series:
    """Cliente que ya está en el flujo de baja en el corte: el equipo de retención lo llamó en los últimos
    `window_days` días o tiene un ticket de "cancelar" en los últimos 90.

    A estos clientes no se les recomienda contacto: el equipo ya los atiende y el 95 % se va igual (sección 6),
    así que suponer una retención del 40 % para ellos no tiene sustento.
    """
    recent_call = X["days_since_contact"].le(window_days)
    cancel_ticket = X["topic_cancelar_90d"].gt(0)
    return (recent_call | cancel_ticket).astype(bool)


def break_even_effectiveness(contact: pd.Series, churn: pd.Series, plan: pd.Series,
                             cost: float = CONTACT_COST) -> float:
    """Efectividad mínima de la llamada para que una lista de contactos no pierda plata (según el churn observado)."""
    c = pd.Series(contact).to_numpy().astype(bool)
    retained_if_all = (pd.Series(churn).to_numpy() * VALUE_MONTHS * _price(plan))[c].sum()
    return float(cost * c.sum() / retained_if_all) if retained_if_all > 0 else float("inf")
