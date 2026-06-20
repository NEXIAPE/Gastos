"""
BETLAB AI - Elo Rating dinámico
===============================

Calcula un rating Elo por equipo a partir del histórico de partidos, al estilo
del "World Football Elo": el ajuste de cada partido se pondera por la diferencia
de goles y se aplica una ventaja de localía constante.

Fórmulas:
    E_home = 1 / (1 + 10 ** ((R_away - (R_home + HFA)) / 400))
    R'     = R + K * G * (S - E)

donde S ∈ {1, 0.5, 0} (victoria/empate/derrota) y G es el multiplicador por
margen de goles. El Elo resume la fuerza global del equipo en una sola cifra
comparable, ideal como factor del Score de Confianza.
"""

from __future__ import annotations

import pandas as pd

from database import query_df

BASE_ELO = 1500.0
K_FACTOR = 20.0
HOME_FIELD_ADV = 65.0   # puntos Elo de ventaja por jugar en casa


def _goal_diff_multiplier(goal_diff: int) -> float:
    """Multiplicador K por margen de goles (atenúa goleadas aisladas)."""
    gd = abs(goal_diff)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11.0 + gd) / 8.0


def _expected(r_home: float, r_away: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_away - (r_home + HOME_FIELD_ADV)) / 400.0))


def compute_elo() -> dict[int, float]:
    """Procesa todos los partidos finalizados en orden y devuelve el Elo final."""
    matches = query_df(
        "SELECT home_team_id, away_team_id, home_goals, away_goals "
        "FROM fixtures "
        "WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL "
        "ORDER BY match_date"
    )
    ratings: dict[int, float] = {}
    if matches.empty:
        return ratings

    for _, m in matches.iterrows():
        h, a = int(m["home_team_id"]), int(m["away_team_id"])
        rh = ratings.get(h, BASE_ELO)
        ra = ratings.get(a, BASE_ELO)

        exp_h = _expected(rh, ra)
        hg, ag = int(m["home_goals"]), int(m["away_goals"])
        if hg > ag:
            s_h = 1.0
        elif hg == ag:
            s_h = 0.5
        else:
            s_h = 0.0

        g = _goal_diff_multiplier(hg - ag)
        delta = K_FACTOR * g * (s_h - exp_h)
        ratings[h] = rh + delta
        ratings[a] = ra - delta

    return {tid: round(r, 1) for tid, r in ratings.items()}


def win_probability(elo_home: float, elo_away: float) -> float:
    """P(victoria local) implícita por Elo, incluyendo ventaja de localía."""
    return _expected(elo_home, elo_away)
