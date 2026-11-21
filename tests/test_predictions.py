"""Contrato de predicciones.csv: una fila por cliente a puntuar, cliente_id, probabilidad en [0, 1], contactar 0/1."""
import pandas as pd
import pytest

from conecta.models import validate_predictions

IDS = {1, 2, 3}


def _ok() -> pd.DataFrame:
    return pd.DataFrame({"cliente_id": [1, 2, 3], "probabilidad": [0.1, 0.5, 0.9], "contactar": [0, 1, 1]})


def test_validate_ok():
    validate_predictions(_ok(), IDS)


@pytest.mark.parametrize("case,match", [
    ("missing_id", "faltan"), ("duplicate_id", "duplicad"), ("prob_nan", "probabilidad"),
    ("prob_out_of_range", "probabilidad"), ("contact_2", "contactar"), ("extra_columns", "columnas"),
    ("unexpected_id", "sobran"),
])
def test_validate_fails(case, match):
    df = _ok()
    if case == "missing_id":
        df = df.iloc[:2]
    elif case == "duplicate_id":
        df = pd.concat([df, df.iloc[[0]]])
    elif case == "prob_nan":
        df.loc[0, "probabilidad"] = float("nan")
    elif case == "prob_out_of_range":
        df.loc[0, "probabilidad"] = 1.2
    elif case == "contact_2":
        df.loc[0, "contactar"] = 2
    elif case == "extra_columns":
        df["plan"] = "Basico"
    elif case == "unexpected_id":
        df = pd.concat([df, pd.DataFrame({"cliente_id": [99], "probabilidad": [0.2], "contactar": [0]})])
    with pytest.raises(ValueError, match=match):
        validate_predictions(df, IDS)
