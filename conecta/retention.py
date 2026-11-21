"""Desenlace de las llamadas de retención, juzgadas a 90 días.

`clientes` guarda solo la última llamada de cada cliente. Si la llamada fue hace menos de 90 días y el
cliente sigue activo, queda censurada: todavía no se sabe si se retuvo.
"""
from __future__ import annotations

import pandas as pd

from conecta.labels import active_at

HORIZON_DAYS = 90


def _churn_date(subs: pd.DataFrame, date: pd.Timestamp) -> pd.Timestamp:
    """Primera fecha >= date sin ninguna suscripción vigente; un cambio de plan no cuenta."""
    for end in sorted(subs["fecha_fin"].dropna()):
        if end >= date and not active_at(subs, end):
            return end
    return pd.NaT


def contact_outcomes(clients: pd.DataFrame, subscriptions: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    contacted = clients.dropna(subset=["fecha_contacto_retencion"])
    subs_by_client = dict(tuple(subscriptions.groupby("cliente_id")))
    rows = []
    for cid, date in zip(contacted["cliente_id"], contacted["fecha_contacto_retencion"]):
        subs = subs_by_client.get(cid, subscriptions.iloc[0:0])
        churn = _churn_date(subs, date)
        days = (churn - date).days if pd.notna(churn) else None
        churned = days is not None and days <= HORIZON_DAYS
        observable = date + pd.Timedelta(days=HORIZON_DAYS) <= today
        rows.append({"cliente_id": cid, "contact_date": date, "active_at_contact": cid in active_at(subs, date),
                     "churn_date": churn, "days_to_churn": days, "churned_90d": churned,
                     "retained": not churned and observable, "censored": not churned and not observable})
    return pd.DataFrame(rows)


def team_contacted(clients: pd.DataFrame, cutoff: pd.Timestamp, client_ids: pd.Series) -> pd.Series:
    """¿El equipo llamó al cliente en el mes siguiente al corte? Es la política actual, para comparar."""
    date = pd.Series(client_ids).map(clients.set_index("cliente_id")["fecha_contacto_retencion"])
    return ((date > cutoff) & (date <= cutoff + pd.offsets.MonthEnd(1))).fillna(False).astype(bool)
