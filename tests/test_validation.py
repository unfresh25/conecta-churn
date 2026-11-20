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
