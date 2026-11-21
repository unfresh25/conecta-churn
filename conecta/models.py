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

from conecta.business import decide_contact, in_cancellation_process, realized_value
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
# Variables que describen la política actual de llamadas: si la política cambia, cambian de significado (sección 6)
CONTACT_FEATURES = ["contacted_before", "days_since_contact"]

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


def make_model(kind: Literal["base", "gbm"], columns: list[str], params: dict | None = None) -> Pipeline:
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
        return Pipeline([("cat", _AsCategory()), ("clf", LGBMClassifier(**{**GBM_PARAMS, **(params or {})}))])
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
              calibration: str | None = None, params: dict | None = None) -> CalibratedModel:
    """Entrena con los cortes indicados. Con calibration="recent", calibra con el último de ellos."""
    train = panel[panel["cutoff"].isin(train_cutoffs)]
    model = make_model(kind, columns, params).fit(train[columns], train["churn_90d"])
    if calibration is None:
        return CalibratedModel(model, None)
    if calibration != "recent":
        raise ValueError(f"Calibración desconocida: {calibration}")
    cuts = sorted(train_cutoffs)
    if len(cuts) < 2:
        raise ValueError("La calibración 'recent' necesita al menos dos cortes de entrenamiento")
    early = panel[panel["cutoff"].isin(cuts[:-1])]
    last = panel[panel["cutoff"] == cuts[-1]]
    p_last = make_model(kind, columns, params).fit(early[columns], early["churn_90d"]).predict_proba(last[columns])[:, 1]
    calibrator = LogisticRegression(C=1e6, max_iter=1000).fit(_logit(p_last), last["churn_90d"])
    return CalibratedModel(model, calibrator)


def evaluate_run(panel: pd.DataFrame, folds: list[tuple[list[pd.Timestamp], pd.Timestamp]], kind: str,
                 columns: list[str], calibration: str | None = None, params: dict | None = None,
                 train_exclude: pd.Series | None = None) -> dict:
    """Backtest: por fold y en promedio, métricas de ranking, de calibración y de valor (COP).

    `train_exclude` (booleano alineado con `panel`) saca filas del entrenamiento, nunca de la evaluación.
    El valor "accionable" deja fuera de la lista a quien ya está en proceso de baja (ver `in_cancellation_process`).
    """
    rows, preds = [], []
    train_panel = panel if train_exclude is None else panel[~train_exclude.reindex(panel.index).fillna(False).astype(bool)]
    for train_cutoffs, ev in folds:
        model = fit_model(train_panel, train_cutoffs, kind, columns, calibration, params)
        te = panel[panel["cutoff"] == ev]
        y, plan = te["churn_90d"].to_numpy(), te["plan"]
        p = model.predict_proba(te[columns])[:, 1]
        contact = decide_contact(pd.Series(p), plan)
        in_process = in_cancellation_process(te).to_numpy() if {"days_since_contact", "topic_cancelar_90d"} <= set(te) \
            else np.zeros(len(te), bool)
        actionable = contact.to_numpy().astype(bool) & ~in_process
        rows.append({
            "cutoff": ev, "n": len(te), "churn_rate": y.mean(), "mean_p": p.mean(),
            "auc_pr": average_precision_score(y, p), "auc": roc_auc_score(y, p), "brier": brier_score_loss(y, p),
            "realized_value": realized_value(contact, y, plan),
            "value_contact_all": realized_value(np.ones(len(te), int), y, plan),
            "value_contact_none": 0.0,
            "value_oracle": realized_value(y, y, plan),
            "n_contacted": int(contact.sum()),
            "realized_value_actionable": realized_value(actionable, y, plan),
            "n_contacted_actionable": int(actionable.sum()),
            "n_in_process": int((contact.to_numpy().astype(bool) & in_process).sum()),
            "value_contact_all_actionable": realized_value(~in_process, y, plan),
        })
        preds.append(pd.DataFrame({"cliente_id": te["cliente_id"].to_numpy(), "cutoff": ev, "churn_90d": y,
                                   "plan": plan.to_numpy(), "p": p, "contact": contact.to_numpy(),
                                   "in_process": in_process, "contact_actionable": actionable.astype(int)}))
    per_fold = pd.DataFrame(rows)
    metrics = per_fold.drop(columns="cutoff").mean().to_dict()
    metrics["realized_value_std"] = float(per_fold["realized_value"].std())
    metrics["realized_value_actionable_std"] = float(per_fold["realized_value_actionable"].std())
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
            mlflow.log_metrics({f"{m}_{tag}": float(r[m])
                                for m in ["auc_pr", "auc", "brier", "realized_value", "realized_value_actionable"]})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "per_fold.csv"
            per_fold.to_csv(path, index=False)
            mlflow.log_artifact(str(path))
        if model is not None:
            # skops (formato seguro por defecto de MLflow 3) exige declarar los tipos propios del pipeline
            trusted = ["collections.OrderedDict", "conecta.models._AsCategory", "lightgbm.basic.Booster",
                       "lightgbm.sklearn.LGBMClassifier"]
            mlflow.sklearn.log_model(model, name="model", skops_trusted_types=trusted,
                                     code_paths=[str(Path(__file__).parent)])
        return run.info.run_id


def nested_tuning(panel: pd.DataFrame, folds: list[tuple[list[pd.Timestamp], pd.Timestamp]], columns: list[str],
                  grid: list[dict], inner_gap_months: int = 4) -> pd.DataFrame:
    """¿Ajustar hiperparámetros mejora el valor? Ajuste anidado y honesto.

    Para cada fold, los parámetros se eligen con una validación interna que solo usa datos anteriores: se evalúa en el
    último corte de entrenamiento, entrenando con cortes `inner_gap_months` antes (4 y no 3, porque un fin de enero + 90
    días cae en mayo). Se compara contra los parámetros fijos y contra el mejor en retrospectiva (techo con trampa).
    """
    from conecta.validation import temporal_folds

    cutoffs = sorted(panel["cutoff"].unique())

    def value(params, train, ev):
        model = fit_model(panel, train, "gbm", columns, params=params)
        te = panel[panel["cutoff"] == ev]
        p = model.predict_proba(te[columns])[:, 1]
        return realized_value(decide_contact(pd.Series(p), te["plan"]), te["churn_90d"].to_numpy(), te["plan"])

    rows = []
    for train, ev in folds:
        (inner_train, inner_ev), = temporal_folds(cutoffs, [max(train)], gap_months=inner_gap_months)
        chosen = max(grid, key=lambda g: value(g, inner_train, inner_ev))
        rows.append({"cutoff": ev, "chosen_params": chosen, "value_default": value({}, train, ev),
                     "value_tuned": value(chosen, train, ev),
                     "value_best_hindsight": max(value(g, train, ev) for g in grid + [{}])})
    return pd.DataFrame(rows)


PREDICTION_COLUMNS = ["cliente_id", "probabilidad", "contactar"]


def validate_predictions(df: pd.DataFrame, expected_ids: set[int]) -> None:
    """Valida el contrato de predicciones.csv; lanza ValueError con el problema concreto."""
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
