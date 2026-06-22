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


def _store():
    """Devuelve el módulo Supabase si está activo; si no, None (usa SQLite)."""
    try:
        from services import supabase_store as sb
        return sb if sb.enabled() else None
    except Exception:
        return None


def get_deposit(user: str = "default") -> float:
    """Capital inicial (depósito) del usuario para su traza."""
    sb = _store()
    if sb:
        return sb.get_deposit(user)
    df = query_df("SELECT value FROM app_settings WHERE key = ?", [f"deposit:{user}"])
    if df.empty:
        return 0.0
    try:
        return float(df["value"].iloc[0])
    except (ValueError, TypeError):
        return 0.0


def set_deposit(amount: float, user: str = "default") -> None:
    sb = _store()
    if sb:
        sb.set_deposit(user, amount)
        return
    with session() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (f"deposit:{user}", str(float(amount))))


def log_manual_bet(description: str, odd: float, stake: float,
                   market: str = "MANUAL", selection: str = "-",
                   user: str = "default") -> int:
    """Registra una apuesta cargada a mano por el usuario (queda PENDING)."""
    sb = _store()
    if sb:
        return sb.add_bet(user, description, float(odd), float(stake)) or 0
    with session() as conn:
        # Garantiza el partido "sentinela" (id 0) por si fue borrado en un reseed.
        conn.execute("INSERT OR IGNORE INTO teams (id, name) VALUES (0, 'Manual')")
        conn.execute(
            "INSERT OR IGNORE INTO fixtures (id, match_date, status, home_team_id, away_team_id) "
            "VALUES (0, '', 'MANUAL', 0, 0)")
        cur = conn.execute(
            "INSERT INTO bet_log (fixture_id, market, selection, odd, stake_amount, "
            " status, note, manual, user) VALUES (0, ?, ?, ?, ?, 'PENDING', ?, 1, ?)",
            (market, selection, float(odd), float(stake), description, user),
        )
        return int(cur.lastrowid)


def manual_bets(user: str = "default") -> "pd.DataFrame":
    """Apuestas manuales del usuario (su traza), más recientes primero."""
    cols = ["id", "note", "odd", "stake_amount", "status", "profit", "placed_at", "settled_at"]
    sb = _store()
    if sb:
        return pd.DataFrame(sb.list_bets(user), columns=cols)
    return query_df(
        "SELECT id, note, odd, stake_amount, status, profit, placed_at, settled_at "
        "FROM bet_log WHERE manual = 1 AND user = ? ORDER BY id DESC", [user]
    )


def manual_ledger(start: float = 0.0, user: str = "default") -> dict[str, float]:
    """Resumen de la traza manual del usuario: balance, pendiente, ROI."""
    sb = _store()
    if sb:
        df = pd.DataFrame(sb.list_bets(user),
                          columns=["id", "note", "odd", "stake_amount",
                                   "status", "profit", "placed_at", "settled_at"])
    else:
        df = query_df(
            "SELECT status, stake_amount, profit FROM bet_log "
            "WHERE manual = 1 AND user = ?", [user])
    if df.empty:
        return {"balance": round(start, 2), "pending_stake": 0.0, "staked": 0.0,
                "profit": 0.0, "roi": 0.0, "won": 0, "lost": 0, "pending": 0}
    settled = df[df["status"].isin(["WON", "LOST", "VOID"])]
    staked = float(settled["stake_amount"].sum())
    profit = float(df["profit"].sum())
    pending = df[df["status"] == "PENDING"]
    return {
        "balance": round(start + profit, 2),
        "pending_stake": round(float(pending["stake_amount"].sum()), 2),
        "staked": round(staked, 2),
        "profit": round(profit, 2),
        "roi": round(profit / staked, 4) if staked else 0.0,
        "won": int((df["status"] == "WON").sum()),
        "lost": int((df["status"] == "LOST").sum()),
        "pending": int(len(pending)),
    }


def delete_bet(bet_id: int) -> None:
    """Elimina una apuesta del registro."""
    sb = _store()
    if sb:
        sb.delete_bet(bet_id)
        return
    with session() as conn:
        conn.execute("DELETE FROM bet_log WHERE id = ?", (bet_id,))


def update_bet(bet_id: int, odd: float | None = None, stake: float | None = None,
               note: str | None = None) -> None:
    """Edita cuota/stake/descripción de una apuesta y recalcula su ganancia
    si ya estaba resuelta."""
    sb = _store()
    if sb:
        sb.update_bet(bet_id, odd if odd is not None else 0,
                      stake if stake is not None else 0, note)
        return
    with session() as conn:
        row = conn.execute(
            "SELECT odd, stake_amount, status FROM bet_log WHERE id = ?", (bet_id,)
        ).fetchone()
        if row is None:
            return
        new_odd = float(odd) if odd is not None else row["odd"]
        new_stake = float(stake) if stake is not None else row["stake_amount"]
        if row["status"] == "WON":
            profit = round(new_stake * (new_odd - 1.0), 2)
        elif row["status"] == "LOST":
            profit = round(-new_stake, 2)
        else:
            profit = 0.0
        if note is not None:
            conn.execute(
                "UPDATE bet_log SET odd=?, stake_amount=?, note=?, profit=? WHERE id=?",
                (new_odd, new_stake, note, profit, bet_id))
        else:
            conn.execute(
                "UPDATE bet_log SET odd=?, stake_amount=?, profit=? WHERE id=?",
                (new_odd, new_stake, profit, bet_id))


def set_bet_status(bet_id: int, status: str) -> None:
    """Cambia el estado de una apuesta (incluye volver a PENDIENTE)."""
    status = status.upper()
    sb = _store()
    if sb:
        sb.set_status(bet_id, status)
        return
    if status == "PENDING":
        with session() as conn:
            conn.execute(
                "UPDATE bet_log SET status='PENDING', profit=0, settled_at=NULL WHERE id=?",
                (bet_id,))
    else:
        settle_bet(bet_id, status)


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
        "WHERE status IN ('WON', 'LOST', 'VOID') AND manual = 0"
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
        "  AND manual = 0 "
        "ORDER BY settled_at"
    )
    if df.empty:
        return pd.DataFrame({"settled_at": [], "bankroll": []})
    df["bankroll"] = starting_bankroll + df["profit"].cumsum()
    return df
