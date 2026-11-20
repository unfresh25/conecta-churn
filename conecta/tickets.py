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


# ---------------------------------------------------------------------------------------------
# Clasificación del texto (ver spec §5.3 y §6.4)
#   strands-decider -> tema (choice) y amenaza de irse (noul): acierta 38/38 y 37/38 contra la referencia.
#   pysentimiento   -> ironía e ira: strands-decider no detecta el sarcasmo; la ironía de pysentimiento sí lo ordena.
#   molesto = ira o ironía > 0,5 (corte natural del modelo, no ajustado a los 38 textos).
# ---------------------------------------------------------------------------------------------
DECIDER_MODEL = "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"
IRONY_THRESHOLD = 0.5
CLASSIFICATION_COLUMNS = ["hash", "topic", "topic_conf", "p_threat", "p_irony", "anger", "annoyed"]

TOPICS = {
    "cobro_doble": "Le cobraron dos veces o pide reembolso de un cobro duplicado",
    "cobro_no_reconocido": "No reconoce o no entiende un cobro o valor facturado",
    "aumento_precio": "Se queja de que le subieron la tarifa o el precio",
    "app_se_cierra": "La aplicación se cierra, se cae o no abre",
    "lentitud": "El servicio o la app está lento",
    "acceso_cuenta": "No puede entrar a su cuenta o recuperar/cambiar la contraseña",
    "cambio_plan": "Quiere cambiar de plan (subir o bajar) o compara planes",
    "cancelar": "Quiere cancelar o dar de baja el servicio",
}
DECIDER_QUESTIONS = {
    "topic": {"type": "choice", "instructions": "¿Cuál es el tema principal del mensaje del cliente?", "criteria": TOPICS},
    "threat": {"type": "noul", "instructions": "¿El cliente dice que quiere cancelar, irse o dar de baja el servicio, "
                                               "o amenaza con hacerlo?"},
}


def annoyed_rule(p_irony: pd.Series, anger: pd.Series) -> pd.Series:
    """Cliente molesto = emoción ira o ironía por encima del corte (estricto)."""
    return (anger.astype(bool) | (p_irony > IRONY_THRESHOLD)).astype(bool)


def _ask_decider(text: str, port: int) -> dict:
    import json
    import urllib.request

    body = json.dumps({"state": f'Mensaje de un cliente a soporte: "{text}"', "questions": DECIDER_QUESTIONS}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/systemone", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.load(resp)["answers"]


def classify_texts(texts: list[str], port: int = 8765) -> pd.DataFrame:
    """Clasifica textos únicos. Requiere `strands-decider serve` activo en `port` y pysentimiento instalado."""
    from pysentimiento import create_analyzer

    texts = sorted(set(texts))
    irony = create_analyzer(task="irony", lang="es").predict(texts)
    emotion = create_analyzer(task="emotion", lang="es").predict(texts)
    rows = []
    for text, iro, emo in zip(texts, irony, emotion):
        ans = _ask_decider(text, port)
        rows.append({"hash": hash_text(text), "topic": ans["topic"]["choice"],
                     "topic_conf": round(ans["topic"]["confidence"], 4), "p_threat": round(ans["threat"]["noul"], 4),
                     "p_irony": round(iro.probas["ironic"], 4), "anger": emo.output == "anger"})
    out = pd.DataFrame(rows)
    out["annoyed"] = annoyed_rule(out["p_irony"], out["anger"])
    return out[CLASSIFICATION_COLUMNS]


def load_classification(path) -> pd.DataFrame:
    """Carga el CSV cacheado y valida su contrato (columnas exactas, hash único, sin textos)."""
    df = pd.read_csv(path)
    if "text" in df.columns:
        raise ValueError("El CSV de clasificación no debe incluir la columna 'text' (datos de clientes).")
    if list(df.columns) != CLASSIFICATION_COLUMNS:
        raise ValueError(f"Columnas esperadas {CLASSIFICATION_COLUMNS}, recibidas {list(df.columns)}")
    if df["hash"].duplicated().any():
        raise ValueError("El CSV de clasificación tiene valores de 'hash' duplicados.")
    df["anger"] = df["anger"].astype(bool)
    df["annoyed"] = df["annoyed"].astype(bool)
    return df
