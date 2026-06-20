"""
MODULE 1 - PERFORMANCE TRACKER
==============================

Registro y análisis del rendimiento histórico de las apuestas (bet_log).

Cada apuesta liquidada guarda: fecha, liga, partido, mercado, cuota,
probabilidad estimada, EV, stake, resultado y ganancia/pérdida.

Métricas:
  * Profit total
  * ROI    = profit / capital inicial
  * Yield  = profit / importe total apostado (turnover)
  * Hit Rate (aciertos / apuestas decididas)
  * Drawdown máximo (caída pico-valle de la curva de bankroll)
  * Profit por mercado
  * Profit por liga

También expone DataFrames listos para graficar (curva de bankroll, barras).
"""

from __future__ import annotations

import pandas as pd

from config import settings
from database import query_df


def _settled() -> pd.DataFrame:
    return query_df(
        "SELECT bl.settled_at, bl.placed_at, bl.league_id, bl.market, bl.selection, "
        "       bl.odd, bl.model_prob, bl.ev, bl.stake_amount, bl.status, bl.profit, "
        "       lg.name AS league, "
        "       th.name || ' vs ' || ta.name AS match "
        "FROM bet_log bl "
        "LEFT JOIN leagues lg ON lg.id = bl.league_id "
        "LEFT JOIN fixtures f ON f.id = bl.fixture_id "
        "LEFT JOIN teams th ON th.id = f.home_team_id "
        "LEFT JOIN teams ta ON ta.id = f.away_team_id "
        "WHERE bl.status IN ('WON','LOST','VOID') "
        "ORDER BY bl.settled_at, bl.id"
    )


def metrics(initial_bankroll: float | None = None) -> dict[str, float]:
    """Métricas agregadas del track record."""
    initial = settings.bankroll if initial_bankroll is None else initial_bankroll
    df = _settled()
    if df.empty:
        return {"bets": 0, "staked": 0.0, "profit": 0.0, "roi": 0.0,
                "yield": 0.0, "hit_rate": 0.0, "max_drawdown": 0.0}

    staked = float(df["stake_amount"].sum())
    profit = float(df["profit"].sum())
    decided = df[df["status"].isin(["WON", "LOST"])]
    hit_rate = (df["status"] == "WON").sum() / len(decided) if len(decided) else 0.0

    # Drawdown máximo sobre la curva de bankroll.
    equity = initial + df["profit"].cumsum()
    running_peak = equity.cummax()
    drawdowns = (running_peak - equity) / running_peak
    max_dd = float(drawdowns.max()) if not drawdowns.empty else 0.0

    return {
        "bets": int(len(df)),
        "staked": round(staked, 2),
        "profit": round(profit, 2),
        "roi": round(profit / initial, 4) if initial else 0.0,
        "yield": round(profit / staked, 4) if staked else 0.0,
        "hit_rate": round(float(hit_rate), 4),
        "max_drawdown": round(max_dd, 4),
    }


def profit_by_market() -> pd.DataFrame:
    df = _settled()
    if df.empty:
        return pd.DataFrame(columns=["market", "profit", "bets", "yield"])
    g = df.groupby("market").agg(
        profit=("profit", "sum"),
        staked=("stake_amount", "sum"),
        bets=("profit", "count"),
    ).reset_index()
    g["yield"] = (g["profit"] / g["staked"]).round(4)
    g["profit"] = g["profit"].round(2)
    return g[["market", "profit", "bets", "yield"]].sort_values("profit", ascending=False)


def profit_by_league() -> pd.DataFrame:
    df = _settled()
    if df.empty:
        return pd.DataFrame(columns=["league", "profit", "bets", "yield"])
    g = df.groupby("league").agg(
        profit=("profit", "sum"),
        staked=("stake_amount", "sum"),
        bets=("profit", "count"),
    ).reset_index()
    g["yield"] = (g["profit"] / g["staked"]).round(4)
    g["profit"] = g["profit"].round(2)
    return g[["league", "profit", "bets", "yield"]].sort_values("profit", ascending=False)


def bankroll_curve(initial_bankroll: float | None = None) -> pd.DataFrame:
    """Curva de bankroll a lo largo del tiempo (para graficar)."""
    initial = settings.bankroll if initial_bankroll is None else initial_bankroll
    df = _settled()
    if df.empty:
        return pd.DataFrame({"settled_at": [], "bankroll": []})
    out = df[["settled_at", "profit"]].copy()
    out["bankroll"] = initial + out["profit"].cumsum()
    return out[["settled_at", "bankroll"]]


def ledger() -> pd.DataFrame:
    """Registro completo (para la tabla del Performance Tracker)."""
    df = _settled()
    if df.empty:
        return df
    return df[["settled_at", "league", "match", "market", "selection", "odd",
               "model_prob", "ev", "stake_amount", "status", "profit"]]
