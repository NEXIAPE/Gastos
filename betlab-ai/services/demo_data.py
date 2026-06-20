"""
BETLAB AI - Generador de datos demo
===================================

Cuando no hay claves de API, este módulo siembra la base de datos con ligas,
equipos, un historial de partidos sintético (con goles, xG, posesión y tiros),
fixtures del día y cuotas de mercado coherentes. Permite probar todo el
pipeline (ratings, Poisson, value bets, Kelly, dashboard) de extremo a extremo.

Los datos son pseudoaleatorios pero deterministas (semilla fija).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

import numpy as np

from database import init_db, session, upsert

SEED = 42

LEAGUE = {"id": 140, "name": "La Liga (DEMO)", "country": "Spain", "season": 2025}

# (id, nombre, fuerza_ataque, fuerza_defensa) — fuerzas latentes "reales".
TEAMS = [
    (1, "Real Madrid", 1.9, 0.8),
    (2, "Barcelona", 1.85, 0.85),
    (3, "Atletico Madrid", 1.5, 0.7),
    (4, "Sevilla", 1.3, 1.0),
    (5, "Real Sociedad", 1.25, 0.95),
    (6, "Villarreal", 1.35, 1.05),
    (7, "Real Betis", 1.2, 1.1),
    (8, "Athletic Bilbao", 1.3, 0.9),
    (9, "Valencia", 1.05, 1.15),
    (10, "Getafe", 0.85, 1.0),
    (11, "Osasuna", 0.95, 1.05),
    (12, "Celta Vigo", 1.1, 1.2),
    (13, "Mallorca", 0.9, 1.05),
    (14, "Girona", 1.4, 1.15),
    (15, "Rayo Vallecano", 1.0, 1.15),
    (16, "Cadiz", 0.75, 1.25),
]

LEAGUE_AVG_GOALS = 1.4  # goles medios por equipo y partido


def seed_database(num_history_matches: int = 14) -> None:
    """Genera y guarda todo el dataset demo en SQLite."""
    init_db()
    rng = random.Random(SEED)
    np_rng = np.random.default_rng(SEED)
    team_map = {t[0]: t for t in TEAMS}

    with session() as conn:
        # Liga y equipos
        upsert(conn, "leagues", LEAGUE)
        for tid, name, _att, _def in TEAMS:
            upsert(conn, "teams", {"id": tid, "name": name, "logo": ""})

        fixture_id = 1000
        base_date = datetime(2026, 6, 20)

        # --- Historial: round-robin parcial -------------------------------
        team_ids = [t[0] for t in TEAMS]
        for rnd in range(num_history_matches):
            rng.shuffle(team_ids)
            day = base_date - timedelta(days=(num_history_matches - rnd) * 4)
            for i in range(0, len(team_ids) - 1, 2):
                home_id, away_id = team_ids[i], team_ids[i + 1]
                h_att, h_def = team_map[home_id][2], team_map[home_id][3]
                a_att, a_def = team_map[away_id][2], team_map[away_id][3]

                hg = int(np_rng.poisson(max(0.15, LEAGUE_AVG_GOALS * h_att * a_def * 1.25)))
                ag = int(np_rng.poisson(max(0.15, LEAGUE_AVG_GOALS * a_att * h_def * 0.9)))

                fixture_id += 1
                upsert(conn, "fixtures", {
                    "id": fixture_id,
                    "league_id": LEAGUE["id"],
                    "season": LEAGUE["season"],
                    "match_date": day.isoformat(),
                    "status": "FT",
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "home_goals": hg,
                    "away_goals": ag,
                })
                _seed_stats(conn, fixture_id, home_id, True, hg, np_rng)
                _seed_stats(conn, fixture_id, away_id, False, ag, np_rng)

        # --- Fixtures del día (sin jugar) ----------------------------------
        today = datetime(2026, 6, 20)
        todays = [(1, 4), (2, 7), (3, 9), (14, 16), (6, 11), (8, 13)]
        for home_id, away_id in todays:
            fixture_id += 1
            upsert(conn, "fixtures", {
                "id": fixture_id,
                "league_id": LEAGUE["id"],
                "season": LEAGUE["season"],
                "match_date": today.replace(hour=18).isoformat(),
                "status": "NS",
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_goals": None,
                "away_goals": None,
            })
            _seed_odds(conn, fixture_id, home_id, away_id, team_map, np_rng)
            _seed_injuries(conn, fixture_id, home_id, away_id, np_rng)


def _seed_stats(conn, fixture_id: int, team_id: int, is_home: bool,
                goals: int, np_rng) -> None:
    xg = max(0.1, goals * 0.85 + float(np_rng.normal(0.4, 0.25)))
    possession = float(np.clip(np_rng.normal(52 if is_home else 48, 8), 30, 70))
    shots = int(max(2, np_rng.poisson(12 if is_home else 10)))
    sot = int(max(0, min(shots, np_rng.poisson(4 + goals))))
    upsert(conn, "match_stats", {
        "fixture_id": fixture_id,
        "team_id": team_id,
        "is_home": 1 if is_home else 0,
        "goals": goals,
        "xg": round(xg, 2),
        "possession": round(possession, 1),
        "shots": shots,
        "shots_on_target": sot,
    })


def _seed_odds(conn, fixture_id: int, home_id: int, away_id: int,
               team_map: dict, np_rng) -> None:
    """
    Crea cuotas con margen de casa (~6%) y ruido por libro, en DOS snapshots:
    una cuota de *apertura* (hace 2 días) y una *actual* (ahora). La actual se
    mueve ligeramente respecto a la apertura, lo que alimenta el factor de
    'movimiento de cuotas' del Score de Confianza.
    """
    from models.poisson_model import PoissonModel  # import diferido

    h_att, h_def = team_map[home_id][2], team_map[home_id][3]
    a_att, a_def = team_map[away_id][2], team_map[away_id][3]

    lam_home = LEAGUE_AVG_GOALS * h_att * a_def * 1.25
    lam_away = LEAGUE_AVG_GOALS * a_att * h_def * 0.9
    model = PoissonModel(lam_home, lam_away)
    probs = model.summary()

    def odd_from_prob(p: float, margin: float = 1.06) -> float:
        p = min(0.97, max(0.03, p))
        fair = 1.0 / p
        noisy = fair / margin * float(np_rng.normal(1.0, 0.04))
        return round(max(1.01, noisy), 2)

    rows = [
        ("1X2", "HOME", probs["home_win"]),
        ("1X2", "DRAW", probs["draw"]),
        ("1X2", "AWAY", probs["away_win"]),
        ("OU_2.5", "OVER", probs["over_2_5"]),
        ("OU_2.5", "UNDER", 1 - probs["over_2_5"]),
        ("BTTS", "YES", probs["btts"]),
        ("BTTS", "NO", 1 - probs["btts"]),
    ]

    opening_ts = (datetime(2026, 6, 20) - timedelta(days=2)).isoformat()
    current_ts = datetime(2026, 6, 20, 12).isoformat()

    for bk in ("Pinnacle", "Bet365", "William Hill"):
        for market, selection, p in rows:
            opening = odd_from_prob(p)
            # Deriva la cuota actual: a veces se acorta (entra dinero), a veces se abre.
            drift = float(np_rng.normal(0.0, 0.03))      # ±3% típico
            current = round(max(1.01, opening * (1.0 + drift)), 2)
            conn.execute(
                "INSERT INTO odds (fixture_id, bookmaker, market, selection, odd, captured_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (fixture_id, bk, market, selection, opening, opening_ts),
            )
            conn.execute(
                "INSERT INTO odds (fixture_id, bookmaker, market, selection, odd, captured_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (fixture_id, bk, market, selection, current, current_ts),
            )


# Catálogo demo de jugadores lesionados (nombre genérico por equipo).
def _seed_injuries(conn, fixture_id: int, home_id: int, away_id: int, np_rng) -> None:
    """Siembra 0-2 lesiones por equipo para alimentar el factor de lesiones."""
    reasons = ["Lesión muscular", "Sobrecarga", "Sanción", "Esguince"]
    for team_id in (home_id, away_id):
        n = int(np_rng.integers(0, 3))   # 0, 1 o 2 lesiones
        for i in range(n):
            conn.execute(
                "INSERT INTO injuries (fixture_id, team_id, player, reason) "
                "VALUES (?, ?, ?, ?)",
                (fixture_id, team_id, f"Jugador {team_id}-{i+1}",
                 reasons[int(np_rng.integers(0, len(reasons)))]),
            )


if __name__ == "__main__":  # pragma: no cover
    seed_database()
    print("Datos demo generados.")
