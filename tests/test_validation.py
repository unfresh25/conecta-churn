"""Folds temporales: entrenamiento solo con cortes cuya etiqueta (90 días) ya se conocía en el corte de evaluación."""
import pandas as pd

from conecta.labels import monthly_cutoffs
from conecta.validation import temporal_folds

EVAL = [pd.Timestamp("2025-07-31"), pd.Timestamp("2025-08-31"), pd.Timestamp("2025-09-30")]


def test_folds_spec():
    cutoffs = monthly_cutoffs("2025-01-31", "2025-09-30")
    f = temporal_folds(cutoffs, EVAL)
    assert f[0] == (monthly_cutoffs("2025-01-31", "2025-04-30"), pd.Timestamp("2025-07-31"))
    assert f[2][0][-1] == pd.Timestamp("2025-06-30")


def test_no_overlap():
    cutoffs = monthly_cutoffs("2025-01-31", "2025-09-30")
    for train, ev in temporal_folds(cutoffs, EVAL):
        assert max(train) + pd.Timedelta(days=90) <= ev
        assert ev not in train


# --- Evaluación de corridas (Tarea 8) -----------------------------------------------------------
import numpy as np
import pytest

from conecta.models import make_model, evaluate_run

METRICS = ["auc_pr", "auc", "brier", "realized_value", "value_contact_all", "value_contact_none", "n_contacted"]


@pytest.fixture
def synthetic_panel():
    rng = np.random.default_rng(0)
    cutoffs = monthly_cutoffs("2025-01-31", "2025-09-30")
    rows = []
    for c in cutoffs:
        n = 300
        x = rng.normal(size=n)
        rows.append(pd.DataFrame({
            "cliente_id": np.arange(n), "cutoff": c,
            "churn_90d": (rng.random(n) < 1 / (1 + np.exp(-(x * 2 - 2)))).astype(int),
            "signal": x, "noise": rng.normal(size=n),
            "plan": rng.choice(["Basico", "Estandar", "Premium", "Familiar"], n),
        }))
    return pd.concat(rows, ignore_index=True)


@pytest.mark.parametrize("kind", ["base", "gbm"])
@pytest.mark.parametrize("calibration", [None, "recent"])
def test_evaluate_run_smoke(synthetic_panel, kind, calibration):
    folds = temporal_folds(sorted(synthetic_panel["cutoff"].unique()), EVAL)
    res = evaluate_run(synthetic_panel, folds, kind, ["signal", "noise", "plan"], calibration=calibration)
    for m in METRICS:
        assert m in res and len(res["per_fold"][m]) == 3
    assert 0 <= res["auc"] <= 1 and res["auc"] > 0.7      # la señal es fuerte: el modelo la debe encontrar
    assert res["value_contact_none"] == 0
    assert set(res["predictions"]["cutoff"]) == set(EVAL)


def test_make_model_handles_unknown_category(synthetic_panel):
    m = make_model("gbm", ["signal", "plan"]).fit(synthetic_panel[["signal", "plan"]], synthetic_panel["churn_90d"])
    p = m.predict_proba(pd.DataFrame({"signal": [0.0], "plan": ["Oro"]}))[:, 1]
    assert 0 <= p[0] <= 1
