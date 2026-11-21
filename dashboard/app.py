"""Dashboard de la campaña de retención de Conecta+ (bonus de la prueba).

Lee solo `dashboard/clientes_dashboard.csv`, que exporta la sección 7 de `solucion.ipynb`, y recalcula la decisión de
contacto con las mismas funciones de `conecta/business.py`. Uso: streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from conecta.business import CONTACT_COST, EFFECTIVENESS, PRICES, decide_contact, expected_value, threshold  # noqa: E402

DATA_PATH = Path(__file__).with_name("clientes_dashboard.csv")
PLANS = ["Basico", "Estandar", "Premium", "Familiar"]
PLATFORMS = {"android": "Android", "ios": "iOS", "web": "Web"}
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#a3a29c"

st.set_page_config(page_title="Conecta+ · Retención", page_icon="📞", layout="wide")


@st.cache_data
def load_clients() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    df["plataforma"] = df["plataforma"].map(PLATFORMS).fillna(df["plataforma"])
    df["en_proceso"] = df["en_proceso"].astype(bool)
    df["usa_520"] = df["usa_520"].astype(bool)
    df[["factor_1", "factor_2", "factor_3"]] = df[["factor_1", "factor_2", "factor_3"]].fillna("")
    return df


def decide(df: pd.DataFrame, effectiveness: float, cost: float) -> pd.DataFrame:
    """La regla del notebook: contactar si el valor esperado es positivo, salvo a quien ya está en proceso de baja."""
    out = df.copy()
    out["valor"] = expected_value(out["probabilidad"], out["plan"], cost, effectiveness).to_numpy()
    rule = decide_contact(out["probabilidad"], out["plan"], cost, effectiveness).to_numpy().astype(bool)
    out["llamar"] = rule & ~out["en_proceso"].to_numpy()
    out["decision"] = np.select([out["en_proceso"], out["llamar"]], ["En proceso de baja", "Llamar"], "No llamar")
    out["riesgo"] = pd.cut(out["probabilidad"], [-0.01, 0.15, 0.30, 1.01], labels=["Bajo", "Medio", "Alto"]).astype(str)
    return out


def money(v: float) -> str:
    sign = "−" if v < 0 else ""
    v = abs(v)
    return f"{sign}{v / 1e6:,.1f} M".replace(".", ",") if v >= 1e6 else f"{sign}{v:,.0f}".replace(",", ".")


def risk_badge(level: str) -> str:
    color = {"Alto": "red", "Medio": "orange", "Bajo": "gray"}[level]
    return f":{color}-badge[Riesgo {level.lower()}]"


def decision_badge(decision: str) -> str:
    color = {"Llamar": "blue", "No llamar": "gray", "En proceso de baja": "violet"}[decision]
    return f":{color}-badge[{decision}]"


clients = load_clients()

# ------------------------------------------------------------------------------------------- barra lateral
with st.sidebar:
    st.header("Supuestos")
    effectiveness = st.slider("Efectividad de la llamada", 0.05, 0.80, EFFECTIVENESS, 0.05, format="%.2f",
                              help="Fracción de los clientes que se iban a ir y que la llamada retiene. El enunciado supone 0,40.")
    cost = st.number_input("Costo por llamada (COP)", 5_000, 100_000, CONTACT_COST, 5_000)
    st.caption("Cambian el umbral de cada plan y, con él, la lista. El notebook usa 0,40 y 25.000.")
    st.header("Filtros")
    plans = st.multiselect("Plan", PLANS, default=PLANS)
    segments = st.multiselect("Segmento", sorted(clients["segmento"].unique()), default=sorted(clients["segmento"].unique()))
    platforms = st.multiselect("Plataforma", list(PLATFORMS.values()), default=list(PLATFORMS.values()))
    st.divider()
    st.caption("Puntaje al 31-dic-2025 del modelo final (LightGBM). Datos sin ciudad, edad ni textos de tickets. "
               "Detalle en `solucion.ipynb`.")

scored = decide(clients, effectiveness, cost)
base = decide(clients, EFFECTIVENESS, CONTACT_COST)
view = scored[scored["plan"].isin(plans) & scored["segmento"].isin(segments) & scored["plataforma"].isin(platforms)]
base_view = base.loc[view.index]

# ------------------------------------------------------------------------------------------- encabezado y KPIs
st.title("Campaña de retención · enero de 2026")
st.caption("A quién llamar este mes, cuánto se espera ganar y por qué cada cliente está en riesgo.")

calls = view["llamar"]
net = view.loc[calls, "valor"].sum()
base_calls, base_net = base_view["llamar"], base_view.loc[base_view["llamar"], "valor"].sum()
changed = effectiveness != EFFECTIVENESS or cost != CONTACT_COST

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Clientes activos", f"{len(view):,}".replace(",", "."), border=True)
k2.metric("A llamar", f"{calls.sum():,}".replace(",", "."), delta=int(calls.sum() - base_calls.sum()) if changed else None,
          border=True, help="Valor esperado positivo y fuera del proceso de baja.")
k3.metric("Costo de las llamadas", money(calls.sum() * cost), border=True)
k4.metric("Valor esperado neto", money(net), delta=money(net - base_net) if changed else None, border=True,
          help="Ya descuenta el costo de las llamadas.")
k5.metric("Probabilidad media", f"{view['probabilidad'].mean():.1%}".replace(".", ","), border=True,
          help="Churn a 90 días esperado. El de los últimos cortes conocidos fue 16,2 %.")
if changed:
    st.caption(f"Los cambios se comparan con los supuestos del enunciado (efectividad 0,40, costo {CONTACT_COST:,} COP)."
               .replace(",", "."))

tab_list, tab_summary, tab_rule = st.tabs(["Lista de contacto", "Resumen", "Cómo se decide"])

# ------------------------------------------------------------------------------------------- lista de contacto
with tab_list:
    quick = st.segmented_control(
        "Mostrar", ["A llamar", "Todos", "En proceso de baja", "Usan la app 5.2.0"], default="A llamar",
        label_visibility="collapsed")
    masks = {"A llamar": view["llamar"], "Todos": pd.Series(True, index=view.index),
             "En proceso de baja": view["en_proceso"], "Usan la app 5.2.0": view["usa_520"]}
    shown = view[masks.get(quick or "Todos")].sort_values(["valor", "probabilidad"], ascending=False)

    left, right = st.columns([3, 2], gap="large")
    with left:
        search = st.text_input("Buscar cliente", placeholder="Número de cliente, por ejemplo 10000",
                               label_visibility="collapsed")
        if search.strip().isdigit():
            shown = shown[shown["cliente_id"].astype(str).str.startswith(search.strip())]
        table = shown[["cliente_id", "plan", "segmento", "plataforma", "probabilidad", "riesgo", "valor", "decision",
                       "factor_1"]].rename(columns={"cliente_id": "cliente", "valor": "valor esperado",
                                                    "decision": "decisión", "factor_1": "motivo principal"})
        event = st.dataframe(
            table, hide_index=True, width="stretch", height=520, on_select="rerun",
            selection_mode="single-row", key="clients_table",
            column_config={
                "cliente": st.column_config.NumberColumn(format="%d"),
                "probabilidad": st.column_config.ProgressColumn("riesgo de baja", format="percent", min_value=0,
                                                                max_value=1),
                "riesgo": st.column_config.TextColumn("nivel"),
                "valor esperado": st.column_config.NumberColumn(format="$ %d"),
            })
        st.caption(f"{len(shown):,} clientes, ordenados por valor esperado. Nivel de riesgo: alto desde 30 %, medio "
                   "desde 15 %. Selecciona una fila para ver su ficha.".replace(",", "."))
        st.download_button("Descargar esta lista (CSV)", shown.drop(columns=["riesgo"]).to_csv(index=False),
                           file_name="lista_contacto.csv", mime="text/csv")

    with right:
        rows = event.selection.rows if event is not None else []
        if shown.empty:
            st.info("No hay clientes con estos filtros.")
        else:
            c = shown.iloc[rows[0]] if rows else shown.iloc[0]
            with st.container(border=True):
                st.subheader(f"Cliente {c['cliente_id']}")
                st.markdown(f"{decision_badge(c['decision'])} {risk_badge(c['riesgo'])} "
                            f":gray-badge[{c['plan']}] :gray-badge[{c['segmento']}] :gray-badge[{c['plataforma']}]")
                m1, m2, m3 = st.columns(3)
                m1.metric("Riesgo de baja", f"{c['probabilidad']:.0%}")
                m2.metric("Umbral del plan", f"{threshold(c['plan'], cost, effectiveness):.0%}",
                          help="Probabilidad desde la cual llamar vale la pena con estos supuestos.")
                m3.metric("Valor esperado", money(c["valor"]))
                if c["decision"] == "En proceso de baja":
                    st.caption("Ya lo atiende el flujo de baja (llamada del equipo en los últimos 30 días o ticket de "
                               "cancelar en 90). Casi todos esos clientes se van igual, así que no se recomienda llamarlo.")
                elif c["decision"] == "Llamar":
                    st.caption("Su riesgo supera el umbral de su plan: con estos supuestos, la llamada se paga sola.")
                else:
                    st.caption("Su riesgo no alcanza el umbral de su plan: la llamada costaría más de lo que se espera "
                               "retener.")
                st.markdown("**Qué sube su riesgo**")
                factors = [f for f in c[["factor_1", "factor_2", "factor_3"]] if f]
                st.markdown("\n".join(f"{i}. {f}" for i, f in enumerate(factors, 1)) or "Ningún factor sube su riesgo.")
                st.caption("Las tres variables que más suben su probabilidad según SHAP, con su valor.")

# ------------------------------------------------------------------------------------------- resumen
with tab_summary:
    col_a, col_b = st.columns(2, gap="large")
    by_plan = (view.groupby("plan").agg(clientes=("cliente_id", "size"), llamar=("llamar", "sum"))
               .reindex([p for p in PLANS if p in plans]).reset_index())
    by_plan["umbral"] = [threshold(p, cost, effectiveness) for p in by_plan["plan"]]
    by_plan["% a llamar"] = by_plan["llamar"] / by_plan["clientes"]
    with col_a:
        st.markdown("**A quién se llama, por plan**")
        bars = alt.Chart(by_plan).mark_bar(color=BLUE, cornerRadiusEnd=3).encode(
            x=alt.X("% a llamar:Q", axis=alt.Axis(format="%", title=None), scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("plan:N", sort=PLANS, title=None),
            tooltip=["plan", "clientes", "llamar", alt.Tooltip("umbral:Q", format=".1%"),
                     alt.Tooltip("% a llamar:Q", format=".0%")])
        st.altair_chart(bars + bars.mark_text(align="left", dx=4).encode(text=alt.Text("% a llamar:Q", format=".0%")),
                        width="stretch")
        st.caption("Los planes caros tienen un umbral más bajo: retener a un cliente Familiar vale 2,5 veces lo que uno "
                   "Básico.")

    with col_b:
        st.markdown("**Motivos más frecuentes entre los clientes a llamar**")
        reasons = (view.loc[view["llamar"], "factor_1"].str.split(":").str[0].replace("", np.nan).dropna()
                   .value_counts().head(8).rename_axis("motivo").reset_index(name="clientes"))
        if reasons.empty:
            st.info("Nadie a llamar con estos supuestos y filtros.")
        else:
            reason_bars = alt.Chart(reasons).mark_bar(color=ORANGE, cornerRadiusEnd=3).encode(
                x=alt.X("clientes:Q", title=None), y=alt.Y("motivo:N", sort="-x", title=None),
                tooltip=["motivo", "clientes"])
            st.altair_chart(reason_bars + reason_bars.mark_text(align="left", dx=4).encode(text="clientes:Q"),
                            width="stretch")
            st.caption("El motivo principal de cada cliente es la variable que más sube su probabilidad.")

    st.markdown("**Cuánto depende el resultado de la efectividad**")
    grid = pd.DataFrame({"efectividad": np.round(np.arange(0.05, 0.801, 0.05), 2)})
    eligible = view[~view["en_proceso"]]
    grid["valor"] = [expected_value(eligible["probabilidad"], eligible["plan"], cost, e)
                     .where(lambda v: v > 0).sum() for e in grid["efectividad"]]
    grid["llamadas"] = [int(decide_contact(eligible["probabilidad"], eligible["plan"], cost, e).sum())
                        for e in grid["efectividad"]]
    line = alt.Chart(grid).mark_line(color=BLUE, point=True).encode(
        x=alt.X("efectividad:Q", axis=alt.Axis(format="%", title="efectividad de la llamada")),
        y=alt.Y("valor:Q", title="valor esperado neto (COP)"),
        tooltip=[alt.Tooltip("efectividad:Q", format=".0%"), "llamadas", alt.Tooltip("valor:Q", format=",.0f")])
    rule = alt.Chart(pd.DataFrame({"efectividad": [effectiveness]})).mark_rule(color=GREY, strokeDash=[4, 4]).encode(
        x="efectividad:Q")
    st.altair_chart(line + rule, width="stretch")
    st.caption("La línea punteada es la efectividad elegida. Las llamadas actuales del equipo, que llegan tarde, "
               "retienen cerca del 3 %: por eso se recomienda medir la efectividad real con un piloto antes de escalar.")

# ------------------------------------------------------------------------------------------- cómo se decide
with tab_rule:
    st.markdown(
        f"""
Por cada cliente, el modelo estima la probabilidad de que se vaya en los próximos 90 días. Llamarlo conviene si lo que se
espera retener supera el costo de la llamada:

**probabilidad × efectividad × 12 × precio del plan > costo de la llamada**

Con los supuestos de la barra lateral (efectividad {effectiveness:.0%}, costo {cost:,.0f} COP), el umbral de cada plan es:
""".replace(",", "."))
    st.dataframe(pd.DataFrame({"plan": PLANS, "precio mensual": [PRICES[p] for p in PLANS],
                               "umbral": [threshold(p, cost, effectiveness) for p in PLANS]}),
                 hide_index=True, column_config={
                     "precio mensual": st.column_config.NumberColumn(format="$ %d"),
                     "umbral": st.column_config.NumberColumn(format="percent")})
    st.markdown(
        """
- No se llama a quien ya está en proceso de baja (llamada del equipo en los últimos 30 días o ticket de cancelar en los
  últimos 90): lo atiende el flujo actual y casi todos se van igual.
- El valor esperado ya descuenta el costo de la llamada. Si es negativo, la llamada cuesta más de lo que se espera retener.
- La efectividad del 40 % es un supuesto del enunciado y es lo que más pesa en el resultado. El piloto con grupo de control
  propuesto en el memo sirve para reemplazarlo por la efectividad medida.
"""
    )
