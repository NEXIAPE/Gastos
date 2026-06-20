"""
MODULE 7 - DASHBOARD (Streamlit)
================================

Panel interactivo de BETLAB AI:

  * KPIs: nº de picks, ROI acumulado, profit, win rate, bankroll.
  * Top Picks del día (ordenados por EV) con stake recomendado.
  * Historial de apuestas liquidadas.
  * Gráficos Plotly: EV por pick, distribución de mercados, curva de bankroll.

Ejecución:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite importar el paquete del proyecto al lanzar con streamlit.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from config import settings  # noqa: E402
from database import init_db, query_df  # noqa: E402
from models.roi import bankroll_curve, roi_metrics, settle_by_results  # noqa: E402
from models.value_bet import detect_value_bets, value_bets_dataframe  # noqa: E402
from services.data_ingestion import ingest  # noqa: E402

st.set_page_config(page_title="BETLAB AI", page_icon="⚽", layout="wide")

MARKET_LABELS = {"1X2": "1X2", "BTTS": "Ambos marcan", "OU_2.5": "O/U 2.5"}
SEL_LABELS = {"HOME": "Local", "DRAW": "Empate", "AWAY": "Visitante",
              "OVER": "Over", "UNDER": "Under", "YES": "Sí", "NO": "No"}


@st.cache_data(show_spinner=False)
def load_value_bets() -> pd.DataFrame:
    bets = detect_value_bets()
    return value_bets_dataframe(bets)


def pretty(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["Mercado"] = out["market"].map(lambda m: MARKET_LABELS.get(m, m))
    out["Selección"] = out["selection"].map(lambda s: SEL_LABELS.get(s, s))
    out["Prob. modelo"] = (out["model_prob"] * 100).round(1).astype(str) + "%"
    out["Prob. implícita"] = (out["implied_prob"] * 100).round(1).astype(str) + "%"
    out["EV"] = "+" + (out["ev"] * 100).round(1).astype(str) + "%"
    out["Stake"] = out["stake_amount"].round(2).astype(str) + "€"
    return out[["match", "Mercado", "Selección", "odd",
                "Prob. modelo", "Prob. implícita", "EV", "Stake"]].rename(
        columns={"match": "Partido", "odd": "Cuota"})


def main() -> None:
    init_db()

    st.title("⚽ BETLAB AI · Value Bet Detector")
    st.caption("Detección de apuestas de valor mediante Poisson + Expected Value + Kelly fraccionado.")

    # --- Sidebar de control -------------------------------------------------
    with st.sidebar:
        st.header("Control")
        st.write("**Modo:**", "Demo (sin claves)" if not (settings.has_football_key or settings.has_odds_key) else "API en vivo")
        st.metric("Bankroll", f"{settings.bankroll:.0f}€")
        st.metric("EV mínimo", f"{settings.min_ev:.0%}")
        st.metric("Fracción Kelly", f"{settings.kelly_fraction:.0%}")

        if st.button("🔄 Actualizar datos (ingesta)"):
            with st.spinner("Ingesta en curso..."):
                ingest()
            load_value_bets.clear()
            st.success("Datos actualizados.")
        if st.button("🧮 Recalcular value bets"):
            load_value_bets.clear()
            st.success("Recalculado.")
        if st.button("✅ Liquidar resultados"):
            n = settle_by_results()
            st.success(f"{n} apuestas liquidadas.")

    df = load_value_bets()
    metrics = roi_metrics()

    # --- KPIs ---------------------------------------------------------------
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Top Picks", len(df))
    c2.metric("ROI acumulado", f"{metrics['roi'] * 100:.1f}%")
    c3.metric("Profit", f"{metrics['profit']:.2f}€")
    c4.metric("Win rate", f"{metrics['win_rate'] * 100:.1f}%")
    c5.metric("Apuestas", metrics["bets"])

    tab_picks, tab_hist, tab_charts = st.tabs(["🎯 Top Picks", "📜 Historial", "📊 Gráficos"])

    # --- Top Picks ----------------------------------------------------------
    with tab_picks:
        st.subheader("Top Picks del día (EV > umbral)")
        if df.empty:
            st.info("No hay value bets. Pulsa «Actualizar datos» en la barra lateral.")
        else:
            st.dataframe(pretty(df), use_container_width=True, hide_index=True)

    # --- Historial ----------------------------------------------------------
    with tab_hist:
        st.subheader("Historial de apuestas")
        hist = query_df(
            "SELECT bl.placed_at AS Fecha, "
            "       th.name || ' vs ' || ta.name AS Partido, "
            "       bl.market AS Mercado, bl.selection AS Seleccion, "
            "       bl.odd AS Cuota, bl.stake_amount AS Stake, "
            "       bl.status AS Estado, bl.profit AS Profit "
            "FROM bet_log bl "
            "JOIN fixtures f ON f.id = bl.fixture_id "
            "JOIN teams th ON th.id = f.home_team_id "
            "JOIN teams ta ON ta.id = f.away_team_id "
            "ORDER BY bl.placed_at DESC"
        )
        if hist.empty:
            st.info("Aún no hay apuestas registradas.")
        else:
            st.dataframe(hist, use_container_width=True, hide_index=True)

    # --- Gráficos -----------------------------------------------------------
    with tab_charts:
        if df.empty:
            st.info("Sin datos para graficar.")
        else:
            colA, colB = st.columns(2)
            with colA:
                st.markdown("**EV por pick**")
                top = df.head(15).copy()
                top["label"] = top["match"] + " · " + top["selection"]
                fig = px.bar(top, x="ev", y="label", orientation="h",
                             color="ev", color_continuous_scale="Greens",
                             labels={"ev": "Expected Value", "label": ""})
                fig.update_layout(height=420, coloraxis_showscale=False)
                st.plotly_chart(fig, use_container_width=True)
            with colB:
                st.markdown("**Distribución por mercado**")
                dist = df["market"].map(lambda m: MARKET_LABELS.get(m, m)).value_counts().reset_index()
                dist.columns = ["Mercado", "Picks"]
                fig2 = px.pie(dist, names="Mercado", values="Picks", hole=0.45)
                fig2.update_layout(height=420)
                st.plotly_chart(fig2, use_container_width=True)

            st.markdown("**Curva de bankroll**")
            curve = bankroll_curve(settings.bankroll)
            if curve.empty:
                st.info("La curva de bankroll aparecerá cuando liquides apuestas.")
            else:
                fig3 = px.line(curve, x="settled_at", y="bankroll", markers=True,
                               labels={"settled_at": "Fecha", "bankroll": "Bankroll (€)"})
                fig3.update_layout(height=360)
                st.plotly_chart(fig3, use_container_width=True)


main()
