import numpy as np
import pandas as pd
import pytest

from conecta.labels import monthly_cutoffs
from conecta.models import evaluate_run, make_model, nested_tuning
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
    assert res["auc"] > 0.7
    assert res["value_contact_none"] == 0
    assert set(res["predictions"]["cutoff"]) == set(EVAL)


def test_make_model_handles_unknown_category(synthetic_panel):
    m = make_model("gbm", ["signal", "plan"]).fit(synthetic_panel[["signal", "plan"]], synthetic_panel["churn_90d"])
    p = m.predict_proba(pd.DataFrame({"signal": [0.0], "plan": ["Oro"]}))[:, 1]
    assert 0 <= p[0] <= 1


def test_evaluate_run_actionable_and_train_exclusion(synthetic_panel):
    pnl = synthetic_panel.assign(days_since_contact=np.where(synthetic_panel["signal"] > 1.5, 3, np.nan),
                                 topic_cancelar_90d=0)
    folds = temporal_folds(sorted(pnl["cutoff"].unique()), EVAL)
    res = evaluate_run(pnl, folds, "gbm", ["signal", "noise", "plan"])
    assert res["n_contacted_actionable"] <= res["n_contacted"]
    assert res["realized_value_actionable"] <= res["realized_value"] + 1e-6 or res["n_in_process"] == 0
    assert (res["predictions"]["contact_actionable"] <= res["predictions"]["contact"]).all()
    excl = evaluate_run(pnl, folds, "gbm", ["signal", "noise", "plan"], train_exclude=pnl["churn_90d"] == 1)
    assert excl["mean_p"] < res["mean_p"]


def test_make_model_custom_params(synthetic_panel):
    m = make_model("gbm", ["signal"], params={"n_estimators": 5})
    assert m["clf"].n_estimators == 5


def test_nested_tuning_smoke(synthetic_panel):
    earlier = synthetic_panel.assign(cutoff=synthetic_panel["cutoff"] - pd.offsets.MonthEnd(9))
    synthetic_panel = pd.concat([earlier, synthetic_panel], ignore_index=True)
    folds = temporal_folds(sorted(synthetic_panel["cutoff"].unique()), EVAL)
    grid = [{"n_estimators": 20}, {"n_estimators": 60, "num_leaves": 7}]
    out = nested_tuning(synthetic_panel, folds, ["signal", "noise", "plan"], grid)
    assert len(out) == 3
    assert {"chosen_params", "value_default", "value_tuned", "value_best_hindsight"} <= set(out.columns)
    assert (out["value_best_hindsight"] >= out["value_tuned"] - 1e-6).all()
