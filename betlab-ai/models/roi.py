"""
BETLAB AI - Registro de resultados y ROI
========================================

Funciones para registrar apuestas en `bet_log`, liquidar su resultado
(WON/LOST/VOID) y calcular métricas históricas: profit, ROI, yield, tasa de
acierto y curva de bankroll.

ROI = beneficio_total / stake_total
"""

from __future__ import annotations

import pandas as pd

from database import query_df, session


def log_value_bets() -> int:
    """Crea entradas PENDING en bet_log para las value bets aún no registradas."""
    inserted = 0
    with session() as conn:
        rows = conn.execute(
            "SELECT vb.id, vb.fixture_id, f.league_id, vb.market, vb.selection, "
            "       vb.odd, vb.model_prob, vb.ev, vb.stake_amount "
            "FROM value_bets vb "
            "JOIN fixtures f ON f.id = vb.fixture_id "
            "LEFT JOIN bet_log bl ON bl.value_bet_id = vb.id "
            "WHERE bl.id IS NULL"
        ).fetchall()
        for r in rows:
            conn.execute(
                "INSERT INTO bet_log "
                "(value_bet_id, fixture_id, league_id, market, selection, odd, "
                " model_prob, ev, stake_amount) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (r["id"], r["fixture_id"], r["league_id"], r["market"], r["selection"],
                 r["odd"], r["model_prob"], r["ev"], r["stake_amount"]),
            )
            inserted += 1
    return inserted


def settle_bet(bet_id: int, status: str) -> None:
    """Liquida una apuesta. status ∈ {WON, LOST, VOID}."""
    status = status.upper()
    with session() as conn:
        row = conn.execute(
            "SELECT odd, stake_amount FROM bet_log WHERE id = ?", (bet_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"bet_log id {bet_id} no existe")
        stake = row["stake_amount"]
        odd = row["odd"]
        if status == "WON":
            profit = round(stake * (odd - 1.0), 2)
        elif status == "LOST":
            profit = round(-stake, 2)
        else:  # VOID
            profit = 0.0
        conn.execute(
            "UPDATE bet_log SET status = ?, profit = ?, settled_at = datetime('now') "
            "WHERE id = ?",
            (status, profit, bet_id),
        )


def settle_by_results() -> int:
    """
    Liquida automáticamente las apuestas pendientes cuyo fixture ya tiene
    marcador final (status FT). Cubre 1X2, OU_2.5 y BTTS.
    """
    settled = 0
    pending = query_df(
        "SELECT bl.id, bl.market, bl.selection, f.home_goals, f.away_goals "
        "FROM bet_log bl JOIN fixtures f ON f.id = bl.fixture_id "
        "WHERE bl.status = 'PENDING' AND f.home_goals IS NOT NULL"
    )
    for _, b in pending.iterrows():
        won = _evaluate(b["market"], b["selection"],
                        int(b["home_goals"]), int(b["away_goals"]))
        if won is None:
            continue
        settle_bet(int(b["id"]), "WON" if won else "LOST")
        settled += 1
    return settled


def _evaluate(market: str, selection: str, hg: int, ag: int) -> bool | None:
    total = hg + ag
    if market == "1X2":
        if selection == "HOME":
            return hg > ag
        if selection == "DRAW":
            return hg == ag
        if selection == "AWAY":
            return ag > hg
    if market.startswith("OU_"):
        line = float(market.split("_", 1)[1])
        if selection == "OVER":
            return total > line
        if selection == "UNDER":
            return total < line
    if market == "BTTS":
        both = hg > 0 and ag > 0
        return both if selection == "YES" else (not both)
    return None


def roi_metrics() -> dict[str, float]:
    """Métricas agregadas sobre apuestas liquidadas."""
    df = query_df(
        "SELECT stake_amount, profit, status FROM bet_log "
        "WHERE status IN ('WON', 'LOST', 'VOID')"
    )
    if df.empty:
        return {"bets": 0, "staked": 0.0, "profit": 0.0,
                "roi": 0.0, "win_rate": 0.0}
    staked = float(df["stake_amount"].sum())
    profit = float(df["profit"].sum())
    decided = df[df["status"].isin(["WON", "LOST"])]
    win_rate = (df["status"] == "WON").sum() / len(decided) if len(decided) else 0.0
    return {
        "bets": int(len(df)),
        "staked": round(staked, 2),
        "profit": round(profit, 2),
        "roi": round(profit / staked, 4) if staked else 0.0,
        "win_rate": round(float(win_rate), 4),
    }


def bankroll_curve(starting_bankroll: float = 1000.0) -> pd.DataFrame:
    """Evolución acumulada del bankroll a lo largo de las apuestas liquidadas."""
    df = query_df(
        "SELECT settled_at, profit FROM bet_log "
        "WHERE status IN ('WON', 'LOST', 'VOID') AND settled_at IS NOT NULL "
        "ORDER BY settled_at"
    )
    if df.empty:
        return pd.DataFrame({"settled_at": [], "bankroll": []})
    df["bankroll"] = starting_bankroll + df["profit"].cumsum()
    return df
