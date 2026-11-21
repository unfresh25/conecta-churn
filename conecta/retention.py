"""Llamadas del equipo de retención: qué pasó después de cada una.

`clientes` solo guarda la fecha del último contacto por cliente. Una llamada se juzga a 90 días:
- se fue (churned_90d): quedó sin suscripción activa dentro de los 90 días siguientes;
- retenido: siguió activo los 90 días completos;
- censurado: la llamada fue hace menos de 90 días y sigue activo, así que todavía no se sabe.
"""
from __future__ import annotations

import pandas as pd

from conecta.labels import active_at

HORIZON_DAYS = 90


def _churn_date(subs: pd.DataFrame, date: pd.Timestamp) -> pd.Timestamp:
    """Primera fecha >= date en que el cliente queda sin ninguna suscripción vigente (un cambio de plan no cuenta)."""
    for end in sorted(subs["fecha_fin"].dropna()):
        if end < date:
            continue
        if not ((subs["fecha_inicio"] <= end) & (subs["fecha_fin"].isna() | (subs["fecha_fin"] > end))).any():
            return end
    return pd.NaT


def contact_outcomes(clients: pd.DataFrame, subscriptions: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    """Una fila por cliente contactado: fecha, si estaba activo, días hasta la baja y desenlace a 90 días."""
    contacted = clients.dropna(subset=["fecha_contacto_retencion"])
    by_client = dict(tuple(subscriptions.groupby("cliente_id")))
    rows = []
    for cid, date in zip(contacted["cliente_id"], contacted["fecha_contacto_retencion"]):
        subs = by_client.get(cid, subscriptions.iloc[0:0])
        churn = _churn_date(subs, date)
        days = (churn - date).days if pd.notna(churn) else None
        churned = days is not None and days <= HORIZON_DAYS
        observable = date + pd.Timedelta(days=HORIZON_DAYS) <= today
        rows.append({"cliente_id": cid, "contact_date": date, "active_at_contact": cid in active_at(subs, date),
                     "churn_date": churn, "days_to_churn": days, "churned_90d": churned,
                     "retained": (not churned) and observable, "censored": (not churned) and not observable})
    return pd.DataFrame(rows)


def team_contacted(clients: pd.DataFrame, cutoff: pd.Timestamp, client_ids: pd.Series) -> pd.Series:
    """¿El equipo llamó al cliente en el mes siguiente al corte? (la política actual, para comparar con el modelo)"""
    date = pd.Series(client_ids).map(clients.set_index("cliente_id")["fecha_contacto_retencion"])
    return ((date > cutoff) & (date <= cutoff + pd.offsets.MonthEnd(1))).fillna(False).astype(bool)
