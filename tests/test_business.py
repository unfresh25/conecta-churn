"""Economía del contacto de retención (valores del enunciado)."""
import pandas as pd
import pytest

from conecta.business import (CONTACT_COST, EFFECTIVENESS, PRICES, decide_contact, expected_value, realized_value,
                              sensitivity, threshold)


@pytest.mark.parametrize("plan,expected", [("Basico", 0.2180), ("Estandar", 0.1492), ("Premium", 0.1044),
                                           ("Familiar", 0.0870)])
def test_threshold(plan, expected):
    assert threshold(plan) == pytest.approx(expected, abs=1e-4)


def test_expected_value_formula():
    ev = expected_value(pd.Series([0.5]), pd.Series(["Premium"]))
    assert ev.iloc[0] == pytest.approx(0.5 * EFFECTIVENESS * 12 * PRICES["Premium"] - CONTACT_COST)


def test_decide_at_threshold_does_not_contact():
    p = pd.Series([threshold("Estandar"), threshold("Estandar") + 1e-6])
    assert decide_contact(p, pd.Series(["Estandar"] * 2)).tolist() == [0, 1]


def test_realized_value():
    # contactar=[1,1,0], churn=[1,0,1], Basico -> 0.4*12*23900 - 25000 - 25000 = 64720
    assert realized_value(pd.Series([1, 1, 0]), pd.Series([1, 0, 1]), pd.Series(["Basico"] * 3)) == pytest.approx(64_720)


def test_index_alignment_is_positional():
    v = realized_value(pd.Series([1, 0], index=[10, 11]), pd.Series([1, 0]), pd.Series(["Basico", "Basico"]))
    assert v == pytest.approx(0.4 * 12 * 23_900 - 25_000)


def test_unknown_plan_fails():
    with pytest.raises(KeyError, match="Oro"):
        threshold("Oro")
    with pytest.raises(KeyError, match="Oro"):
        expected_value(pd.Series([0.5]), pd.Series(["Oro"]))


def test_sensitivity():
    p, plan = pd.Series([0.1, 0.3, 0.9]), pd.Series(["Basico"] * 3)
    s = sensitivity(p, plan)
    assert s["effectiveness"].tolist() == [0.2, 0.4, 0.6]
    assert s["n_contacted"].is_monotonic_increasing
    assert {"effectiveness", "n_contacted", "expected_value_total"} <= set(s.columns)
