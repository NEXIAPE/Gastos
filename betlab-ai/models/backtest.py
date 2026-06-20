"""
MODULE 7 - BACKTESTING
======================

Simula la estrategia de valor sobre el histórico (>= ~2 años de datos demo) y
compara tres variantes de modelo, cada una añadiendo una señal:

  * "Poisson"           : ratings de ataque/defensa a partir de goles.
  * "Poisson+Elo"       : + ajuste de lambdas por diferencia de Elo.
  * "Poisson+Elo+xG"    : + ratings mezclando goles con xG.

Validación walk-forward simple: se entrena con el primer tramo del histórico y
se apuesta sobre el tramo final (out-of-sample), usando la cuota de cierre
('Closing') guardada y liquidando con el resultado real.

Métricas por variante: Accuracy, ROI, Yield, Drawdown, Profit. Selecciona
automáticamente la variante más rentable (mayor profit) y la persiste en
`backtest_results`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import settings
from database import query_df, session
from models.kelly import recommend_stake
from models.poisson_model import PoissonModel

HOME_ADV = 1.25
AWAY_FACTOR = 0.9
TRAIN_FRACTION = 0.7
VARIANTS = ("Poisson", "Poisson+Elo", "Poisson+Elo+xG")


@dataclass
class BacktestResult:
    model: str
    accuracy: float
    roi: float
    yield_: float
    drawdown: float
    profit: float
    bets: int


# --- carga de datos ---------------------------------------------------------
def _load_history() -> pd.DataFrame:
    df = query_df(
        "SELECT f.id, f.match_date, f.home_team_id, f.away_team_id, "
        "       f.home_goals, f.away_goals, "
        "       sh.xg AS home_xg, sa.xg AS away_xg "
        "FROM fixtures f "
        "LEFT JOIN match_stats sh ON sh.fixture_id=f.id AND sh.team_id=f.home_team_id "
        "LEFT JOIN match_stats sa ON sa.fixture_id=f.id AND sa.team_id=f.away_team_id "
        "WHERE f.home_goals IS NOT NULL "
        "ORDER BY f.match_date, f.id"
    )
    return df


def _closing_odds() -> dict[tuple[int, str, str], float]:
    df = query_df(
        "SELECT fixture_id, market, selection, odd FROM odds WHERE bookmaker='Closing'"
    )
    return {(int(r.fixture_id), r.market, r.selection): float(r.odd)
            for r in df.itertuples()}


# --- ratings y elo sobre un subconjunto -------------------------------------
def _ratings(train: pd.DataFrame, use_xg: bool) -> tuple[dict, dict, float]:
    """Devuelve (attack, defense, league_avg) por equipo a partir del train."""
    df = train.copy()
    if use_xg:
        df["home_eff"] = 0.6 * df["home_goals"] + 0.4 * df["home_xg"].fillna(df["home_goals"])
        df["away_eff"] = 0.6 * df["away_goals"] + 0.4 * df["away_xg"].fillna(df["away_goals"])
    else:
        df["home_eff"] = df["home_goals"]
        df["away_eff"] = df["away_goals"]

    league_avg = (df["home_eff"].mean() + df["away_eff"].mean()) / 2 or 1.4
    attack, defense = {}, {}
    team_ids = pd.unique(df[["home_team_id", "away_team_id"]].values.ravel())
    for tid in team_ids:
        home = df[df["home_team_id"] == tid]
        away = df[df["away_team_id"] == tid]
        n = len(home) + len(away)
        if n == 0:
            continue
        scored = home["home_eff"].sum() + away["away_eff"].sum()
        conceded = home["away_eff"].sum() + away["home_eff"].sum()
        attack[int(tid)] = (scored / n) / league_avg
        defense[int(tid)] = (conceded / n) / league_avg
    return attack, defense, float(league_avg)


def _elo(train: pd.DataFrame) -> dict[int, float]:
    ratings: dict[int, float] = {}
    K, HFA, BASE = 20.0, 65.0, 1500.0
    for _, m in train.iterrows():
        h, a = int(m["home_team_id"]), int(m["away_team_id"])
        rh, ra = ratings.get(h, BASE), ratings.get(a, BASE)
        exp_h = 1.0 / (1.0 + 10 ** ((ra - (rh + HFA)) / 400.0))
        hg, ag = int(m["home_goals"]), int(m["away_goals"])
        s_h = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        gd = abs(hg - ag)
        g = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
        delta = K * g * (s_h - exp_h)
        ratings[h], ratings[a] = rh + delta, ra - delta
    return ratings


# --- simulación de una variante ---------------------------------------------
def _simulate(variant: str, train: pd.DataFrame, test: pd.DataFrame,
              odds: dict) -> BacktestResult:
    use_xg = "xG" in variant
    use_elo = "Elo" in variant
    attack, defense, league_avg = _ratings(train, use_xg)
    elo = _elo(train) if use_elo else {}

    bankroll = settings.bankroll
    peak = bankroll
    max_dd = 0.0
    staked = profit = 0.0
    won = decided = bets = 0

    for _, m in test.iterrows():
        h, a = int(m["home_team_id"]), int(m["away_team_id"])
        if h not in attack or a not in attack:
            continue
        lam_h = league_avg * attack[h] * defense.get(a, 1.0) * HOME_ADV
        lam_a = league_avg * attack[a] * defense.get(h, 1.0) * AWAY_FACTOR
        if use_elo and h in elo and a in elo:
            tilt = (10 ** ((elo[h] - elo[a]) / 400.0)) ** 0.15
            lam_h *= tilt
            lam_a /= tilt
        lam_h, lam_a = max(0.1, lam_h), max(0.1, lam_a)

        model = PoissonModel(lam_h, lam_a)
        candidates = _candidates(model, int(m["id"]), odds)
        if not candidates:
            continue
        market, selection, p, odd, ev = max(candidates, key=lambda c: c[4])
        if ev <= settings.min_ev:
            continue

        stake = recommend_stake(p, odd, bankroll=bankroll).stake_amount
        if stake <= 0:
            continue
        result = _settle(market, selection, int(m["home_goals"]), int(m["away_goals"]))
        if result is None:
            continue

        bets += 1
        decided += 1
        staked += stake
        pl = stake * (odd - 1.0) if result else -stake
        profit += pl
        bankroll += pl
        won += 1 if result else 0
        peak = max(peak, bankroll)
        max_dd = max(max_dd, (peak - bankroll) / peak if peak > 0 else 0.0)

    return BacktestResult(
        model=variant,
        accuracy=round(won / decided, 4) if decided else 0.0,
        roi=round(profit / settings.bankroll, 4),
        yield_=round(profit / staked, 4) if staked else 0.0,
        drawdown=round(max_dd, 4),
        profit=round(profit, 2),
        bets=bets,
    )


def _candidates(model: PoissonModel, fixture_id: int, odds: dict):
    probs = {
        ("1X2", "HOME"): model.prob_home_win(),
        ("1X2", "DRAW"): model.prob_draw(),
        ("1X2", "AWAY"): model.prob_away_win(),
        ("OU_2.5", "OVER"): model.prob_over(2.5),
        ("OU_2.5", "UNDER"): model.prob_under(2.5),
        ("BTTS", "YES"): model.prob_btts(),
        ("BTTS", "NO"): 1 - model.prob_btts(),
    }
    out = []
    for (market, selection), p in probs.items():
        odd = odds.get((fixture_id, market, selection))
        if odd is None or p <= 0:
            continue
        out.append((market, selection, p, odd, p * odd - 1.0))
    return out


def _settle(market, selection, hg, ag):
    total = hg + ag
    if market == "1X2":
        return {"HOME": hg > ag, "DRAW": hg == ag, "AWAY": ag > hg}.get(selection)
    if market.startswith("OU_"):
        line = float(market.split("_", 1)[1])
        return total > line if selection == "OVER" else total < line
    if market == "BTTS":
        both = hg > 0 and ag > 0
        return both if selection == "YES" else (not both)
    return None


def run_backtest(persist: bool = True) -> tuple[list[BacktestResult], str]:
    """Ejecuta las 3 variantes y devuelve (resultados, mejor_modelo)."""
    history = _load_history()
    if history.empty or len(history) < 50:
        return [], ""

    split = int(len(history) * TRAIN_FRACTION)
    train, test = history.iloc[:split], history.iloc[split:]
    odds = _closing_odds()

    results = [_simulate(v, train, test, odds) for v in VARIANTS]
    best = max(results, key=lambda r: r.profit)

    if persist:
        with session() as conn:
            conn.execute("DELETE FROM backtest_results")
            for r in results:
                conn.execute(
                    "INSERT INTO backtest_results (model, accuracy, roi, yield, "
                    " drawdown, profit, bets) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (r.model, r.accuracy, r.roi, r.yield_, r.drawdown, r.profit, r.bets),
                )
    return results, best.model
