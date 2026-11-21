import pandas as pd
import pytest

from conecta.data import Data, clean
from conecta.features import (build_matrix, build_panel, client_features, contact_features, invoice_features,
                              subscription_features, ticket_features)
from conecta.tickets import CLASSIFICATION_COLUMNS, hash_text, unify_tickets

CUT = pd.Timestamp("2025-09-30")
TEXT_OK = "Me cobraron la mensualidad dos veces este mes y quiero la devolución."
TEXT_NEW = "Un texto que nadie clasificó todavía."


def _ticket(tid, created, resolved=None, text=TEXT_OK, csat=None, client="CL-000001"):
    return {"ticket_id": tid, "customer": client, "created_at": created, "channel": "chat", "category": "cobro_doble",
            "text": text, "status": "closed" if resolved else "open", "resolved_at": resolved, "csat": csat}


@pytest.fixture
def data(clients_df, subs_df, invoices_df, events_df) -> Data:
    raw = Data(clients=clients_df, subscriptions=subs_df, invoices=invoices_df,
               labels=pd.DataFrame({"cliente_id": [], "fecha_corte": [], "churn_90d": []}),
               to_score=pd.DataFrame({"cliente_id": [1, 3]}), events=events_df, tickets_raw=[])
    d = clean(raw)
    d.tickets, _ = unify_tickets([
        _ticket("T1", "2025-09-10T15:00:00Z", resolved="2025-09-12T15:00:00Z", csat=2),
        _ticket("T2", "2025-09-25T15:00:00Z", resolved="2025-10-03T15:00:00Z", csat=5),  # resuelto después del corte
        _ticket("T3", "2025-09-28T15:00:00Z", text=TEXT_NEW),                            # texto sin clasificar
        _ticket("T4", "2025-10-01T04:30:00Z", resolved="2025-10-02T10:00:00Z"),          # 30-sep 23:30 en Bogotá
        _ticket("T5", "2025-10-05T15:00:00Z", resolved="2025-10-06T10:00:00Z"),          # posterior al corte
    ])
    return d


@pytest.fixture
def classification() -> pd.DataFrame:
    return pd.DataFrame([{"hash": hash_text(TEXT_OK), "topic": "cobro_doble", "topic_conf": 0.99, "p_threat": 0.1,
                          "p_irony": 0.9, "anger": False, "annoyed": True}])[CLASSIFICATION_COLUMNS]


IDX = pd.Index([1, 2, 3], name="cliente_id")


def test_duplicate_charge_counted(data):
    assert invoice_features(data, CUT, IDX).loc[1, "duplicate_charges_90d"] == 1


def test_contact_after_cutoff_not_counted(data):
    assert contact_features(data, CUT, IDX).loc[2, "contacted_before"] == 0
    assert contact_features(data, pd.Timestamp("2025-10-31"), IDX).loc[2, "contacted_before"] == 1


def test_ticket_resolved_after_cutoff_is_open(data, classification):
    tk = ticket_features(data, classification, CUT, IDX)
    assert tk.loc[1, "open_tickets"] == 3      # T2 y T4 (se resolvieron después del corte) y T3 (abierto)
    assert tk.loc[1, "tickets_30d"] == 4       # T1, T2, T3 y T4 (borde de zona horaria); T5 no


def test_csat_only_known_after_resolution(data, classification):
    tk = ticket_features(data, classification, CUT, IDX)
    assert tk.loc[1, "csat_mean"] == 2.0


def test_client_without_history_does_not_break(data, classification):
    cut = pd.Timestamp("2025-12-31")
    m = build_matrix(data, classification, cut, pd.Index([3], name="cliente_id"))
    assert m.index.tolist() == [3]
    assert m.loc[3, "logins_30d"] == 0 and m.loc[3, "no_events"] == 1 and m.loc[3, "no_tickets"] == 1


def test_client_and_subscription_features(data):
    cl = client_features(data, CUT, IDX)
    assert cl.loc[2, "invalid_age"] == 1 and pd.isna(cl.loc[2, "age"])
    sub = subscription_features(data, CUT, IDX)
    assert sub.loc[1, "plan"] == "Premium" and sub.loc[1, "plan_changes"] == 1
    assert pd.isna(sub.loc[2, "plan"])


def test_build_panel_shape(data, classification):
    labels = pd.DataFrame({"cliente_id": [1, 1], "cutoff": [pd.Timestamp("2025-08-31"), CUT], "churn_90d": [0, 1]})
    panel = build_panel(data, classification, labels)
    assert len(panel) == 2
    assert {"cliente_id", "cutoff", "churn_90d", "plan"} <= set(panel.columns)
