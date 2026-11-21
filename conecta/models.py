"""Modelos de churn, backtest con valor en pesos y registro en MLflow.

"base" es una regresión logística con pocas variables obvias, la vara mínima. "gbm" es LightGBM con
hiperparámetros fijos, elegidos antes de mirar los folds de evaluación.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from conecta.business import decide_contact, in_cancellation_process, realized_value
from conecta.features import TOPIC_NAMES

SEED = 42
TRACKING_URI = "sqlite:///mlflow.db"
EXPERIMENT = "conecta-churn"
ID_COLUMNS = ["cliente_id", "cutoff", "churn_90d"]
PREDICTION_COLUMNS = ["cliente_id", "probabilidad", "contactar"]
CATEGORICAL_FEATURES = {"segment", "city", "acquisition_channel", "main_platform", "plan", "last_payment_method"}

BASE_FEATURES = ["tenure_days", "plan", "late_payments_90d", "overdue_unpaid", "tickets_90d"]
EVENT_FEATURES = ["logins_30d", "logins_90d", "login_trend", "events_90d", "errors_30d", "error_rate_90d",
                  "crashes_30d", "distinct_features_90d", "uses_v520", "days_since_last_event", "no_events",
                  "logs_available"]
TICKET_FEATURES = (["tickets_30d", "tickets_90d"] + [f"topic_{t}_90d" for t in TOPIC_NAMES]
                   + ["annoyed_90d", "threats_90d", "unclassified_tickets_90d", "open_tickets", "csat_mean",
                      "days_since_last_ticket", "no_tickets"])
UNSTRUCTURED_FEATURES = EVENT_FEATURES + TICKET_FEATURES
CONTACT_FEATURES = ["contacted_before", "days_since_contact"]

GBM_PARAMS = dict(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8,
                  subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=SEED, verbose=-1)
SKOPS_TRUSTED_TYPES = ["collections.OrderedDict", "conecta.models._AsCategory", "lightgbm.basic.Booster",
                       "lightgbm.sklearn.LGBMClassifier"]

Folds = list[tuple[list[pd.Timestamp], pd.Timestamp]]


def feature_columns(panel: pd.DataFrame, exclude: list[str] | None = None) -> list[str]:
    drop = set(ID_COLUMNS) | set(exclude or [])
    return [c for c in panel.columns if c not in drop]


class _AsCategory(BaseEstimator, TransformerMixin):
    """Texto -> `category` con las categorías vistas en fit; una categoría nueva queda como NaN."""

    def fit(self, X: pd.DataFrame, y=None):
        self.categories_ = {c: sorted(X[c].dropna().unique()) for c in X.columns
                            if X[c].dtype == object or isinstance(X[c].dtype, pd.CategoricalDtype)}
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        return X.assign(**{c: pd.Categorical(X[c], categories=self.categories_[c]) if c in self.categories_
                           else pd.to_numeric(X[c], errors="coerce").astype(float) for c in X.columns})


def _logistic_pipeline(columns: list[str]) -> Pipeline:
    categorical = [c for c in columns if c in CATEGORICAL_FEATURES]
    numeric = [c for c in columns if c not in CATEGORICAL_FEATURES]
    prep = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                          ("sc", StandardScaler())]), numeric),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="missing")),
                          ("oh", OneHotEncoder(handle_unknown="ignore"))]), categorical),
    ])
    return Pipeline([("prep", prep), ("clf", LogisticRegression(max_iter=2000, C=1.0))])


def make_model(kind: Literal["base", "gbm"], columns: list[str], params: dict | None = None) -> Pipeline:
    if kind == "base":
        return _logistic_pipeline(columns)
    if kind == "gbm":
        from lightgbm import LGBMClassifier
        return Pipeline([("cat", _AsCategory()), ("clf", LGBMClassifier(**{**GBM_PARAMS, **(params or {})}))])
    raise ValueError(f"Tipo de modelo desconocido: {kind}")


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


class CalibratedModel:
    """Modelo con un calibrador de Platt opcional sobre el logit de su probabilidad."""

    def __init__(self, model: Pipeline, calibrator: LogisticRegression | None):
        self.model, self.calibrator = model, calibrator

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = self.model.predict_proba(X)[:, 1]
        if self.calibrator is not None:
            p = self.calibrator.predict_proba(_logit(p))[:, 1]
        return np.column_stack([1 - p, p])


def _fit_on(panel: pd.DataFrame, cutoffs, kind: str, columns: list[str], params: dict | None) -> Pipeline:
    train = panel[panel["cutoff"].isin(cutoffs)]
    return make_model(kind, columns, params).fit(train[columns], train["churn_90d"])


def _recent_calibrator(panel, train_cutoffs, kind, columns, params) -> LogisticRegression:
    """Platt sobre el último corte de entrenamiento, puntuado por un modelo que no lo vio."""
    cuts = sorted(train_cutoffs)
    if len(cuts) < 2:
        raise ValueError("La calibración 'recent' necesita al menos dos cortes de entrenamiento")
    last = panel[panel["cutoff"] == cuts[-1]]
    p_last = _fit_on(panel, cuts[:-1], kind, columns, params).predict_proba(last[columns])[:, 1]
    return LogisticRegression(C=1e6, max_iter=1000).fit(_logit(p_last), last["churn_90d"])


def fit_model(panel: pd.DataFrame, train_cutoffs: list[pd.Timestamp], kind: str, columns: list[str],
              calibration: str | None = None, params: dict | None = None) -> CalibratedModel:
    if calibration not in (None, "recent"):
        raise ValueError(f"Calibración desconocida: {calibration}")
    model = _fit_on(panel, train_cutoffs, kind, columns, params)
    calibrator = _recent_calibrator(panel, train_cutoffs, kind, columns, params) if calibration else None
    return CalibratedModel(model, calibrator)


def _in_process(rows: pd.DataFrame) -> np.ndarray:
    if {"days_since_contact", "topic_cancelar_90d"} <= set(rows):
        return in_cancellation_process(rows).to_numpy()
    return np.zeros(len(rows), bool)


def _fold_metrics(te: pd.DataFrame, p: np.ndarray) -> tuple[dict, pd.DataFrame]:
    y, plan = te["churn_90d"].to_numpy(), te["plan"]
    contact = decide_contact(pd.Series(p), plan).to_numpy().astype(bool)
    in_process = _in_process(te)
    actionable = contact & ~in_process
    metrics = {
        "n": len(te), "churn_rate": y.mean(), "mean_p": p.mean(),
        "auc_pr": average_precision_score(y, p), "auc": roc_auc_score(y, p), "brier": brier_score_loss(y, p),
        "realized_value": realized_value(contact, y, plan),
        "value_contact_all": realized_value(np.ones(len(te), bool), y, plan),
        "value_oracle": realized_value(y, y, plan),
        "n_contacted": int(contact.sum()),
        "realized_value_actionable": realized_value(actionable, y, plan),
        "n_contacted_actionable": int(actionable.sum()),
        "n_in_process": int((contact & in_process).sum()),
        "value_contact_all_actionable": realized_value(~in_process, y, plan),
    }
    predictions = pd.DataFrame({"cliente_id": te["cliente_id"].to_numpy(), "churn_90d": y, "plan": plan.to_numpy(),
                                "p": p, "contact": contact.astype(int), "in_process": in_process,
                                "contact_actionable": actionable.astype(int)})
    return metrics, predictions


def evaluate_run(panel: pd.DataFrame, folds: Folds, kind: str, columns: list[str], calibration: str | None = None,
                 params: dict | None = None, train_exclude: pd.Series | None = None) -> dict:
    """Backtest por fold y en promedio. `train_exclude` saca filas del entrenamiento, nunca de la evaluación.
    El valor "accionable" deja fuera de la lista a quien ya está en proceso de baja."""
    train_panel = panel
    if train_exclude is not None:
        train_panel = panel[~train_exclude.reindex(panel.index).fillna(False).astype(bool)]
    rows, preds = [], []
    for train_cutoffs, ev in folds:
        model = fit_model(train_panel, train_cutoffs, kind, columns, calibration, params)
        te = panel[panel["cutoff"] == ev]
        metrics, predictions = _fold_metrics(te, model.predict_proba(te[columns])[:, 1])
        rows.append({"cutoff": ev, **metrics})
        preds.append(predictions.assign(cutoff=ev))
    per_fold = pd.DataFrame(rows)
    summary = per_fold.drop(columns="cutoff").mean().to_dict()
    summary["realized_value_std"] = float(per_fold["realized_value"].std())
    summary["realized_value_actionable_std"] = float(per_fold["realized_value_actionable"].std())
    return {**summary, "per_fold": per_fold, "predictions": pd.concat(preds, ignore_index=True)}


def log_run(name: str, params: dict, result: dict, model=None) -> str:
    import mlflow

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=name) as run:
        mlflow.log_params({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in params.items()})
        mlflow.log_metrics({k: float(v) for k, v in result.items() if isinstance(v, (int, float, np.number))})
        per_fold = result["per_fold"]
        for _, r in per_fold.iterrows():
            mlflow.log_metrics({f"{m}_{r['cutoff']:%Y_%m}": float(r[m])
                                for m in ["auc_pr", "auc", "brier", "realized_value", "realized_value_actionable"]})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "per_fold.csv"
            per_fold.to_csv(path, index=False)
            mlflow.log_artifact(str(path))
        if model is not None:
            mlflow.sklearn.log_model(model, name="model", skops_trusted_types=SKOPS_TRUSTED_TYPES,
                                     code_paths=[str(Path(__file__).parent)])
        return run.info.run_id


def validate_predictions(df: pd.DataFrame, expected_ids: set[int]) -> None:
    if list(df.columns) != PREDICTION_COLUMNS:
        raise ValueError(f"Las columnas deben ser exactamente {PREDICTION_COLUMNS}, se recibió {list(df.columns)}")
    ids = df["cliente_id"]
    if ids.duplicated().any():
        raise ValueError(f"cliente_id duplicados: {sorted(ids[ids.duplicated()].unique())[:5]}")
    missing, extra = set(expected_ids) - set(ids), set(ids) - set(expected_ids)
    if missing:
        raise ValueError(f"faltan {len(missing)} clientes a puntuar, p. ej. {sorted(missing)[:5]}")
    if extra:
        raise ValueError(f"sobran {len(extra)} clientes que no están en clientes_a_puntuar, p. ej. {sorted(extra)[:5]}")
    p = df["probabilidad"]
    if p.isna().any() or not p.between(0, 1).all():
        raise ValueError("probabilidad debe estar en [0, 1] y sin vacíos")
    if not df["contactar"].isin([0, 1]).all():
        raise ValueError("contactar solo puede valer 0 o 1")
