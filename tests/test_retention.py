import pandas as pd

from conecta.retention import contact_outcomes, team_contacted

TODAY = pd.Timestamp("2025-12-31")


def _subs():
    return pd.DataFrame({
        "cliente_id": [1, 2, 3, 3, 4],
        "fecha_inicio": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-01", "2025-06-01", "2025-01-01"]),
        "fecha_fin": pd.to_datetime(["2025-05-12", None, "2025-06-01", "2025-08-10", None]),
    })


def _clients():
    return pd.DataFrame({"cliente_id": [1, 2, 3, 4, 5],
                         "fecha_contacto_retencion": pd.to_datetime(["2025-05-01", "2025-03-01", "2025-05-25",
                                                                     "2025-12-20", None])})


def test_contact_outcomes():
    out = contact_outcomes(_clients(), _subs(), TODAY).set_index("cliente_id")
    assert list(out.index) == [1, 2, 3, 4]
    assert out.loc[1, "days_to_churn"] == 11 and out.loc[1, "churned_90d"]
    assert out.loc[2, "retained"] and not out.loc[2, "censored"]
    # el 3 cambia de suscripción el 1-jun (no es baja) y se va el 10-ago
    assert out.loc[3, "days_to_churn"] == 77 and out.loc[3, "churned_90d"]
    assert out.loc[4, "censored"] and not out.loc[4, "retained"]


def test_team_contacted_next_month():
    s = team_contacted(_clients(), pd.Timestamp("2025-04-30"), pd.Series([1, 2, 3, 5]))
    assert s.tolist() == [True, False, True, False]
