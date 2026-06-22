"""
MODULE 3 - TEAM STRENGTH
========================

Calcula ratings dinámicos por equipo a partir del histórico de partidos:

  * Ataque  : goles marcados por partido relativo a la media de la liga.
  * Defensa : goles encajados por partido relativo a la media de la liga.
  * Home Advantage   : factor multiplicativo de goles jugando en casa.
  * Away Performance : factor multiplicativo de goles jugando fuera.
  * Forma   : rendimiento ponderado de los últimos N partidos [0,1].

Estos ratings alimentan al modelo de Poisson para estimar lambda_home y
lambda_away de cualquier emparejamiento, incluido uno que no se haya jugado.

Se mezclan goles reales con xG (cuando existe) para reducir el ruido del
muestreo de goles.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import settings
from database import query_df, session, upsert


@dataclass
class TeamRating:
    team_id: int
    attack: float          # >1 = mejor que la media ofensiva
    defense: float         # <1 = mejor que la media defensiva (encaja menos)
    home_advantage: float
    away_performance: float
    form: float            # [0,1]


def _load_played_matches() -> pd.DataFrame:
    """Carga partidos finalizados con goles y xG (si existe)."""
    sql = """
        SELECT f.id, f.match_date, f.home_team_id, f.away_team_id,
               f.home_goals, f.away_goals,
               sh.xg AS home_xg, sa.xg AS away_xg
        FROM fixtures f
        LEFT JOIN match_stats sh
               ON sh.fixture_id = f.id AND sh.team_id = f.home_team_id
        LEFT JOIN match_stats sa
               ON sa.fixture_id = f.id AND sa.team_id = f.away_team_id
        WHERE f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
        ORDER BY f.match_date
    """
    return query_df(sql)


def _blended_goals(goals: pd.Series, xg: pd.Series, w_xg: float = 0.4) -> pd.Series:
    """Combina goles reales y xG; usa goles puros si no hay xG."""
    xg_filled = xg.fillna(goals)
    return (1 - w_xg) * goals + w_xg * xg_filled


def _recency_weights(dates: pd.Series) -> pd.Series:
    """Peso exponencial por recencia: el partido más reciente pesa 1.0 y va
    decayendo con vida media settings.recency_halflife_days."""
    d = pd.to_datetime(dates, errors="coerce", utc=True)
    ref = d.max()
    if pd.isna(ref):
        return pd.Series(1.0, index=dates.index)
    age_days = (ref - d).dt.total_seconds() / 86400.0
    half = max(1.0, settings.recency_halflife_days)
    w = 0.5 ** (age_days / half)
    return w.fillna(w.min() if w.notna().any() else 1.0)


def compute_ratings(persist: bool = True) -> dict[int, TeamRating]:
    """Calcula los ratings de todos los equipos con partidos jugados."""
    df = _load_played_matches()
    if df.empty:
        return {}

    df["home_eff"] = _blended_goals(df["home_goals"], df["home_xg"])
    df["away_eff"] = _blended_goals(df["away_goals"], df["away_xg"])
    df["w"] = _recency_weights(df["match_date"])

    # Medias de liga ponderadas por recencia.
    wsum = df["w"].sum() or 1.0
    league_home_avg = (df["home_eff"] * df["w"]).sum() / wsum
    league_away_avg = (df["away_eff"] * df["w"]).sum() / wsum
    league_avg = (league_home_avg + league_away_avg) / 2

    team_ids = pd.unique(df[["home_team_id", "away_team_id"]].values.ravel())
    ratings: dict[int, TeamRating] = {}

    for tid in team_ids:
        home = df[df["home_team_id"] == tid]
        away = df[df["away_team_id"] == tid]
        wh, wa = home["w"].sum(), away["w"].sum()
        w_total = wh + wa
        if w_total == 0:
            continue

        # Sumas ponderadas por recencia (partidos recientes pesan más).
        scored = (home["home_eff"] * home["w"]).sum() + (away["away_eff"] * away["w"]).sum()
        conceded = (home["away_eff"] * home["w"]).sum() + (away["home_eff"] * away["w"]).sum()

        attack = (scored / w_total) / league_avg if league_avg else 1.0
        defense = (conceded / w_total) / league_avg if league_avg else 1.0

        home_scored = ((home["home_eff"] * home["w"]).sum() / wh) if wh else league_home_avg
        away_scored = ((away["away_eff"] * away["w"]).sum() / wa) if wa else league_away_avg
        home_adv = (home_scored / league_home_avg) if league_home_avg else 1.0
        away_perf = (away_scored / league_away_avg) if league_away_avg else 1.0

        form = _recent_form(df, tid, settings.form_matches)

        ratings[int(tid)] = TeamRating(
            team_id=int(tid),
            attack=round(float(attack), 3),
            defense=round(float(defense), 3),
            home_advantage=round(float(home_adv), 3),
            away_performance=round(float(away_perf), 3),
            form=round(float(form), 3),
        )

    if persist:
        _persist(ratings)
    return ratings


def _recent_form(df: pd.DataFrame, team_id: int, last: int) -> float:
    """Puntos por partido normalizados [0,1] en los últimos N encuentros."""
    mask = (df["home_team_id"] == team_id) | (df["away_team_id"] == team_id)
    recent = df[mask].sort_values("match_date").tail(last)
    if recent.empty:
        return 0.5
    points = 0
    for _, r in recent.iterrows():
        is_home = r["home_team_id"] == team_id
        gf = r["home_goals"] if is_home else r["away_goals"]
        ga = r["away_goals"] if is_home else r["home_goals"]
        if gf > ga:
            points += 3
        elif gf == ga:
            points += 1
    return points / (3 * len(recent))


def _persist(ratings: dict[int, TeamRating]) -> None:
    with session() as conn:
        for r in ratings.values():
            upsert(conn, "team_ratings", {
                "team_id": r.team_id,
                "attack": r.attack,
                "defense": r.defense,
                "home_advantage": r.home_advantage,
                "away_performance": r.away_performance,
                "form": r.form,
            })


def expected_lambdas(home: TeamRating, away: TeamRating,
                     league_avg_goals: float = 1.4,
                     neutral: bool = False) -> tuple[float, float]:
    """
    Combina los ratings de dos equipos para estimar los goles esperados.

        lambda_home = media_liga * ataque_local * defensa_visitante
                      * ventaja_local * ajuste_forma
        lambda_away = media_liga * ataque_visitante * defensa_local
                      * rendimiento_visitante * ajuste_forma

    En cancha neutral (p.ej. Mundial) no se aplica ventaja de localía ni
    penalización de visitante: ningún equipo juega "en casa".
    """
    form_home = 0.9 + 0.2 * home.form     # forma escala el lambda en ±10%
    form_away = 0.9 + 0.2 * away.form

    home_factor = 1.0 if neutral else home.home_advantage
    away_factor = 1.0 if neutral else away.away_performance

    lam_home = (league_avg_goals * home.attack * away.defense
                * home_factor * form_home)
    lam_away = (league_avg_goals * away.attack * home.defense
                * away_factor * form_away)
    return max(0.1, lam_home), max(0.1, lam_away)
