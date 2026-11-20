import pandas as pd

from conecta.data import clean_age, clean_events, clean_invoices, normalize_city


def test_normalize_city_all_spellings():
    raw = pd.Series(["BOGOTA", "bogota d.c.", "Bogota D.C.", "Bogotá", "medellin", "MEDELLIN", "Medellín",
                     "Cali", "CALI", "Santiago de Cali", "B/quilla", "BARRANQUILLA", "Barranquilla",
                     "Bucaramanga", "BUCARAMANGA", "Pereira", "PEREIRA"])
    assert set(normalize_city(raw)) == {"Bogotá", "Medellín", "Cali", "Barranquilla", "Bucaramanga", "Pereira"}


def test_normalize_city_unknown_is_nan():
    assert normalize_city(pd.Series(["Tunja"])).isna().all()


def test_clean_age():
    out = clean_age(pd.Series([0, 999, 17, 18, 45, 100, 101]))
    assert out.isna().tolist() == [True, True, True, False, False, False, True]


def test_clean_invoices_reload_vs_double_charge(invoices_df):
    out = clean_invoices(invoices_df)
    sept = out[out["periodo"] == "2025-09"].sort_values("factura_id")
    # factura_id 1 cargada dos veces -> una sola fila, la de fecha_carga más temprana
    assert (out["factura_id"] == 1).sum() == 1
    assert out.loc[out["factura_id"] == 1, "fecha_carga"].iloc[0] == pd.Timestamp("2025-09-02 02:00:00")
    # factura_id 2 (mismo cliente, periodo y suscripción, id distinto) -> cobro duplicado real
    assert sept["is_duplicate_charge"].tolist() == [False, True]
    assert len(out) == 3


def test_clean_events_dedup_and_local_date(events_df):
    out = clean_events(events_df)
    assert len(out) == 2
    # 2025-10-01T04:30Z es 2025-09-30 23:30 en Bogotá
    assert out.loc[out["event_id"] == "e2", "local_date"].iloc[0] == pd.Timestamp("2025-09-30")
