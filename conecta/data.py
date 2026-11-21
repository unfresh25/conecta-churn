"""Carga y limpieza de las fuentes. Los nombres de columna de la fuente se conservan."""
from __future__ import annotations

import gzip
import json
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

LOCAL_TZ = "America/Bogota"
VALID_AGE = (18, 100)

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
    clients: pd.DataFrame
    subscriptions: pd.DataFrame
    invoices: pd.DataFrame
    labels: pd.DataFrame
    to_score: pd.DataFrame
    events: pd.DataFrame
    tickets_raw: list[dict] = field(repr=False)
    tickets: pd.DataFrame | None = None


def _read_jsonl(lines) -> list[dict]:
    return [json.loads(line) for line in lines if line.strip()]


def load_data(path: str | Path) -> Data:
    path = Path(path)
    with sqlite3.connect(path / "conecta.db") as con:
        tables = {t: pd.read_sql(f"SELECT * FROM {t}", con) for t in
                  ["clientes", "suscripciones", "facturas", "etiquetas_entrenamiento", "clientes_a_puntuar"]}
    with open(path / "tickets.jsonl", encoding="utf-8") as f:
        tickets_raw = _read_jsonl(f)
    with gzip.open(path / "eventos.jsonl.gz", "rt", encoding="utf-8") as f:
        events = pd.DataFrame(_read_jsonl(f))
    return Data(tables["clientes"], tables["suscripciones"], tables["facturas"], tables["etiquetas_entrenamiento"],
                tables["clientes_a_puntuar"], events, tickets_raw)


def _ascii_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = "".join(ch for ch in text.lower() if ch.isalnum() or ch == " ")
    return " ".join(text.split())


def normalize_city(s: pd.Series) -> pd.Series:
    """Lleva las 17 grafías a 6 ciudades; una grafía desconocida queda como NaN."""
    return s.map(lambda v: _CITY_MAP.get(_ascii_key(v)) if isinstance(v, str) else None).astype("object")


def clean_age(s: pd.Series) -> pd.Series:
    """La fuente trae edades 0 y 999: fuera del rango válido se tratan como faltantes."""
    age = pd.to_numeric(s, errors="coerce").astype(float)
    return age.where(age.between(*VALID_AGE))


def clean_invoices(f: pd.DataFrame) -> pd.DataFrame:
    """Un `factura_id` repetido es una recarga del sistema y se descarta. Dos ids distintos para el mismo
    cliente, periodo y suscripción son un cobro doble real: se conserva y se marca."""
    out = f.copy()
    for col in ("fecha_vencimiento", "fecha_pago", "fecha_carga"):
        out[col] = pd.to_datetime(out[col])
    out = out.sort_values(["factura_id", "fecha_carga"]).drop_duplicates("factura_id", keep="first")
    out = out.sort_values(["cliente_id", "periodo", "suscripcion_id", "factura_id"])
    out["is_duplicate_charge"] = out.duplicated(["cliente_id", "periodo", "suscripcion_id"], keep="first")
    return out.reset_index(drop=True)


def clean_events(e: pd.DataFrame) -> pd.DataFrame:
    out = e.drop_duplicates("event_id").copy()
    out["local_ts"] = pd.to_datetime(out["ts"], utc=True).dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    out["local_date"] = out["local_ts"].dt.normalize()
    return out.reset_index(drop=True)


def _parse_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return df.assign(**{c: pd.to_datetime(df[c]) for c in columns})


def clean(data: Data) -> Data:
    clients = _parse_dates(data.clients, ["fecha_alta", "fecha_contacto_retencion"])
    clients["ciudad"] = normalize_city(clients["ciudad"])
    clients["edad"] = clean_age(clients["edad"])
    return Data(
        clients=clients,
        subscriptions=_parse_dates(data.subscriptions, ["fecha_inicio", "fecha_fin"]),
        invoices=clean_invoices(data.invoices),
        labels=_parse_dates(data.labels, ["fecha_corte"]),
        to_score=data.to_score.copy(),
        events=clean_events(data.events),
        tickets_raw=data.tickets_raw,
        tickets=data.tickets,
    )
