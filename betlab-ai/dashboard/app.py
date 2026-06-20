"""
DASHBOARD (Streamlit) - BETLAB AI
=================================

Panel de control completo:

  * Estrategia diaria: Pick Premium, Top 5 y combinadas (C/D/E) con modo bankroll.
  * Performance Tracker: KPIs, curva de bankroll, profit por mercado y por liga.
  * League Analyzer: clasificación de ligas y ajuste de confianza.
  * Backtesting: comparación de variantes de modelo.
  * No Bet Engine: partidos descartados y su motivo.
  * Factores del Score de Confianza por pick.

Ejecución:  streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from config import settings  # noqa: E402
from database import init_db, query_df  # noqa: E402
from models.backtest import run_backtest  # noqa: E402
from models.bankroll import get_state  # noqa: E402
from models.league_analyzer import analyze as analyze_leagues  # noqa: E402
from models.performance import (  # noqa: E402
    bankroll_curve, ledger, metrics as perf_metrics,
    profit_by_league, profit_by_market,
)
from models.roi import settle_by_results  # noqa: E402
from models.strategies import build_strategies  # noqa: E402
from services.data_ingestion import ingest  # noqa: E402

st.set_page_config(page_title="BETLAB AI", page_icon="⚽", layout="wide")

SEL = {"HOME": "Local", "DRAW": "Empate", "AWAY": "Visitante", "OVER": "Over 2.5",
       "UNDER": "Under 2.5", "YES": "BTTS Sí", "NO": "BTTS No"}
MKT = {"1X2": "1X2", "BTTS": "BTTS", "OU_2.5": "O/U 2.5"}
FACTOR_LABELS = {
    "poisson": "Poisson", "xg": "xG", "elo": "Elo", "form5": "Forma 5",
    "form10": "Forma 10", "injuries": "Lesiones", "fatigue": "Fatiga",
    "home_perf": "Rend. local", "away_perf": "Rend. visitante", "h2h": "H2H",
    "odds_movement": "Mov. cuotas", "league_adj": "Ajuste liga",
}
MODE_COLOR = {"NORMAL": "🟢", "REDUCED": "🟡", "CONSERVATION": "🔴"}


@st.cache_data(show_spinner=False)
def load_strategies():
    # Refresca la clasificación de ligas para que la confianza incorpore el
    # ajuste por liga, igual que en el pipeline.
    analyze_leagues(initial_bankroll=settings.bankroll)
    return build_strategies()


def main() -> None:
    init_db()
    st.title("⚽ BETLAB AI · Sistema de Value Betting")
    st.caption("Poisson · xG · Elo · Confianza · Performance · Ligas · No-Bet · Bankroll · Backtesting")

    state = get_state()
    rep = load_strategies()
    perf = perf_metrics(settings.bankroll)

    # --- Sidebar ------------------------------------------------------------
    with st.sidebar:
        st.header("Bankroll Manager")
        st.metric("Bankroll", f"{state.current:.0f}€", f"{(state.current - state.initial):+.0f}€")
        st.write(f"**Modo:** {MODE_COLOR.get(state.mode,'')} {state.mode}")
        st.progress(min(1.0, max(0.0, 1 - state.drawdown)),
                    text=f"Drawdown {state.drawdown:.1%} (peak {state.peak:.0f}€)")
        st.caption(f"stake ×{state.stake_multiplier} · conf. mín. {state.min_confidence:.0f} · "
                   f"combinadas {'sí' if state.allow_parlays else 'NO'}")
        st.divider()
        if st.button("🔄 Actualizar datos"):
            with st.spinner("Ingesta..."):
                ingest()
            load_strategies.clear(); st.rerun()
        if st.button("🧮 Recalcular picks"):
            load_strategies.clear(); st.rerun()
        if st.button("✅ Liquidar resultados"):
            n = settle_by_results(); load_strategies.clear()
            st.success(f"{n} liquidadas"); st.rerun()
        if st.button("🧪 Ejecutar backtest"):
            with st.spinner("Backtesting..."):
                run_backtest()
            st.success("Backtest actualizado")

    # --- KPIs ---------------------------------------------------------------
    c = st.columns(6)
    c[0].metric("Picks elegibles", len(rep.pool))
    c[1].metric("ROI", f"{perf['roi'] * 100:.1f}%")
    c[2].metric("Yield", f"{perf['yield'] * 100:.1f}%")
    c[3].metric("Hit rate", f"{perf['hit_rate'] * 100:.0f}%")
    c[4].metric("Max DD", f"{perf['max_drawdown'] * 100:.0f}%")
    c[5].metric("Profit", f"{perf['profit']:.0f}€")

    tabs = st.tabs(["🎯 Estrategia", "📈 Performance", "🏆 Ligas",
                    "🧪 Backtest", "🚫 No Bet", "🧬 Factores"])

    with tabs[0]:
        _tab_strategy(rep, state)
    with tabs[1]:
        _tab_performance()
    with tabs[2]:
        _tab_leagues()
    with tabs[3]:
        _tab_backtest()
    with tabs[4]:
        _tab_nobet()
    with tabs[5]:
        _tab_factors(rep)


def _tab_strategy(rep, state) -> None:
    st.subheader("Estrategia diaria")
    if state.mode != "NORMAL":
        st.warning(f"Bankroll en modo **{state.mode}**: "
                   + ("stakes reducidos al 50%." if state.mode == "REDUCED"
                      else "solo picks confianza > 90, stake máx 1% y SIN combinadas."))

    # A) Pick premium
    if rep.premium:
        b = rep.premium
        st.markdown(f"### 🏅 A) Pick Premium del día")
        st.success(f"**{b.match}** · {MKT.get(b.market, b.market)} **{SEL.get(b.selection, b.selection)}**  \n"
                   f"Cuota **{b.odd}** · Prob **{b.model_prob:.0%}** · EV **+{b.ev:.1%}** · "
                   f"Confianza **{b.confidence:.0f}** [{b.tier}] · Stake **{b.stake_amount:.2f}€** · Riesgo {b.risk}")
    else:
        st.info("A) Pick Premium: no hay pick elegible hoy.")

    # B) Top 5
    st.markdown("### 📋 B) Top 5 Value Bets")
    if rep.top5:
        df = pd.DataFrame([{
            "Partido": b.match, "Mercado": MKT.get(b.market, b.market),
            "Selección": SEL.get(b.selection, b.selection), "Cuota": b.odd,
            "Prob": f"{b.model_prob:.0%}", "EV": f"+{b.ev:.1%}",
            "Confianza": int(b.confidence), "Tier": b.tier,
            "Stake": f"{b.stake_amount:.2f}€", "Riesgo": b.risk,
        } for b in rep.top5])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No hay value bets elegibles hoy.")

    # C/D/E) Combinadas
    st.markdown("### 🎰 Combinadas")
    if rep.parlays_blocked:
        st.error("Combinadas bloqueadas por el modo CONSERVACIÓN del bankroll.")
    elif not rep.has_combos:
        st.warning("**NO HAY COMBINADAS DE VALOR HOY.**")
    else:
        names = {"Conservadora": "C) Conservadora (máx 2)",
                 "Moderada": "D) Moderada (máx 3)", "Agresiva": "E) Agresiva (máx 5)"}
        cols = st.columns(len(rep.parlays))
        for col, p in zip(cols, rep.parlays):
            with col:
                st.markdown(f"**{names.get(p.name, p.name)}**")
                for leg in p.legs:
                    st.caption(f"• {leg.match} · {MKT.get(leg.market, leg.market)} "
                               f"{SEL.get(leg.selection, leg.selection)} @ {leg.odd}")
                st.metric("Cuota total", f"{p.total_odd:.2f}",
                          f"EV +{p.ev:.0%} · {p.risk}")
                st.caption(f"Prob. conjunta {p.joint_prob:.1%}")


def _tab_performance() -> None:
    st.subheader("Performance Tracker")
    curve = bankroll_curve(settings.bankroll)
    if curve.empty:
        st.info("Sin apuestas liquidadas todavía.")
        return
    fig = px.area(curve, x="settled_at", y="bankroll",
                  labels={"settled_at": "Fecha", "bankroll": "Bankroll (€)"})
    fig.update_layout(height=320)
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Profit por mercado**")
        pm = profit_by_market()
        fig1 = px.bar(pm, x="market", y="profit", color="profit",
                      color_continuous_scale="RdYlGn", text="profit")
        fig1.update_layout(height=300, coloraxis_showscale=False)
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        st.markdown("**Profit por liga**")
        pl = profit_by_league()
        fig2 = px.bar(pl, x="league", y="profit", color="profit",
                      color_continuous_scale="RdYlGn", text="profit")
        fig2.update_layout(height=300, coloraxis_showscale=False)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("**Registro de apuestas (últimas 200)**")
    st.dataframe(ledger().tail(200), use_container_width=True, hide_index=True)


def _tab_leagues() -> None:
    st.subheader("League Analyzer")
    df = analyze_leagues(initial_bankroll=settings.bankroll)
    if df.empty:
        st.info("Sin historial para clasificar ligas.")
        return
    show = df.rename(columns={
        "league": "Liga", "tier": "Clasificación", "yield": "Yield",
        "roi": "ROI", "accuracy": "Accuracy", "bets": "Bets",
        "confidence_multiplier": "Ajuste conf.", "ev_hist": "EV hist."})
    show["Yield"] = (show["Yield"] * 100).round(1).astype(str) + "%"
    show["ROI"] = (show["ROI"] * 100).round(1).astype(str) + "%"
    show["Accuracy"] = (show["Accuracy"] * 100).round(0).astype(str) + "%"
    st.dataframe(show[["Liga", "Clasificación", "Yield", "ROI", "Accuracy",
                       "Bets", "Ajuste conf."]], use_container_width=True, hide_index=True)
    st.caption("El multiplicador ajusta la confianza de las predicciones futuras "
               "según el desempeño histórico de cada liga.")


def _tab_backtest() -> None:
    st.subheader("Backtesting (out-of-sample, ~2 años)")
    df = query_df("SELECT model, accuracy, roi, yield, drawdown, profit, bets "
                  "FROM backtest_results ORDER BY profit DESC")
    if df.empty:
        st.info("Pulsa «Ejecutar backtest» en la barra lateral.")
        return
    best = df.iloc[0]["model"]
    st.success(f"Modelo más rentable (auto-seleccionado): **{best}**")
    show = df.copy()
    for col in ("accuracy", "roi", "yield", "drawdown"):
        show[col] = (show[col] * 100).round(1).astype(str) + "%"
    show["profit"] = show["profit"].round(2).astype(str) + "€"
    show = show.rename(columns={"model": "Modelo", "accuracy": "Accuracy", "roi": "ROI",
                                "yield": "Yield", "drawdown": "Max DD", "profit": "Profit",
                                "bets": "Bets"})
    st.dataframe(show, use_container_width=True, hide_index=True)
    fig = px.bar(df, x="model", y="profit", color="profit",
                 color_continuous_scale="Greens", text="profit")
    fig.update_layout(height=320, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)


def _tab_nobet() -> None:
    st.subheader("No Bet Engine · partidos descartados")
    df = query_df("SELECT match AS Partido, reasons AS Motivo FROM no_bets ORDER BY id")
    if df.empty:
        st.success("Ningún partido descartado hoy.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("Reglas: bajas importantes · rotaciones · amistoso · info insuficiente · "
               "EV<5% · diferencia de probabilidades <3%.")


def _tab_factors(rep) -> None:
    st.subheader("Score de Confianza · desglose de factores")
    bets = rep.pool or rep.by_confidence[:10]
    if not bets:
        st.info("Sin picks para desglosar.")
        return
    labels = [f"{b.match} · {SEL.get(b.selection, b.selection)} "
              f"({b.confidence:.0f} · {b.tier})" for b in bets]
    idx = st.selectbox("Pick", range(len(labels)), format_func=lambda i: labels[i])
    fb = bets[idx].factors
    if not fb:
        st.info("Sin factores aplicables.")
        return
    fdf = pd.DataFrame({"Factor": [FACTOR_LABELS.get(k, k) for k in fb],
                        "Aporte": list(fb.values())}).sort_values("Aporte")
    fig = px.bar(fdf, x="Aporte", y="Factor", orientation="h", range_x=[0, 100],
                 color="Aporte", color_continuous_scale="RdYlGn")
    fig.add_vline(x=50, line_dash="dot", line_color="gray")
    fig.update_layout(height=420, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Cada factor aporta 0-100 a favor de la selección (>50 apoya la apuesta). "
               "El score es su media ponderada, ajustada por la liga.")


main()
