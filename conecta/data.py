"""Carga y limpieza de las fuentes de Conecta+.

Decisiones de limpieza (documentadas también en el notebook):
- `ciudad`: 17 grafías -> 6 ciudades canónicas.
- `edad`: valores fuera de [18, 100] (hay 0 y 999) se tratan como faltantes.
- Facturas: el mismo `factura_id` cargado dos veces es una recarga del sistema (se elimina);
  dos facturas con id distinto para el mismo (cliente, periodo, suscripción) son un cobro doble real
  (se conserva y se marca).
- Eventos: se deduplican por `event_id` y se lleva la marca de tiempo a la fecha local de Bogotá.
"""
from __future__ import annotations

import gzip
import json
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

LOCAL_TZ = "America/Bogota"

_CITY_MAP = {
    "bogota": "Bogotá", "bogota dc": "Bogotá",
    "medellin": "Medellín",
    "cali": "Cali", "santiago de cali": "Cali",
    "barranquilla": "Barranquilla", "bquilla": "Barranquilla",
    "bucaramanga": "Bucaramanga",
    "pereira": "Pereira",
}


@dataclass
class Data:
    """Todas las fuentes en memoria. Los nombres de columna de la fuente se conservan."""
    clients: pd.DataFrame
    subscriptions: pd.DataFrame
    invoices: pd.DataFrame
    labels: pd.DataFrame
    to_score: pd.DataFrame
    events: pd.DataFrame
    tickets_raw: list[dict] = field(repr=False)
    tickets: pd.DataFrame | None = None


def load_data(path: str | Path) -> Data:
    """Lee `conecta.db`, `tickets.jsonl` y `eventos.jsonl.gz` desde la carpeta descomprimida."""
    path = Path(path)
    with sqlite3.connect(path / "conecta.db") as con:
        read = lambda table: pd.read_sql(f"SELECT * FROM {table}", con)  # noqa: E731
        clients, subscriptions, invoices = read("clientes"), read("suscripciones"), read("facturas")
        labels, to_score = read("etiquetas_entrenamiento"), read("clientes_a_puntuar")
    with open(path / "tickets.jsonl", encoding="utf-8") as f:
        tickets_raw = [json.loads(line) for line in f if line.strip()]
    with gzip.open(path / "eventos.jsonl.gz", "rt", encoding="utf-8") as f:
        events = pd.DataFrame([json.loads(line) for line in f if line.strip()])
    return Data(clients, subscriptions, invoices, labels, to_score, events, tickets_raw)


def _ascii_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = "".join(ch for ch in text.lower() if ch.isalnum() or ch == " ")
    return " ".join(text.split())


def normalize_city(s: pd.Series) -> pd.Series:
    """Mapea las grafías de ciudad a 6 valores canónicos; lo desconocido queda NaN."""
    return s.map(lambda v: _CITY_MAP.get(_ascii_key(v)) if isinstance(v, str) else None).astype("object")


def clean_age(s: pd.Series) -> pd.Series:
    """Edad como float; fuera de [18, 100] se considera inválida (NaN)."""
    age = pd.to_numeric(s, errors="coerce").astype(float)
    return age.where(age.between(18, 100))


def clean_invoices(f: pd.DataFrame) -> pd.DataFrame:
    """Elimina recargas (mismo factura_id) y marca cobros dobles reales (id distinto, mismo periodo)."""
    out = f.copy()
    for col in ("fecha_vencimiento", "fecha_pago", "fecha_carga"):
        out[col] = pd.to_datetime(out[col])
    out = out.sort_values(["factura_id", "fecha_carga"]).drop_duplicates("factura_id", keep="first")
    out = out.sort_values(["cliente_id", "periodo", "suscripcion_id", "factura_id"])
    out["is_duplicate_charge"] = out.duplicated(["cliente_id", "periodo", "suscripcion_id"], keep="first")
    return out.reset_index(drop=True)


def clean_events(e: pd.DataFrame) -> pd.DataFrame:
    """Deduplica por event_id y agrega `local_ts` y `local_date` (hora de Bogotá, sin zona)."""
    out = e.drop_duplicates("event_id").copy()
    local = pd.to_datetime(out["ts"], utc=True).dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    out["local_ts"] = local
    out["local_date"] = local.dt.normalize()
    return out.reset_index(drop=True)


def clean(data: Data) -> Data:
    """Aplica toda la limpieza y convierte las fechas a datetime."""
    clients = data.clients.copy()
    clients["ciudad"] = normalize_city(clients["ciudad"])
    clients["edad"] = clean_age(clients["edad"])
    clients["fecha_alta"] = pd.to_datetime(clients["fecha_alta"])
    clients["fecha_contacto_retencion"] = pd.to_datetime(clients["fecha_contacto_retencion"])

    subs = data.subscriptions.copy()
    subs["fecha_inicio"] = pd.to_datetime(subs["fecha_inicio"])
    subs["fecha_fin"] = pd.to_datetime(subs["fecha_fin"])

    labels = data.labels.copy()
    labels["fecha_corte"] = pd.to_datetime(labels["fecha_corte"])

    return Data(
        clients=clients,
        subscriptions=subs,
        invoices=clean_invoices(data.invoices),
        labels=labels,
        to_score=data.to_score.copy(),
        events=clean_events(data.events),
        tickets_raw=data.tickets_raw,
        tickets=data.tickets,
    )
