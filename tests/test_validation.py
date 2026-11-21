import numpy as np
import pandas as pd
import pytest

from conecta.labels import monthly_cutoffs
from conecta.models import evaluate_run
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

METRICS = ["auc_pr", "auc", "brier", "realized_value", "value_contact_all", "n_contacted"]


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
    assert res["auc"] > 0.7
    assert set(res["predictions"]["cutoff"]) == set(EVAL)

