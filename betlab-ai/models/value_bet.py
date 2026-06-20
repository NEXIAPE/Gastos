"""
MODULE 5 - VALUE BET ENGINE
===========================

Une todo el pipeline analítico:

  1. Carga los fixtures pendientes (status NS) y los ratings de equipos.
  2. Estima lambda_home / lambda_away (Module 3) y construye el modelo de
     Poisson (Module 4).
  3. Para cada mercado con cuota disponible compara la probabilidad del modelo
     con la mejor cuota de mercado y calcula el Expected Value:

         EV = (prob_modelo * cuota) - 1

  4. Filtra apuestas con EV > umbral (por defecto 5%).
  5. Calcula el stake recomendado (Module 6 - Kelly fraccionado).
  6. Persiste las value bets en SQLite.

Todo se basa en probabilidad matemática; ninguna decisión usa intuición.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

import pandas as pd

from config import settings
from database import query_df, session
from models.confidence import ConfidenceModel
from models.kelly import recommend_stake
from models.poisson_model import PoissonModel
from models.team_strength import TeamRating, compute_ratings, expected_lambdas


@dataclass
class ValueBet:
    fixture_id: int
    match: str
    match_date: str
    market: str
    selection: str
    model_prob: float
    odd: float
    implied_prob: float
    ev: float
    confidence: float
    tier: str
    stake_pct: float
    stake_amount: float
    risk: str
    factors: dict = field(default_factory=dict)


def _best_odds() -> pd.DataFrame:
    """
    Mejor cuota (máxima) por fixture/market/selection usando solo el snapshot
    de cuotas MÁS RECIENTE de cada partido (precio actual, no de apertura).
    """
    sql = """
        WITH latest AS (
            SELECT fixture_id, MAX(captured_at) AS mc
            FROM odds GROUP BY fixture_id
        )
        SELECT o.fixture_id, o.market, o.selection, MAX(o.odd) AS odd
        FROM odds o
        JOIN latest l ON o.fixture_id = l.fixture_id AND o.captured_at = l.mc
        GROUP BY o.fixture_id, o.market, o.selection
    """
    return query_df(sql)


def _pending_fixtures() -> pd.DataFrame:
    sql = """
        SELECT f.id AS fixture_id, f.match_date,
               f.home_team_id, f.away_team_id,
               th.name AS home_name, ta.name AS away_name
        FROM fixtures f
        JOIN teams th ON th.id = f.home_team_id
        JOIN teams ta ON ta.id = f.away_team_id
        WHERE f.status = 'NS'
        ORDER BY f.match_date
    """
    return query_df(sql)


def _model_prob(model: PoissonModel, market: str, selection: str) -> float | None:
    """Devuelve la probabilidad del modelo para un (market, selection)."""
    if market == "1X2":
        return {"HOME": model.prob_home_win(),
                "DRAW": model.prob_draw(),
                "AWAY": model.prob_away_win()}.get(selection)
    if market.startswith("OU_"):
        try:
            line = float(market.split("_", 1)[1])
        except ValueError:
            line = 2.5
        if selection == "OVER":
            return model.prob_over(line)
        if selection == "UNDER":
            return model.prob_under(line)
        return None
    if market == "BTTS":
        p = model.prob_btts()
        return p if selection == "YES" else (1 - p if selection == "NO" else None)
    return None  # Asian Handicap no modelado analíticamente aquí


def detect_value_bets(min_ev: float | None = None,
                      min_confidence: float | None = None,
                      persist: bool = True) -> list[ValueBet]:
    """
    Detecta value bets que cumplen DOS filtros:
      * EV > min_ev (apuesta de valor), y
      * Score de Confianza >= min_confidence (por defecto 80 => Strong/Elite).
    """
    min_ev = settings.min_ev if min_ev is None else min_ev
    min_confidence = settings.min_confidence if min_confidence is None else min_confidence

    ratings = compute_ratings(persist=True)
    if not ratings:
        return []

    fixtures = _pending_fixtures()
    odds = _best_odds()
    if fixtures.empty or odds.empty:
        return []

    league_avg = _league_avg_goals()
    confidence_model = ConfidenceModel()
    results: list[ValueBet] = []

    for _, fx in fixtures.iterrows():
        home_id, away_id = int(fx["home_team_id"]), int(fx["away_team_id"])
        home_r = ratings.get(home_id)
        away_r = ratings.get(away_id)
        if not home_r or not away_r:
            continue

        lam_h, lam_a = expected_lambdas(home_r, away_r, league_avg)
        model = PoissonModel(lam_h, lam_a, max_goals=settings.max_goals)

        fx_odds = odds[odds["fixture_id"] == fx["fixture_id"]]
        match_label = f"{fx['home_name']} vs {fx['away_name']}"

        for _, o in fx_odds.iterrows():
            prob = _model_prob(model, o["market"], o["selection"])
            if prob is None or prob <= 0:
                continue
            odd = float(o["odd"])
            ev = prob * odd - 1.0
            if ev <= min_ev:
                continue

            conf = confidence_model.score(
                int(fx["fixture_id"]), home_id, away_id,
                str(fx["match_date"]), o["market"], o["selection"],
            )
            if conf.score < min_confidence:
                continue  # solo Strong (80+) y Elite (90+)

            stake = recommend_stake(prob, odd)
            results.append(ValueBet(
                fixture_id=int(fx["fixture_id"]),
                match=match_label,
                match_date=str(fx["match_date"]),
                market=o["market"],
                selection=o["selection"],
                model_prob=round(prob, 4),
                odd=round(odd, 2),
                implied_prob=round(1.0 / odd, 4),
                ev=round(ev, 4),
                confidence=conf.score,
                tier=conf.tier,
                stake_pct=stake.stake_pct,
                stake_amount=stake.stake_amount,
                risk=stake.risk,
                factors=conf.breakdown,
            ))

    # Ordena por confianza y, a igualdad, por EV.
    results.sort(key=lambda b: (b.confidence, b.ev), reverse=True)

    if persist:
        _persist(results)
    return results


def _league_avg_goals() -> float:
    df = query_df(
        "SELECT AVG(home_goals + away_goals) AS avg_total FROM fixtures "
        "WHERE home_goals IS NOT NULL"
    )
    if df.empty or df["avg_total"].iloc[0] is None:
        return 1.4
    return float(df["avg_total"].iloc[0]) / 2.0


def _persist(bets: list[ValueBet]) -> None:
    with session() as conn:
        # Reemplaza el set actual de value bets pendientes.
        conn.execute("DELETE FROM value_bets")
        for b in bets:
            conn.execute(
                "INSERT INTO value_bets "
                "(fixture_id, market, selection, model_prob, odd, implied_prob, "
                " ev, confidence, tier, factors_json, stake_pct, stake_amount) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (b.fixture_id, b.market, b.selection, b.model_prob, b.odd,
                 b.implied_prob, b.ev, b.confidence, b.tier,
                 json.dumps(b.factors), b.stake_pct, b.stake_amount),
            )


def value_bets_dataframe(bets: list[ValueBet]) -> pd.DataFrame:
    df = pd.DataFrame([asdict(b) for b in bets])
    if not df.empty:
        df = df.drop(columns=["factors"])   # el desglose no va en la tabla plana
    return df
