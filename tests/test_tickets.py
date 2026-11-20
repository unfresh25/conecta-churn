import datetime as dt

import pandas as pd

from conecta.tickets import hash_text, unify_tickets


def test_unify_schema_a(tickets_raw):
    df, _ = unify_tickets(tickets_raw)
    a = df[df["schema"] == "A"].iloc[0]
    assert a["cliente_id"] == 12375
    assert a["status"] == "closed"
    assert a["source_topic"] == "cobro_doble"
    assert a["csat"] == 4.0
    assert a["text"].startswith("Veo un cobro duplicado")


def test_unify_schema_b(tickets_raw):
    df, _ = unify_tickets(tickets_raw)
    b = df[df["schema"] == "B"].iloc[0]
    assert b["cliente_id"] == 12386
    assert b["text"].startswith("Me encanta pagar dos veces")  # primer mensaje del cliente, no del agente
    assert b["status"] == "open"
    assert pd.isna(b["resolved_at"])
    assert pd.isna(b["csat"])
    assert b["source_topic"] == "cobro_doble"


def test_unify_schema_b_resolved_maps_to_closed():
    rec = {"id": "TK-9", "cliente": {"id": "10001"}, "fecha": "2025-07-25T10:29:00-05:00", "canal": "app",
           "tipo": {"principal": "tecnico", "sub": "lentitud"}, "mensajes": [{"autor": "cliente", "texto": "Lento"}],
           "estado": {"valor": "resuelto", "fecha": "2025-08-24T11:29:00-05:00"}, "satisfaccion": {"csat": 2}}
    df, _ = unify_tickets([rec])
    assert df.iloc[0]["status"] == "closed"
    assert df.iloc[0]["resolved_at"] == pd.Timestamp("2025-08-24 11:29:00")
    assert df.iloc[0]["csat"] == 2.0


def test_timezone_edge(tickets_raw):
    df, _ = unify_tickets(tickets_raw)
    # A: 2025-10-01T04:30Z y B: 2025-09-30T23:30-05:00 son el mismo instante: 30-sep en Bogotá
    assert set(df["created_at"].dt.date) == {dt.date(2025, 9, 30)}


def test_null_client_is_dropped():
    df, dropped = unify_tickets([{"ticket_id": "TK-1", "customer": None, "text": "x", "created_at": "2025-01-01T00:00:00Z"}])
    assert len(df) == 0 and dropped == 1


def test_malformed_client_is_dropped():
    df, dropped = unify_tickets([{"ticket_id": "TK-1", "customer": "desconocido", "text": "x", "created_at": "2025-01-01T00:00:00Z"}])
    assert len(df) == 0 and dropped == 1


def test_hash_is_stable():
    assert hash_text(" Hola ") == hash_text("Hola")
    assert len(hash_text("Hola")) == 64
