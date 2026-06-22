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
from services.footballdata import FootballDataClient, normalize_fd_match
from services.odds_api import OddsAPIClient, normalize_event_odds


def ingest(target_date: str | None = None, league: int | None = None,
           season: int | None = None, competition: str | None = None,
           odds_sport: str | None = None) -> dict[str, int]:
    """
    Ejecuta la ingesta completa para una fecha (YYYY-MM-DD).

    Fuentes de datos (según las claves configuradas):
      * football-data.org (temporadas actuales, incl. Mundial) + The Odds API
        para cuotas, o
      * API-Football (fixtures/stats/lesiones) con cuotas de API-Football o
        The Odds API, o
      * datos demo si no hay ninguna clave.
    """
    init_db()
    target_date = target_date or date_cls.today().isoformat()

    football = APIFootballClient()
    odds = OddsAPIClient()
    fd = FootballDataClient()

    if not (football.enabled or odds.enabled or fd.enabled):
        from services.demo_data import seed_database

        seed_database()
        return {"mode": 0, "fixtures": 0, "demo": 1}

    counts = {"fixtures": 0, "stats": 0, "odds": 0, "injuries": 0}
    use_oddsapi = odds.enabled

    with session() as conn:
        if fd.enabled:
            # --- Fuente: football-data.org (fixtures + resultados) --------
            # FD_COMPETITION admite varias competiciones separadas por coma, con
            # temporada opcional por competición: "WC:2026,EC:2024".
            default_season = season if season is not None else settings.season
            spec = competition or settings.fd_competition or "PL"
            comps = _parse_competitions(spec, default_season)
            for comp, comp_season in comps:
                for match in fd.get_matches(comp, season=comp_season):
                    if _store_fd_match(conn, match):
                        counts["fixtures"] += 1
            # Cuotas: The Odds API (no las da football-data.org).
            if use_oddsapi:
                _ingest_odds_api(conn, odds, counts, odds_sport=odds_sport)
        else:
            # --- Fuente: API-Football (fixtures + stats + lesiones) -------
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

                # Cuotas vía API-Football (por fixture) si no hay The Odds API.
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

            # Cuotas vía The Odds API (emparejadas por nombre de equipo).
            if use_oddsapi:
                _ingest_odds_api(conn, odds, counts, odds_sport=odds_sport)

    counts["mode"] = 1
    return counts


def _parse_competitions(spec: str, default_season: int | None) -> list[tuple[str, int | None]]:
    """Parsea 'WC:2026,EC:2024' -> [('WC',2026),('EC',2024)].
    Acepta también códigos sueltos ('WC,PL') usando la temporada por defecto."""
    out: list[tuple[str, int | None]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            code, _, s = part.partition(":")
            s = s.strip()
            out.append((code.strip(), int(s) if s.isdigit() else default_season))
        else:
            out.append((part, default_season))
    return out


def _ingest_odds_api(conn, odds: OddsAPIClient, counts: dict,
                     odds_sport: str | None = None) -> None:
    """Descarga cuotas de The Odds API y las empareja con los fixtures por nombre."""
    events = odds.get_odds(
        sport=odds_sport or settings.odds_sport,
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


def _store_fd_match(conn, match: dict) -> bool:
    """Guarda un partido de football-data.org en teams/leagues/fixtures."""
    norm = normalize_fd_match(match)
    if norm is None:
        return False
    for team in (norm["home_team"], norm["away_team"]):
        upsert(conn, "teams", team)
    lg = norm["league"]
    if lg.get("id"):
        upsert(conn, "leagues", {
            "id": lg["id"], "name": lg.get("name"),
            "country": lg.get("country"), "season": lg.get("season"),
        })
    fx = norm["fixture"]
    upsert(conn, "fixtures", {
        "id": fx["id"],
        "league_id": lg.get("id"),
        "season": lg.get("season"),
        "match_date": fx["match_date"],
        "status": fx["status"],
        "home_team_id": norm["home_team"]["id"],
        "away_team_id": norm["away_team"]["id"],
        "home_goals": fx["home_goals"],
        "away_goals": fx["away_goals"],
    })
    return True


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
