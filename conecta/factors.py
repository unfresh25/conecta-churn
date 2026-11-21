"""Factores de riesgo por cliente en palabras, a partir de los valores SHAP del modelo final (para el dashboard).

Solo cuentan las contribuciones que suben la probabilidad. Ciudad y edad se nombran sin su valor, para no exportar
datos personales.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TOPICS = {"cobro_doble": "cobro doble", "cobro_no_reconocido": "cobro no reconocido", "aumento_precio": "aumento de precio",
          "app_se_cierra": "la app se cierra", "lentitud": "lentitud", "acceso_cuenta": "acceso a la cuenta",
          "cambio_plan": "cambio de plan", "cancelar": "cancelar"}

LABELS = {
    "tenure_days": "antigüedad (días)", "segment": "segmento", "city": "ciudad", "age": "edad", "invalid_age": "edad inválida",
    "acquisition_channel": "canal de adquisición", "main_platform": "plataforma", "plan": "plan",
    "days_in_plan": "días en el plan", "previous_subscriptions": "suscripciones previas", "plan_changes": "cambios de plan",
    "late_payments_90d": "pagos tarde en 90 días", "late_payments_180d": "pagos tarde en 180 días",
    "overdue_unpaid": "facturas vencidas sin pagar", "duplicate_charges_total": "cobros dobles en total",
    "duplicate_charges_90d": "cobros dobles en 90 días", "monthly_amount": "mensualidad (COP)", "autopay": "débito automático",
    "last_payment_method": "último medio de pago", "hit_by_price_increase": "afectado por el aumento del Básico",
    "logins_30d": "logins en 30 días", "logins_90d": "logins en 90 días", "login_trend": "logins del último mes frente a los dos anteriores",
    "events_90d": "eventos en la app en 90 días", "errors_30d": "errores de la app en 30 días",
    "error_rate_90d": "tasa de errores en 90 días", "crashes_30d": "cierres de la app en 30 días",
    "distinct_features_90d": "funcionalidades usadas en 90 días", "uses_v520": "usa la app 5.2.0",
    "days_since_last_event": "días desde el último uso de la app", "no_events": "no usa la app",
    "logs_available": "hay logs de la app", "tickets_30d": "tickets en 30 días", "tickets_90d": "tickets en 90 días",
    **{f"topic_{k}_90d": f"tickets de {v} en 90 días" for k, v in TOPICS.items()},
    "annoyed_90d": "tickets molestos en 90 días", "threats_90d": "amenazas de irse en 90 días",
    "unclassified_tickets_90d": "tickets sin clasificar en 90 días", "open_tickets": "tickets abiertos",
    "csat_mean": "csat promedio", "days_since_last_ticket": "días desde el último ticket", "no_tickets": "sin tickets",
}
YES_NO = {"invalid_age", "autopay", "hit_by_price_increase", "uses_v520", "no_events", "logs_available", "no_tickets"}
HIDE_VALUE = {"city", "age"}


def describe(feature: str, value) -> str:
    label = LABELS.get(feature, feature)
    if feature in HIDE_VALUE:
        return label
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return f"{label}: sin dato"
    if feature in YES_NO:
        return f"{label}: {'sí' if value else 'no'}"
    if isinstance(value, (int, float, np.number)):
        if feature == "error_rate_90d":
            return f"{label}: {value:.0%}"
        if feature == "login_trend":
            return f"{label}: {value:.1f} veces".replace(".", ",")
        if feature == "csat_mean":
            return f"{label}: {value:.1f}".replace(".", ",")
        return f"{label}: {value:,.0f}".replace(",", ".")
    return f"{label}: {value}"


def top_factors(shap_values: np.ndarray, X: pd.DataFrame, k: int = 3) -> pd.DataFrame:
    """Para cada fila de X, los k factores que más suben su probabilidad, de mayor a menor. Vacío si hay menos de k."""
    shap_values = np.asarray(shap_values)
    if shap_values.shape != X.shape:
        raise ValueError(f"shap_values {shap_values.shape} no coincide con X {X.shape}")
    cols = list(X.columns)
    rows = []
    for i in range(len(X)):
        order = np.argsort(-shap_values[i])
        top = [j for j in order[:k] if shap_values[i, j] > 0]
        names = [describe(cols[j], X.iat[i, j]) for j in top]
        rows.append(names + [""] * (k - len(names)))
    return pd.DataFrame(rows, index=X.index, columns=[f"factor_{n + 1}" for n in range(k)])
