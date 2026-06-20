"""
BETLAB AI - Generador de datos demo (multi-liga, ~2 años)
=========================================================

Cuando no hay claves de API, este módulo siembra un dataset sintético pero
determinista que ejercita TODO el sistema:

  * 4 ligas con distinto "perfil de mercado" para que el League Analyzer las
    clasifique en Elite / Good / Neutral / Avoid:
        - market_bias > 0  => el mercado nos da ventaja (apostar es rentable)
        - market_bias < 0  => el mercado va en contra (liga a evitar)
  * ~2 años de historial continuo por liga (resultados, xG, posesión, tiros y
    cuota de cierre), suficiente para el Backtesting.
  * Un track record de apuestas liquidadas (bet_log) simulando la estrategia
    de valor sobre ese historial: alimenta el Performance Tracker y el
    League Analyzer desde el primer arranque.
  * Fixtures del día (NS) con DOS snapshots de cuotas (apertura/actual) y valor
    inyectado dentro de la banda [1.40, 2.20] para que existan picks Strong/Elite
    y se puedan construir combinadas.
  * Lesiones (algunas "importantes") para alimentar el No Bet Engine.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from config import settings
from database import init_db, session, upsert

SEED = 42
LEAGUE_AVG_GOALS = 1.4
TODAY = datetime(2026, 6, 20)

# id, nombre, país, abreviatura, sesgo de mercado, "trampa", nº equipos
# market_bias>0 => cuotas generosas (apostar da ventaja).
# trap          => prob. de que una apuesta GANADORA no se materialice (factores
#                  no modelados / mercado más afilado): hunde el ROID de la liga.
LEAGUES = [
    (140, "La Liga (DEMO)", "Spain", "LL", 0.13, 0.00, 10),      # -> Elite League
    (39, "Premier League (DEMO)", "England", "PL", 0.07, 0.04, 10),  # -> Good League
    (78, "Bundesliga (DEMO)", "Germany", "BL", 0.03, 0.10, 10),  # -> Neutral (muestra baja)
    (135, "Serie A (DEMO)", "Italy", "SA", 0.10, 0.32, 10),      # -> Avoid League
]

ROUNDS = 60            # jornadas de historial por liga (~2 años con paso de 11 días)
DATE_STEP_DAYS = 11
MARGIN = 1.05          # margen de la casa


def _latent(rng: np.random.Generator, n: int) -> list[tuple[float, float]]:
    """Genera (ataque, defensa) latentes para n equipos."""
    out = []
    for _ in range(n):
        att = float(np.clip(rng.normal(1.2, 0.32), 0.65, 2.0))
        dfn = float(np.clip(rng.normal(1.0, 0.22), 0.6, 1.5))
        out.append((round(att, 3), round(dfn, 3)))
    return out


def _lambdas(h_att, h_def, a_att, a_def) -> tuple[float, float]:
    lam_h = LEAGUE_AVG_GOALS * h_att * a_def * 1.25
    lam_a = LEAGUE_AVG_GOALS * a_att * h_def * 0.9
    return max(0.15, lam_h), max(0.15, lam_a)


def seed_database(rounds: int = ROUNDS) -> None:
    """Genera y guarda todo el dataset demo."""
    from models.poisson_model import PoissonModel
    from models.kelly import recommend_stake

    init_db()
    rng = np.random.default_rng(SEED)
    fixture_id = 100000
    team_latent: dict[int, tuple[float, float]] = {}
    team_league: dict[int, int] = {}

    with session() as conn:
        # Reinicia tablas volátiles para que el demo sea idempotente.
        for tbl in ("bet_log", "value_bets", "no_bets", "odds", "injuries",
                    "match_stats", "fixtures", "league_ratings", "backtest_results"):
            conn.execute(f"DELETE FROM {tbl}")

        # --- ligas y equipos ----------------------------------------------
        league_teams: dict[int, list[int]] = {}
        for lid, name, country, abbr, _bias, _upset, n in LEAGUES:
            upsert(conn, "leagues", {"id": lid, "name": name,
                                     "country": country, "season": 2025})
            latents = _latent(rng, n)
            ids = []
            for i, (att, dfn) in enumerate(latents):
                tid = lid * 100 + i
                upsert(conn, "teams", {"id": tid, "name": f"{abbr} Team {i+1}", "logo": ""})
                team_latent[tid] = (att, dfn)
                team_league[tid] = lid
                ids.append(tid)
            league_teams[lid] = ids

        # --- historial (~2 años) + cuotas de cierre + track record --------
        start_date = TODAY - timedelta(days=rounds * DATE_STEP_DAYS + 10)
        for lid, name, country, abbr, bias, trap, n in LEAGUES:
            ids = league_teams[lid]
            for rnd in range(rounds):
                day = start_date + timedelta(days=rnd * DATE_STEP_DAYS)
                order = list(ids)
                rng.shuffle(order)
                for i in range(0, len(order) - 1, 2):
                    home_id, away_id = order[i], order[i + 1]
                    fixture_id += 1
                    _store_historical_match(
                        conn, fixture_id, lid, home_id, away_id, day, bias, trap,
                        team_latent, rng, PoissonModel, recommend_stake,
                    )

        # --- fixtures del día con valor inyectado en la banda -------------
        _seed_today(conn, fixture_id, league_teams, team_latent, rng, PoissonModel)

        # --- estado inicial del bankroll ----------------------------------
        conn.execute("DELETE FROM bankroll_state")
        conn.execute(
            "INSERT INTO bankroll_state (id, initial_bankroll, current_bankroll, mode) "
            "VALUES (1, ?, ?, 'NORMAL')",
            (settings.bankroll, settings.bankroll),
        )


def _store_historical_match(conn, fixture_id, lid, home_id, away_id, day, bias, trap,
                            team_latent, rng, PoissonModel, recommend_stake) -> None:
    h_att, h_def = team_latent[home_id]
    a_att, a_def = team_latent[away_id]
    lam_h, lam_a = _lambdas(h_att, h_def, a_att, a_def)

    hg = int(rng.poisson(lam_h))
    ag = int(rng.poisson(lam_a))

    upsert(conn, "fixtures", {
        "id": fixture_id, "league_id": lid, "season": 2025,
        "match_date": day.isoformat(), "status": "FT",
        "home_team_id": home_id, "away_team_id": away_id,
        "home_goals": hg, "away_goals": ag,
    })
    _seed_stats(conn, fixture_id, home_id, True, hg, rng)
    _seed_stats(conn, fixture_id, away_id, False, ag, rng)

    # Cuotas de cierre (true prob + margen + sesgo de liga + ruido).
    model = PoissonModel(lam_h, lam_a)
    probs = _market_probs(model)
    closing_ts = (day - timedelta(days=1)).isoformat()
    odds_rows = {}
    for market, selection, p in probs:
        odd = _odd(p, bias, rng)
        odds_rows[(market, selection)] = (p, odd)
        conn.execute(
            "INSERT INTO odds (fixture_id, bookmaker, market, selection, odd, captured_at) "
            "VALUES (?, 'Closing', ?, ?, ?, ?)",
            (fixture_id, market, selection, odd, closing_ts),
        )

    # Simula la apuesta de valor de la estrategia: mejor EV con EV>umbral.
    best = None
    for (market, selection), (p, odd) in odds_rows.items():
        ev = p * odd - 1.0
        if best is None or ev > best[3]:
            best = (market, selection, odd, ev, p)
    if best and best[3] > settings.min_ev:
        market, selection, odd, ev, p = best
        stake = recommend_stake(p, odd).stake_amount
        won = _settle(market, selection, hg, ag)
        if won is None:
            return
        # "Trampa" de liga: una fracción de las apuestas ganadoras no se
        # materializa (factores no modelados) -> deteriora el ROI de la liga.
        if won and trap and rng.random() < trap:
            won = False
        profit = round(stake * (odd - 1.0), 2) if won else round(-stake, 2)
        conn.execute(
            "INSERT INTO bet_log (fixture_id, league_id, market, selection, odd, "
            " model_prob, ev, stake_amount, status, profit, placed_at, settled_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (fixture_id, lid, market, selection, odd, round(p, 4), round(ev, 4),
             stake, "WON" if won else "LOST", profit, closing_ts, day.isoformat()),
        )


def _seed_today(conn, fixture_id, league_teams, team_latent, rng, PoissonModel) -> None:
    """Fixtures de hoy: favoritos fuertes con valor inyectado dentro de la banda."""
    today_fixtures = []
    for lid, ids in league_teams.items():
        # ordena por fuerza (ataque-defensa) y enfrenta fuerte vs medio/débil
        ranked = sorted(ids, key=lambda t: team_latent[t][0] - team_latent[t][1], reverse=True)
        pairs = [(ranked[0], ranked[6]), (ranked[1], ranked[8])]
        today_fixtures.extend((lid, h, a) for h, a in pairs)

    opening_ts = (TODAY - timedelta(days=2)).isoformat()
    current_ts = TODAY.replace(hour=12).isoformat()

    for lid, home_id, away_id in today_fixtures:
        fixture_id += 1
        h_att, h_def = team_latent[home_id]
        a_att, a_def = team_latent[away_id]
        lam_h, lam_a = _lambdas(h_att, h_def, a_att, a_def)
        model = PoissonModel(lam_h, lam_a)
        probs = dict(((m, s), p) for m, s, p in _market_probs(model))

        upsert(conn, "fixtures", {
            "id": fixture_id, "league_id": lid, "season": 2025,
            "match_date": TODAY.replace(hour=18).isoformat(), "status": "NS",
            "home_team_id": home_id, "away_team_id": away_id,
            "home_goals": None, "away_goals": None,
        })
        _seed_stats_recent(conn, fixture_id, home_id, away_id, rng)

        for (market, selection), p in probs.items():
            fair = 1.0 / min(0.97, max(0.03, p))
            if market == "1X2" and selection == "HOME":
                # Inyecta valor: cuota inflada que empuja al favorito a la banda.
                value_factor = float(rng.uniform(1.18, 1.42))
                opening = round(max(settings.odd_min, fair * value_factor / MARGIN), 2)
                opening = min(opening, settings.odd_max)
                current = round(max(1.01, opening * (1 - float(rng.uniform(0.0, 0.05)))), 2)
            else:
                opening = round(max(1.01, fair / MARGIN * (1 + float(rng.normal(0, 0.03)))), 2)
                current = round(max(1.01, opening * (1 + float(rng.normal(0, 0.03)))), 2)
            for bk, ts, odd in (("Open", opening_ts, opening), ("Now", current_ts, current)):
                conn.execute(
                    "INSERT INTO odds (fixture_id, bookmaker, market, selection, odd, captured_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (fixture_id, bk, market, selection, odd, ts),
                )
        _seed_injuries(conn, fixture_id, home_id, away_id, rng)


def _market_probs(model) -> list[tuple[str, str, float]]:
    s = model.summary()
    return [
        ("1X2", "HOME", s["home_win"]),
        ("1X2", "DRAW", s["draw"]),
        ("1X2", "AWAY", s["away_win"]),
        ("OU_2.5", "OVER", s["over_2_5"]),
        ("OU_2.5", "UNDER", s["under_2_5"]),
        ("BTTS", "YES", s["btts"]),
        ("BTTS", "NO", 1 - s["btts"]),
    ]


def _odd(p: float, bias: float, rng) -> float:
    p = min(0.97, max(0.03, p))
    fair = 1.0 / p
    odd = fair / MARGIN * (1 + bias) * (1 + float(rng.normal(0, 0.03)))
    return round(max(1.01, odd), 2)


def _settle(market: str, selection: str, hg: int, ag: int) -> bool | None:
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


def _seed_stats(conn, fixture_id, team_id, is_home, goals, rng) -> None:
    xg = max(0.1, goals * 0.85 + float(rng.normal(0.4, 0.25)))
    upsert(conn, "match_stats", {
        "fixture_id": fixture_id, "team_id": team_id, "is_home": 1 if is_home else 0,
        "goals": goals, "xg": round(xg, 2),
        "possession": round(float(np.clip(rng.normal(52 if is_home else 48, 8), 30, 70)), 1),
        "shots": int(max(2, rng.poisson(12 if is_home else 10))),
        "shots_on_target": int(max(0, rng.poisson(4 + goals))),
    })


def _seed_stats_recent(conn, fixture_id, home_id, away_id, rng) -> None:
    # placeholder de estadística para fixtures futuros (xG previsto = NULL)
    for tid, is_home in ((home_id, True), (away_id, False)):
        upsert(conn, "match_stats", {
            "fixture_id": fixture_id, "team_id": tid, "is_home": 1 if is_home else 0,
            "goals": None, "xg": None, "possession": None,
            "shots": None, "shots_on_target": None,
        })


def _seed_injuries(conn, fixture_id, home_id, away_id, rng) -> None:
    reasons = ["Lesión muscular", "Sobrecarga", "Sanción", "Esguince", "Rotura"]
    for team_id in (home_id, away_id):
        # 0-2 bajas habitualmente; ~15% de las veces un pico (4-5) que dispara
        # el No Bet Engine por "demasiadas bajas importantes".
        n = int(rng.integers(0, 3))
        if rng.random() < 0.15:
            n += int(rng.integers(2, 4))
        for i in range(n):
            conn.execute(
                "INSERT INTO injuries (fixture_id, team_id, player, reason) "
                "VALUES (?, ?, ?, ?)",
                (fixture_id, team_id, f"Jugador {team_id}-{i+1}",
                 reasons[int(rng.integers(0, len(reasons)))]),
            )


if __name__ == "__main__":  # pragma: no cover
    seed_database()
    print("Datos demo (multi-liga, ~2 años) generados.")
