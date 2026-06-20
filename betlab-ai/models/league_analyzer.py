"""
MODULE 2 - LEAGUE ANALYZER
==========================

Analiza el desempeño histórico por competición y clasifica cada liga, usando
ROI, Yield, Accuracy y EV histórico de las apuestas liquidadas (bet_log):

  * Elite League   : Yield muy positivo  -> multiplicador de confianza 1.10
  * Good League    : Yield positivo      -> 1.05
  * Neutral League : Yield plano         -> 1.00
  * Avoid League   : Yield negativo      -> 0.85

El multiplicador se persiste en `league_ratings` y el ConfidenceModel lo aplica
a las predicciones futuras: las ligas donde el sistema gana dinero refuerzan la
confianza; las ligas "trampa" la reducen. Con pocas apuestas se mantiene Neutral
(evita sobreajustar con muestras pequeñas).
"""

from __future__ import annotations

import pandas as pd

from database import query_df, session

MIN_BETS = 30   # muestra mínima para clasificar; por debajo -> Neutral

# (tier, yield_mínimo, multiplicador)
TIERS = [
    ("Elite League", 0.10, 1.10),
    ("Good League", 0.03, 1.05),
    ("Neutral League", -0.03, 1.00),
    ("Avoid League", float("-inf"), 0.85),
]


def _league_stats() -> pd.DataFrame:
    return query_df(
        "SELECT bl.league_id, lg.name AS league, "
        "       COUNT(*) AS bets, "
        "       SUM(bl.stake_amount) AS staked, "
        "       SUM(bl.profit) AS profit, "
        "       AVG(CASE WHEN bl.status='WON' THEN 1.0 "
        "                WHEN bl.status='LOST' THEN 0.0 END) AS accuracy, "
        "       AVG(bl.ev) AS ev_hist "
        "FROM bet_log bl "
        "LEFT JOIN leagues lg ON lg.id = bl.league_id "
        "WHERE bl.status IN ('WON','LOST') "
        "GROUP BY bl.league_id"
    )


def _classify(yield_: float, bets: int) -> tuple[str, float]:
    if bets < MIN_BETS:
        return "Neutral League", 1.0
    for tier, min_yield, mult in TIERS:
        if yield_ >= min_yield:
            return tier, mult
    return "Avoid League", 0.85


def analyze(initial_bankroll: float = 1000.0, persist: bool = True) -> pd.DataFrame:
    """Clasifica todas las ligas y persiste los ratings."""
    df = _league_stats()
    if df.empty:
        return df

    df["staked"] = df["staked"].fillna(0.0)
    df["profit"] = df["profit"].fillna(0.0)
    df["roi"] = (df["profit"] / initial_bankroll).round(4)
    df["yield"] = (df["profit"] / df["staked"].replace(0, pd.NA)).fillna(0.0).round(4)
    df["accuracy"] = df["accuracy"].fillna(0.0).round(4)
    df["ev_hist"] = df["ev_hist"].fillna(0.0).round(4)

    tiers, mults = [], []
    for _, r in df.iterrows():
        tier, mult = _classify(float(r["yield"]), int(r["bets"]))
        tiers.append(tier)
        mults.append(mult)
    df["tier"] = tiers
    df["confidence_multiplier"] = mults

    if persist:
        with session() as conn:
            for _, r in df.iterrows():
                conn.execute(
                    "INSERT INTO league_ratings (league_id, roi, yield, accuracy, "
                    " ev_hist, bets, tier, confidence_multiplier, computed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now')) "
                    "ON CONFLICT(league_id) DO UPDATE SET "
                    " roi=excluded.roi, yield=excluded.yield, accuracy=excluded.accuracy, "
                    " ev_hist=excluded.ev_hist, bets=excluded.bets, tier=excluded.tier, "
                    " confidence_multiplier=excluded.confidence_multiplier, "
                    " computed_at=excluded.computed_at",
                    (int(r["league_id"]), float(r["roi"]), float(r["yield"]),
                     float(r["accuracy"]), float(r["ev_hist"]), int(r["bets"]),
                     r["tier"], float(r["confidence_multiplier"])),
                )

    return df[["league_id", "league", "bets", "roi", "yield", "accuracy",
               "ev_hist", "tier", "confidence_multiplier"]].sort_values(
        "yield", ascending=False)
