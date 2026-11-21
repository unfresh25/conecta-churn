"""Variables por cliente a la fecha de corte.

Cada función filtra primero lo que se sabía en `cutoff` y después agrega:
- eventos y tickets: fecha local de Bogotá <= cutoff;
- facturas: solo las cargadas (`fecha_carga`) <= cutoff, y un pago posterior al corte cuenta como impago;
- csat: solo si el ticket ya estaba resuelto;
- contactos de retención: solo con fecha <= cutoff;
- `estado_actual` no se usa: describe el 31-dic-2025, no el corte.

Firma común: (data, cutoff, clients) -> DataFrame indexado por exactamente `clients`.
"""
from __future__ import annotations

import pandas as pd

from conecta.data import Data
from conecta.tickets import hash_text

LOGS_START = pd.Timestamp("2025-01-01")
OLD_BASIC_PRICE, NEW_BASIC_PRICE = 19_900, 23_900
TOPIC_NAMES = ["cobro_doble", "cobro_no_reconocido", "aumento_precio", "app_se_cierra",
               "lentitud", "acceso_cuenta", "cambio_plan", "cancelar"]


def _days_before(cutoff: pd.Timestamp, n: int) -> pd.Timestamp:
    return cutoff - pd.Timedelta(days=n)


def _count(df: pd.DataFrame, mask: pd.Series, clients: pd.Index) -> pd.Series:
    return df.loc[mask].groupby("cliente_id").size().reindex(clients, fill_value=0)


def _days_since(cutoff: pd.Timestamp, dates: pd.Series, clients: pd.Index) -> pd.Series:
    return (cutoff - dates).dt.days.reindex(clients)


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
    is_closed = s["fecha_fin"].notna() & (s["fecha_fin"] <= cutoff)
    current = s[~is_closed].sort_values("fecha_inicio").groupby("cliente_id").last()
    closed = s[is_closed]
    return pd.DataFrame({
        "plan": current["plan"].reindex(clients),
        "days_in_plan": _days_since(cutoff, current["fecha_inicio"], clients),
        "previous_subscriptions": closed.groupby("cliente_id").size().reindex(clients, fill_value=0),
        "plan_changes": closed[closed["motivo_cancelacion"] == "cambio_plan"].groupby("cliente_id").size()
                        .reindex(clients, fill_value=0),
    }, index=clients)


def invoice_features(data: Data, cutoff: pd.Timestamp, clients: pd.Index) -> pd.DataFrame:
    f = data.invoices[data.invoices["fecha_carga"] <= cutoff]
    paid = f["fecha_pago"].notna() & (f["fecha_pago"] <= cutoff)
    late = paid & (f["fecha_pago"] > f["fecha_vencimiento"])
    due = f["fecha_vencimiento"]
    duplicate = f["is_duplicate_charge"]
    last = f.sort_values("fecha_carga").groupby("cliente_id").last()
    paid_old_price = set(f.loc[f["monto"] == OLD_BASIC_PRICE, "cliente_id"])
    paid_new_price = set(f.loc[f["monto"] == NEW_BASIC_PRICE, "cliente_id"])
    return pd.DataFrame({
        "late_payments_90d": _count(f, late & (due > _days_before(cutoff, 90)), clients),
        "late_payments_180d": _count(f, late & (due > _days_before(cutoff, 180)), clients),
        "overdue_unpaid": _count(f, ~paid & (due < cutoff), clients),
        "duplicate_charges_total": _count(f, duplicate, clients),
        "duplicate_charges_90d": _count(f, duplicate & (f["fecha_carga"] > _days_before(cutoff, 90)), clients),
        "monthly_amount": last["monto"].reindex(clients),
        "autopay": (last["metodo_pago"] == "debito_auto").astype(int).reindex(clients),
        "last_payment_method": last["metodo_pago"].reindex(clients),
        "hit_by_price_increase": clients.isin(paid_old_price & paid_new_price).astype(int),
    }, index=clients)


def event_features(data: Data, cutoff: pd.Timestamp, clients: pd.Index) -> pd.DataFrame:
    e = data.events[data.events["local_date"] <= cutoff]
    in_30d = e["local_date"] > _days_before(cutoff, 30)
    in_90d = e["local_date"] > _days_before(cutoff, 90)
    login, error = e["tipo"] == "login", e["tipo"] == "error_app"
    out = pd.DataFrame(index=clients)
    out["logins_30d"] = _count(e, login & in_30d, clients)
    out["logins_90d"] = _count(e, login & in_90d, clients)
    logins_prev_60d = out["logins_90d"] - out["logins_30d"]
    out["login_trend"] = out["logins_30d"] / (logins_prev_60d / 2 + 1)
    out["events_90d"] = _count(e, in_90d, clients)
    out["errors_30d"] = _count(e, error & in_30d, clients)
    out["error_rate_90d"] = _count(e, error & in_90d, clients) / out["events_90d"].where(out["events_90d"] > 0)
    out["crashes_30d"] = _count(e, (e["codigo_error"] == "CRASH_ON_START") & in_30d, clients)
    out["distinct_features_90d"] = e[in_90d].groupby("cliente_id")["funcionalidad"].nunique() \
        .reindex(clients, fill_value=0)
    out["uses_v520"] = _count(e, (e["version_app"] == "5.2.0") & in_90d, clients).gt(0).astype(int)
    out["days_since_last_event"] = _days_since(cutoff, e.groupby("cliente_id")["local_date"].max(), clients)
    out["no_events"] = out["days_since_last_event"].isna().astype(int)
    out["logs_available"] = int(cutoff >= LOGS_START)
    if cutoff < LOGS_START:
        usage = out.columns.drop("logs_available")
        out[usage] = float("nan")  # sin logs no se sabe el uso: faltante, no cero
    return out


def ticket_features(data: Data, classification: pd.DataFrame, cutoff: pd.Timestamp,
                    clients: pd.Index) -> pd.DataFrame:
    t = data.tickets[data.tickets["created_at"].dt.normalize() <= cutoff]
    t = t.assign(hash=t["text"].map(hash_text, na_action="ignore")).merge(classification, on="hash", how="left")
    day = t["created_at"].dt.normalize()
    in_30d, in_90d = day > _days_before(cutoff, 30), day > _days_before(cutoff, 90)
    resolved = t["resolved_at"].notna() & (t["resolved_at"].dt.normalize() <= cutoff)
    classified = t["topic"].notna()
    out = pd.DataFrame(index=clients)
    out["tickets_30d"] = _count(t, in_30d, clients)
    out["tickets_90d"] = _count(t, in_90d, clients)
    for topic in TOPIC_NAMES:
        out[f"topic_{topic}_90d"] = _count(t, in_90d & (t["topic"] == topic), clients)
    out["annoyed_90d"] = _count(t, in_90d & classified & t["annoyed"].eq(True), clients)
    out["threats_90d"] = _count(t, in_90d & classified & (t["p_threat"] > 0.5), clients)
    out["unclassified_tickets_90d"] = _count(t, in_90d & t["text"].notna() & ~classified, clients)
    out["open_tickets"] = _count(t, ~resolved, clients)
    out["csat_mean"] = t[resolved].groupby("cliente_id")["csat"].mean().reindex(clients)
    out["days_since_last_ticket"] = _days_since(cutoff, day.groupby(t["cliente_id"]).max(), clients)
    out["no_tickets"] = out["days_since_last_ticket"].isna().astype(int)
    return out


def contact_features(data: Data, cutoff: pd.Timestamp, clients: pd.Index) -> pd.DataFrame:
    """`clientes` solo guarda la última llamada: si fue posterior al corte, se asume que no hubo otra antes."""
    contact = data.clients.set_index("cliente_id").reindex(clients)["fecha_contacto_retencion"]
    known = contact.where(contact <= cutoff)
    return pd.DataFrame({"contacted_before": known.notna().astype(int),
                         "days_since_contact": (cutoff - known).dt.days}, index=clients)


def build_matrix(data: Data, classification: pd.DataFrame, cutoff: pd.Timestamp, clients: pd.Index) -> pd.DataFrame:
    clients = pd.Index(clients, name="cliente_id")
    parts = [client_features(data, cutoff, clients), subscription_features(data, cutoff, clients),
             invoice_features(data, cutoff, clients), event_features(data, cutoff, clients),
             ticket_features(data, classification, cutoff, clients), contact_features(data, cutoff, clients)]
    return pd.concat(parts, axis=1)


def build_panel(data: Data, classification: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Una fila por (cliente, corte): cliente_id, cutoff, churn_90d y todas las variables."""
    frames = []
    for cutoff, group in labels.groupby("cutoff"):
        matrix = build_matrix(data, classification, cutoff, pd.Index(group["cliente_id"], name="cliente_id"))
        matrix = matrix.reset_index()
        matrix.insert(1, "cutoff", cutoff)
        frames.append(matrix.merge(group[["cliente_id", "churn_90d"]], on="cliente_id"))
    panel = pd.concat(frames, ignore_index=True)
    first = ["cliente_id", "cutoff", "churn_90d"]
    return panel[first + [c for c in panel.columns if c not in first]]
