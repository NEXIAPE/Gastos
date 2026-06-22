"""
BETLAB AI - Orquestador de ingesta
==================================

Coordina los Module 1 (API-Football) y 2 (The Odds API):

  * descarga fixtures del día, estadísticas, lesiones y forma,
  * descarga y guarda el histórico de cuotas,
  * o, si no hay claves, siembra datos demo.

Punto de entrada: `ingest(date)`.
"""

from __future__ import annotations

from datetime import date as date_cls

from config import settings
from database import init_db, session, upsert
from services.api_football import (
    APIFootballClient,
    normalize_apifootball_odds,
    parse_statistic_value,
)
from services.odds_api import OddsAPIClient, normalize_event_odds


def ingest(target_date: str | None = None, league: int | None = None,
           season: int | None = None) -> dict[str, int]:
    """
    Ejecuta la ingesta completa para una fecha (YYYY-MM-DD).

    Devuelve un resumen con conteos. Si faltan claves de API recurre al
    generador de datos demo.
    """
    init_db()
    target_date = target_date or date_cls.today().isoformat()

    football = APIFootballClient()
    odds = OddsAPIClient()

    if not football.enabled and not odds.enabled:
        from services.demo_data import seed_database

        seed_database()
        return {"mode": 0, "fixtures": 0, "demo": 1}

    counts = {"fixtures": 0, "stats": 0, "odds": 0, "injuries": 0}

    # Si hay clave de The Odds API se usa esa fuente; si no, las cuotas se
    # toman del propio API-Football (mismo proveedor que los fixtures).
    use_oddsapi = odds.enabled

    with session() as conn:
        # --- Module 1: fixtures + estadísticas ----------------------------
        fixtures = football.get_fixtures_by_date(target_date, league, season)
        for fx in fixtures:
            _store_fixture(conn, fx)
            counts["fixtures"] += 1

            fixture_id = fx["fixture"]["id"]
            stats = football.get_fixture_statistics(fixture_id)
            counts["stats"] += _store_fixture_stats(conn, fixture_id, fx, stats)

            for inj in football.get_injuries(fixture_id):
                team_id = inj.get("team", {}).get("id")
                if team_id:
                    conn.execute(
                        "INSERT INTO injuries (fixture_id, team_id, player, reason) "
                        "VALUES (?, ?, ?, ?)",
                        (fixture_id, team_id,
                         inj.get("player", {}).get("name"),
                         inj.get("player", {}).get("reason")),
                    )
                    counts["injuries"] += 1

            # --- Module 2a: cuotas vía API-Football (por fixture) ---------
            if not use_oddsapi:
                events = football.get_odds_by_fixture(fixture_id)
                for row in normalize_apifootball_odds(events):
                    conn.execute(
                        "INSERT INTO odds (fixture_id, bookmaker, market, selection, odd) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (fixture_id, row["bookmaker"], row["market"],
                         row["selection"], row["odd"]),
                    )
                    counts["odds"] += 1

        # --- Module 2b: cuotas vía The Odds API ---------------------------
        if use_oddsapi:
            events = odds.get_odds(
                sport=settings.odds_sport,
                regions=settings.odds_regions,
                markets="h2h,totals,spreads",
            )
            fixtures_by_teams = _index_fixtures(conn)
            for event in events:
                fixture_id = _match_event_to_fixture(event, fixtures_by_teams)
                if fixture_id is None:
                    continue
                for row in normalize_event_odds(event):
                    conn.execute(
                        "INSERT INTO odds (fixture_id, bookmaker, market, selection, odd) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (fixture_id, row["bookmaker"], row["market"],
                         row["selection"], row["odd"]),
                    )
                    counts["odds"] += 1

    counts["mode"] = 1
    return counts


def _store_fixture(conn, fx: dict) -> None:
    teams = fx["teams"]
    goals = fx.get("goals", {})
    league = fx.get("league", {})
    for side in ("home", "away"):
        t = teams[side]
        upsert(conn, "teams", {"id": t["id"], "name": t["name"], "logo": t.get("logo", "")})
    if league.get("id"):
        upsert(conn, "leagues", {
            "id": league["id"], "name": league.get("name"),
            "country": league.get("country"), "season": league.get("season"),
        })
    upsert(conn, "fixtures", {
        "id": fx["fixture"]["id"],
        "league_id": league.get("id"),
        "season": league.get("season"),
        "match_date": fx["fixture"]["date"],
        "status": fx["fixture"]["status"]["short"],
        "home_team_id": teams["home"]["id"],
        "away_team_id": teams["away"]["id"],
        "home_goals": goals.get("home"),
        "away_goals": goals.get("away"),
    })


def _store_fixture_stats(conn, fixture_id: int, fx: dict, stats: list) -> int:
    """Guarda estadísticas por equipo si están disponibles."""
    if not stats:
        return 0
    teams = fx["teams"]
    goals = fx.get("goals", {})
    home_id = teams["home"]["id"]
    written = 0
    for team_stat in stats:
        team_id = team_stat.get("team", {}).get("id")
        if team_id is None:
            continue
        stat_list = team_stat.get("statistics", [])
        is_home = team_id == home_id
        upsert(conn, "match_stats", {
            "fixture_id": fixture_id,
            "team_id": team_id,
            "is_home": 1 if is_home else 0,
            "goals": goals.get("home") if is_home else goals.get("away"),
            "xg": parse_statistic_value(stat_list, "expected_goals"),
            "possession": parse_statistic_value(stat_list, "Ball Possession"),
            "shots": parse_statistic_value(stat_list, "Total Shots"),
            "shots_on_target": parse_statistic_value(stat_list, "Shots on Goal"),
        })
        written += 1
    return written


def _index_fixtures(conn) -> dict[tuple[str, str], int]:
    """Mapa (home_name, away_name) -> fixture_id para casar eventos de odds."""
    rows = conn.execute(
        "SELECT f.id, th.name AS home, ta.name AS away "
        "FROM fixtures f "
        "JOIN teams th ON th.id = f.home_team_id "
        "JOIN teams ta ON ta.id = f.away_team_id "
        "WHERE f.status = 'NS'"
    ).fetchall()
    return {(r["home"].lower(), r["away"].lower()): r["id"] for r in rows}


def _match_event_to_fixture(event: dict, index: dict) -> int | None:
    home = (event.get("home_team") or "").lower()
    away = (event.get("away_team") or "").lower()
    return index.get((home, away))


if __name__ == "__main__":  # pragma: no cover
    print(ingest())
