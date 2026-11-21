import numpy as np
import pandas as pd
import pytest

from conecta.factors import describe, top_factors


def test_top_factors_keeps_only_positive_contributions_in_order():
    X = pd.DataFrame({"crashes_30d": [4, 0], "uses_v520": [1, 0], "city": ["Cali", "Pereira"]}, index=[10, 20])
    shap_values = np.array([[0.5, 0.9, 0.1], [-0.2, -0.1, 0.3]])
    out = top_factors(shap_values, X, k=3)
    assert out.loc[10].tolist() == ["usa la app 5.2.0: sí", "cierres de la app en 30 días: 4", "ciudad"]
    assert out.loc[20].tolist() == ["ciudad", "", ""]


def test_describe_hides_personal_values_and_handles_missing():
    assert describe("age", 41) == "edad"
    assert describe("csat_mean", np.nan) == "csat promedio: sin dato"
    assert describe("monthly_amount", 59900) == "mensualidad (COP): 59.900"
    assert describe("login_trend", 0.25) == "logins del último mes frente a los dos anteriores: 0,2 veces"


def test_top_factors_rejects_misaligned_shapes():
    with pytest.raises(ValueError):
        top_factors(np.zeros((2, 2)), pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]}))
