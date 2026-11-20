"""Tickets de soporte: unificación de los dos esquemas de la plataforma de atención y clasificación del texto.

Esquema A (2023-2025): ticket_id, customer "CL-012375", created_at en UTC, category, text, status, csat.
Esquema B (2025):      id, cliente{id}, fecha con -05:00, tipo{principal, sub}, mensajes[{autor, texto}],
                       estado{valor, fecha}, satisfaccion{csat}.
Todas las fechas se llevan a hora local de Bogotá sin zona, para compararlas con las fechas de corte.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

import pandas as pd

LOCAL_TZ = "America/Bogota"
COLUMNS = ["ticket_id", "cliente_id", "created_at", "channel", "source_topic", "text",
           "status", "resolved_at", "csat", "schema"]
_STATUS = {"closed": "closed", "open": "open", "resuelto": "closed", "abierto": "open"}


def hash_text(text: str) -> str:
    """SHA-256 (hex) del texto normalizado: permite cachear la clasificación sin publicar el texto."""
    return hashlib.sha256(unicodedata.normalize("NFC", text.strip()).encode("utf-8")).hexdigest()


def _local(ts: str | None) -> pd.Timestamp:
    if not ts:
        return pd.NaT
    return pd.Timestamp(ts).tz_convert(LOCAL_TZ).tz_localize(None)


def _client_id(value) -> int | None:
    if value is None:
        return None
    match = re.fullmatch(r"(?:CL-)?0*(\d+)", str(value).strip())
    return int(match.group(1)) if match else None


def _parse_a(r: dict) -> dict:
    return {"ticket_id": r.get("ticket_id"), "cliente_id": _client_id(r.get("customer")),
            "created_at": _local(r.get("created_at")), "channel": r.get("channel"),
            "source_topic": r.get("category"), "text": r.get("text"),
            "status": _STATUS.get(r.get("status")), "resolved_at": _local(r.get("resolved_at")),
            "csat": r.get("csat"), "schema": "A"}


def _parse_b(r: dict) -> dict:
    client_msgs = [m.get("texto") for m in r.get("mensajes") or [] if m.get("autor") == "cliente"]
    state = r.get("estado") or {}
    return {"ticket_id": r.get("id"), "cliente_id": _client_id((r.get("cliente") or {}).get("id")),
            "created_at": _local(r.get("fecha")), "channel": r.get("canal"),
            "source_topic": (r.get("tipo") or {}).get("sub"), "text": client_msgs[0] if client_msgs else None,
            "status": _STATUS.get(state.get("valor")), "resolved_at": _local(state.get("fecha")),
            "csat": (r.get("satisfaccion") or {}).get("csat"), "schema": "B"}


def unify_tickets(records: list[dict]) -> tuple[pd.DataFrame, int]:
    """Unifica ambos esquemas. Devuelve (tickets, número de registros descartados por cliente o fecha ilegible)."""
    rows = [_parse_b(r) if "mensajes" in r else _parse_a(r) for r in records]
    df = pd.DataFrame(rows, columns=COLUMNS)
    valid = df["cliente_id"].notna() & df["created_at"].notna()
    df = df[valid].copy()
    df["cliente_id"] = df["cliente_id"].astype("int64")
    df["csat"] = pd.to_numeric(df["csat"], errors="coerce").astype(float)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["resolved_at"] = pd.to_datetime(df["resolved_at"])
    return df.reset_index(drop=True), int((~valid).sum())
