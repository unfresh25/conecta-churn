import pandas as pd
import pytest

from conecta.business import CONTACT_COST, EFFECTIVENESS, PRICES, decide_contact, expected_value, sensitivity, threshold


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


def test_sensitivity():
    p, plan = pd.Series([0.1, 0.3, 0.9]), pd.Series(["Basico"] * 3)
    s = sensitivity(p, plan)
    assert s["effectiveness"].tolist() == [0.2, 0.4, 0.6]
    assert s["n_contacted"].is_monotonic_increasing
    assert {"effectiveness", "n_contacted", "expected_value_total"} <= set(s.columns)
