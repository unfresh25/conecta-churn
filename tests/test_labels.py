import pandas as pd
import pytest

from conecta.labels import active_at, build_labels, monthly_cutoffs


@pytest.fixture
def subs(subs_df):
    out = subs_df.copy()
    out["fecha_inicio"] = pd.to_datetime(out["fecha_inicio"])
    out["fecha_fin"] = pd.to_datetime(out["fecha_fin"])
    return out


def _label(labels, cliente_id):
    row = labels[labels["cliente_id"] == cliente_id]
    return None if row.empty else int(row["churn_90d"].iloc[0])


def test_monthly_cutoffs():
    c = monthly_cutoffs("2025-01-31", "2025-09-30")
    assert len(c) == 9
    assert c[1] == pd.Timestamp("2025-02-28")
    assert c[-1] == pd.Timestamp("2025-09-30")


def test_plan_change_is_not_churn(subs):
    labels = build_labels(subs, [pd.Timestamp("2025-01-31")])
    assert _label(labels, 1) == 0  # sub Basico cierra por cambio_plan y abre Premium el mismo día


def test_cancellation_inside_window_is_churn(subs):
    labels = build_labels(subs, [pd.Timestamp("2025-02-28")])
    assert _label(labels, 2) == 1


def test_end_equal_to_cutoff_is_not_active(subs):
    assert 2 not in active_at(subs, pd.Timestamp("2025-03-15"))
    assert 2 in active_at(subs, pd.Timestamp("2025-03-14"))


def test_signup_after_cutoff_is_absent(subs):
    labels = build_labels(subs, [pd.Timestamp("2025-09-30")])
    assert _label(labels, 3) is None
