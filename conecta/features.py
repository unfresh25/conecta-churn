"""Variables por cliente calculadas **a la fecha de corte**.

Regla única contra fugas: cada función filtra primero lo que se sabía en `cutoff` y recién después agrega.
- Eventos y tickets: fecha local de Bogotá <= cutoff.
- Facturas: solo las cargadas al sistema (`fecha_carga`) <= cutoff; un pago posterior al corte cuenta como no pagado.
- csat: solo existe cuando el ticket se resolvió (resolved_at <= cutoff).
- Contactos de retención: solo con fecha <= cutoff.
- `estado_actual` nunca se usa (describe el 31-dic-2025, no el corte).

Todas las funciones tienen la firma (data, cutoff, clients) -> DataFrame indexado por cliente_id con exactamente `clients`.
"""
from __future__ import annotations

import pandas as pd

from conecta.data import Data

LOGS_START = pd.Timestamp("2025-01-01")   # eventos.jsonl.gz solo cubre 2025
TOPIC_NAMES = ["cobro_doble", "cobro_no_reconocido", "aumento_precio", "app_se_cierra",
               "lentitud", "acceso_cuenta", "cambio_plan", "cancelar"]


def _days(cutoff: pd.Timestamp, n: int) -> pd.Timestamp:
    return cutoff - pd.Timedelta(days=n)


def _count(df: pd.DataFrame, mask: pd.Series, clients: pd.Index) -> pd.Series:
    return df.loc[mask].groupby("cliente_id").size().reindex(clients, fill_value=0)


def client_features(data: Data, cutoff: pd.Timestamp, clients: pd.Index) -> pd.DataFrame:
    c = data.clients.set_index("cliente_id").reindex(clients)
    return pd.DataFrame({
        "tenure_days": (cutoff - c["fecha_alta"]).dt.days,
        "segment": c["segmento"],
        "city": c["ciudad"],
        "age": c["edad"],
        "invalid_age": c["edad"].isna().astype(int),
        "acquisition_channel": c["canal_adquisicion"],
        "main_platform": c["plataforma_principal"],
    }, index=clients)


def subscription_features(data: Data, cutoff: pd.Timestamp, clients: pd.Index) -> pd.DataFrame:
    s = data.subscriptions[data.subscriptions["fecha_inicio"] <= cutoff]
    active = s[s["fecha_fin"].isna() | (s["fecha_fin"] > cutoff)].sort_values("fecha_inicio").groupby("cliente_id").last()
    closed = s[s["fecha_fin"].notna() & (s["fecha_fin"] <= cutoff)]
    out = pd.DataFrame(index=clients)
    out["plan"] = active["plan"].reindex(clients)
    out["days_in_plan"] = (cutoff - active["fecha_inicio"]).dt.days.reindex(clients)
    out["previous_subscriptions"] = closed.groupby("cliente_id").size().reindex(clients, fill_value=0)
    out["plan_changes"] = closed[closed["motivo_cancelacion"] == "cambio_plan"].groupby("cliente_id").size() \
        .reindex(clients, fill_value=0)
    return out


def invoice_features(data: Data, cutoff: pd.Timestamp, clients: pd.Index) -> pd.DataFrame:
    f = data.invoices[data.invoices["fecha_carga"] <= cutoff]
    paid = f["fecha_pago"].notna() & (f["fecha_pago"] <= cutoff)
    late = paid & (f["fecha_pago"] > f["fecha_vencimiento"])
    due = f["fecha_vencimiento"]
    out = pd.DataFrame(index=clients)
    out["late_payments_90d"] = _count(f, late & (due > _days(cutoff, 90)), clients)
    out["late_payments_180d"] = _count(f, late & (due > _days(cutoff, 180)), clients)
    out["overdue_unpaid"] = _count(f, ~paid & (due < cutoff), clients)
    out["duplicate_charges_total"] = _count(f, f["is_duplicate_charge"], clients)
    out["duplicate_charges_90d"] = _count(f, f["is_duplicate_charge"] & (f["fecha_carga"] > _days(cutoff, 90)), clients)
    last = f.sort_values("fecha_carga").groupby("cliente_id").last()
    out["monthly_amount"] = last["monto"].reindex(clients)
    out["autopay"] = (last["metodo_pago"] == "debito_auto").astype(int).reindex(clients)
    out["last_payment_method"] = last["metodo_pago"].reindex(clients)
    had_old = f[f["monto"] == 19_900].groupby("cliente_id").size()
    had_new = f[f["monto"] == 23_900].groupby("cliente_id").size()
    out["hit_by_price_increase"] = clients.isin(had_old.index.intersection(had_new.index)).astype(int)
    return out


def event_features(data: Data, cutoff: pd.Timestamp, clients: pd.Index) -> pd.DataFrame:
    e = data.events[data.events["local_date"] <= cutoff]
    d = e["local_date"]
    w30, w90 = d > _days(cutoff, 30), d > _days(cutoff, 90)
    login, err = e["tipo"] == "login", e["tipo"] == "error_app"
    out = pd.DataFrame(index=clients)
    out["logins_30d"] = _count(e, login & w30, clients)
    out["logins_90d"] = _count(e, login & w90, clients)
    prev60 = _count(e, login & w90 & ~w30, clients)
    out["login_trend"] = out["logins_30d"] / (prev60 / 2 + 1)
    out["events_90d"] = _count(e, w90, clients)
    out["errors_30d"] = _count(e, err & w30, clients)
    out["error_rate_90d"] = _count(e, err & w90, clients) / out["events_90d"].where(out["events_90d"] > 0)
    out["crashes_30d"] = _count(e, (e["codigo_error"] == "CRASH_ON_START") & w30, clients)
    out["distinct_features_90d"] = e[w90].groupby("cliente_id")["funcionalidad"].nunique().reindex(clients, fill_value=0)
    out["uses_v520"] = _count(e, (e["version_app"] == "5.2.0") & w90, clients).gt(0).astype(int)
    out["days_since_last_event"] = (cutoff - e.groupby("cliente_id")["local_date"].max()).dt.days.reindex(clients)
    out["no_events"] = out["days_since_last_event"].isna().astype(int)
    out["logs_available"] = int(cutoff >= LOGS_START)
    if cutoff < LOGS_START:  # antes de 2025 no hay logs: faltante, no "cero uso"
        cols = [c for c in out.columns if c != "logs_available"]
        out[cols] = float("nan")
    return out


def ticket_features(data: Data, classification: pd.DataFrame, cutoff: pd.Timestamp, clients: pd.Index) -> pd.DataFrame:
    t = data.tickets[data.tickets["created_at"].dt.normalize() <= cutoff].copy()
    if "hash" not in t.columns:
        from conecta.tickets import hash_text
        t["hash"] = t["text"].map(hash_text, na_action="ignore")
    t = t.merge(classification, on="hash", how="left")
    d = t["created_at"].dt.normalize()
    w30, w90 = d > _days(cutoff, 30), d > _days(cutoff, 90)
    resolved = t["resolved_at"].notna() & (t["resolved_at"].dt.normalize() <= cutoff)
    classified = t["topic"].notna()
    out = pd.DataFrame(index=clients)
    out["tickets_30d"] = _count(t, w30, clients)
    out["tickets_90d"] = _count(t, w90, clients)
    for topic in TOPIC_NAMES:
        out[f"topic_{topic}_90d"] = _count(t, w90 & (t["topic"] == topic), clients)
    out["annoyed_90d"] = _count(t, w90 & classified & t["annoyed"].eq(True), clients)
    out["threats_90d"] = _count(t, w90 & classified & (t["p_threat"] > 0.5), clients)
    out["unclassified_tickets_90d"] = _count(t, w90 & t["text"].notna() & ~classified, clients)
    out["open_tickets"] = _count(t, ~resolved, clients)
    out["csat_mean"] = t[resolved].groupby("cliente_id")["csat"].mean().reindex(clients)
    out["days_since_last_ticket"] = (cutoff - t.groupby("cliente_id")["created_at"].max().dt.normalize()).dt.days \
        .reindex(clients)
    out["no_tickets"] = out["days_since_last_ticket"].isna().astype(int)
    return out


def contact_features(data: Data, cutoff: pd.Timestamp, clients: pd.Index) -> pd.DataFrame:
    # `clientes` solo guarda el último contacto: si fue posterior al corte, no sabemos si hubo uno anterior (se asume que no).
    c = data.clients.set_index("cliente_id").reindex(clients)
    known = c["fecha_contacto_retencion"].where(c["fecha_contacto_retencion"] <= cutoff)
    return pd.DataFrame({
        "contacted_before": known.notna().astype(int),
        "days_since_contact": (cutoff - known).dt.days,
    }, index=clients)


def build_matrix(data: Data, classification: pd.DataFrame, cutoff: pd.Timestamp, clients: pd.Index) -> pd.DataFrame:
    """Todas las variables de `clients` en `cutoff`."""
    clients = pd.Index(clients, name="cliente_id")
    parts = [client_features(data, cutoff, clients), subscription_features(data, cutoff, clients),
             invoice_features(data, cutoff, clients), event_features(data, cutoff, clients),
             ticket_features(data, classification, cutoff, clients), contact_features(data, cutoff, clients)]
    return pd.concat(parts, axis=1)


def build_panel(data: Data, classification: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Una fila por (cliente, corte): cliente_id, cutoff, churn_90d y todas las variables."""
    frames = []
    for cutoff, grp in labels.groupby("cutoff"):
        m = build_matrix(data, classification, cutoff, pd.Index(grp["cliente_id"], name="cliente_id"))
        m = m.reset_index()
        m.insert(1, "cutoff", cutoff)
        frames.append(m.merge(grp[["cliente_id", "churn_90d"]], on="cliente_id"))
    panel = pd.concat(frames, ignore_index=True)
    first = ["cliente_id", "cutoff", "churn_90d"]
    return panel[first + [c for c in panel.columns if c not in first]]
