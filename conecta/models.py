"""Modelos de churn, evaluación temporal con métricas de negocio y registro en MLflow.

- "base": regresión logística (imputación + escalado + one-hot) sobre pocas variables obvias. Es la vara mínima.
- "gbm": LightGBM con categorías nativas. Hiperparámetros fijos y conservadores, elegidos antes de mirar los folds
  de evaluación (no se ajustan sobre ellos para no sobreestimar el desempeño).
- Calibración "recent": la decisión usa probabilidades absolutas (p > umbral del plan), así que importan los niveles,
  no solo el orden. Se ajusta un Platt sobre el corte de entrenamiento más reciente, puntuado por un modelo que no lo vio.
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

from conecta.business import decide_contact, realized_value
from conecta.features import TOPIC_NAMES

SEED = 42
TRACKING_URI = "sqlite:///mlflow.db"  # MLflow 3 deja el backend de archivos en mantenimiento
EXPERIMENT = "conecta-churn"
ID_COLUMNS = ["cliente_id", "cutoff", "churn_90d"]

BASE_FEATURES = ["tenure_days", "plan", "late_payments_90d", "overdue_unpaid", "tickets_90d"]
EVENT_FEATURES = ["logins_30d", "logins_90d", "login_trend", "events_90d", "errors_30d", "error_rate_90d",
                  "crashes_30d", "distinct_features_90d", "uses_v520", "days_since_last_event", "no_events",
                  "logs_available"]
TICKET_FEATURES = (["tickets_30d", "tickets_90d"] + [f"topic_{t}_90d" for t in TOPIC_NAMES]
                   + ["annoyed_90d", "threats_90d", "unclassified_tickets_90d", "open_tickets", "csat_mean",
                      "days_since_last_ticket", "no_tickets"])
UNSTRUCTURED_FEATURES = EVENT_FEATURES + TICKET_FEATURES

GBM_PARAMS = dict(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8,
                  subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=SEED, verbose=-1)


def feature_columns(panel: pd.DataFrame, exclude: list[str] | None = None) -> list[str]:
    """Todas las columnas de variables del panel, menos las indicadas."""
    drop = set(ID_COLUMNS) | set(exclude or [])
    return [c for c in panel.columns if c not in drop]


class _AsCategory(BaseEstimator, TransformerMixin):
    """Convierte columnas de texto en `category` con las categorías vistas en fit (una nueva queda como NaN)."""

    def fit(self, X: pd.DataFrame, y=None):
        self.categories_ = {c: sorted(X[c].dropna().unique()) for c in X.columns
                            if X[c].dtype == object or isinstance(X[c].dtype, pd.CategoricalDtype)}
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        X = X.copy()
        for c in X.columns:
            if c in self.categories_:
                X[c] = pd.Categorical(X[c], categories=self.categories_[c])
            else:
                X[c] = pd.to_numeric(X[c], errors="coerce").astype(float)
        return X


def _categorical(cols: list[str], X: pd.DataFrame | None = None) -> list[str]:
    known = {"segment", "city", "acquisition_channel", "main_platform", "plan", "last_payment_method"}
    return [c for c in cols if c in known or (X is not None and X[c].dtype == object)]


def make_model(kind: Literal["base", "gbm"], columns: list[str]) -> Pipeline:
    if kind == "base":
        cat = _categorical(columns)
        num = [c for c in columns if c not in cat]
        prep = ColumnTransformer([
            ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                              ("sc", StandardScaler())]), num),
            ("cat", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="missing")),
                              ("oh", OneHotEncoder(handle_unknown="ignore"))]), cat),
        ])
        return Pipeline([("prep", prep), ("clf", LogisticRegression(max_iter=2000, C=1.0))])
    if kind == "gbm":
        from lightgbm import LGBMClassifier
        return Pipeline([("cat", _AsCategory()), ("clf", LGBMClassifier(**GBM_PARAMS))])
    raise ValueError(f"Tipo de modelo desconocido: {kind}")


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


class CalibratedModel:
    """Modelo + calibrador de Platt sobre el logit de su probabilidad."""

    def __init__(self, model: Pipeline, calibrator: LogisticRegression | None):
        self.model, self.calibrator = model, calibrator

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = self.model.predict_proba(X)[:, 1]
        if self.calibrator is not None:
            p = self.calibrator.predict_proba(_logit(p))[:, 1]
        return np.column_stack([1 - p, p])


def fit_model(panel: pd.DataFrame, train_cutoffs: list[pd.Timestamp], kind: str, columns: list[str],
              calibration: str | None = None) -> CalibratedModel:
    """Entrena con los cortes indicados. Con calibration="recent", calibra con el último de ellos."""
    train = panel[panel["cutoff"].isin(train_cutoffs)]
    model = make_model(kind, columns).fit(train[columns], train["churn_90d"])
    if calibration is None:
        return CalibratedModel(model, None)
    if calibration != "recent":
        raise ValueError(f"Calibración desconocida: {calibration}")
    cuts = sorted(train_cutoffs)
    if len(cuts) < 2:
        raise ValueError("La calibración 'recent' necesita al menos dos cortes de entrenamiento")
    early = panel[panel["cutoff"].isin(cuts[:-1])]
    last = panel[panel["cutoff"] == cuts[-1]]
    p_last = make_model(kind, columns).fit(early[columns], early["churn_90d"]).predict_proba(last[columns])[:, 1]
    calibrator = LogisticRegression(C=1e6, max_iter=1000).fit(_logit(p_last), last["churn_90d"])
    return CalibratedModel(model, calibrator)


def evaluate_run(panel: pd.DataFrame, folds: list[tuple[list[pd.Timestamp], pd.Timestamp]], kind: str,
                 columns: list[str], calibration: str | None = None) -> dict:
    """Backtest: por fold y en promedio, métricas de ranking, de calibración y de valor (COP)."""
    rows, preds = [], []
    for train_cutoffs, ev in folds:
        model = fit_model(panel, train_cutoffs, kind, columns, calibration)
        te = panel[panel["cutoff"] == ev]
        y, plan = te["churn_90d"].to_numpy(), te["plan"]
        p = model.predict_proba(te[columns])[:, 1]
        contact = decide_contact(pd.Series(p), plan)
        rows.append({
            "cutoff": ev, "n": len(te), "churn_rate": y.mean(), "mean_p": p.mean(),
            "auc_pr": average_precision_score(y, p), "auc": roc_auc_score(y, p), "brier": brier_score_loss(y, p),
            "realized_value": realized_value(contact, y, plan),
            "value_contact_all": realized_value(np.ones(len(te), int), y, plan),
            "value_contact_none": 0.0,
            "value_oracle": realized_value(y, y, plan),
            "n_contacted": int(contact.sum()),
        })
        preds.append(pd.DataFrame({"cliente_id": te["cliente_id"].to_numpy(), "cutoff": ev, "churn_90d": y,
                                   "plan": plan.to_numpy(), "p": p, "contact": contact.to_numpy()}))
    per_fold = pd.DataFrame(rows)
    metrics = per_fold.drop(columns="cutoff").mean().to_dict()
    metrics["realized_value_std"] = float(per_fold["realized_value"].std())
    return {**metrics, "per_fold": per_fold, "predictions": pd.concat(preds, ignore_index=True)}


def log_run(name: str, params: dict, result: dict, model=None) -> str:
    """Registra una corrida en MLflow (métricas promedio y por fold; tabla por fold como artefacto). Devuelve run_id."""
    import mlflow

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=name) as run:
        mlflow.log_params({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in params.items()})
        mlflow.log_metrics({k: float(v) for k, v in result.items() if isinstance(v, (int, float, np.number))})
        per_fold = result["per_fold"]
        for _, r in per_fold.iterrows():
            tag = f"{r['cutoff']:%Y_%m}"
            mlflow.log_metrics({f"{m}_{tag}": float(r[m]) for m in ["auc_pr", "auc", "brier", "realized_value"]})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "per_fold.csv"
            per_fold.to_csv(path, index=False)
            mlflow.log_artifact(str(path))
        if model is not None:
            mlflow.sklearn.log_model(model, name="model")
        return run.info.run_id
