"""
MODULE 1 - DATA INGESTION
=========================

Cliente para API-Football (api-sports.io). Extrae fixtures, equipos, goles,
xG, posesión, tiros, lesiones y forma reciente.

Si no hay clave configurada, los métodos devuelven listas vacías para que el
orquestador pueda recurrir al generador de datos demo.
"""

from __future__ import annotations

from typing import Any

import requests

from config import settings

BASE_URL = "https://v3.football.api-sports.io"
TIMEOUT = 20


class APIFootballClient:
    """Wrapper mínimo sobre los endpoints de API-Football que usa BETLAB."""

    def __init__(self, api_key: str | None = None, host: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.api_football_key
        self.host = host or settings.api_football_host
        self.session = requests.Session()
        if self.api_key:
            # El endpoint directo (api-sports.io) usa 'x-apisports-key';
            # el acceso vía RapidAPI usa 'x-rapidapi-key' + 'x-rapidapi-host'.
            if "api-sports.io" in self.host:
                self.session.headers.update({"x-apisports-key": self.api_key})
            else:
                self.session.headers.update(
                    {
                        "x-rapidapi-key": self.api_key,
                        "x-rapidapi-host": self.host,
                    }
                )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    # --- helper de bajo nivel ----------------------------------------------
    def _get(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        url = f"{BASE_URL}/{endpoint}"
        resp = self.session.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        return payload.get("response", []) or []

    # --- endpoints públicos -------------------------------------------------
    def get_fixtures_by_date(self, date: str, league: int | None = None,
                             season: int | None = None) -> list[dict[str, Any]]:
        """Fixtures de una fecha (YYYY-MM-DD)."""
        params: dict[str, Any] = {"date": date}
        if league:
            params["league"] = league
        if season:
            params["season"] = season
        return self._get("fixtures", params)

    def get_team_statistics(self, team: int, league: int, season: int) -> dict[str, Any]:
        """Estadísticas agregadas de un equipo en una liga/temporada."""
        data = self._get("teams/statistics", {"team": team, "league": league, "season": season})
        # teams/statistics devuelve un objeto, no una lista.
        if isinstance(data, dict):
            return data
        return data[0] if data else {}

    def get_fixture_statistics(self, fixture: int) -> list[dict[str, Any]]:
        """Estadísticas por equipo de un partido (tiros, posesión, etc.)."""
        return self._get("fixtures/statistics", {"fixture": fixture})

    def get_injuries(self, fixture: int) -> list[dict[str, Any]]:
        return self._get("injuries", {"fixture": fixture})

    def get_odds_by_fixture(self, fixture: int) -> list[dict[str, Any]]:
        """Cuotas pre-partido de un fixture (varias casas y mercados)."""
        return self._get("odds", {"fixture": fixture})

    def get_team_form(self, team: int, league: int, season: int,
                      last: int = 5) -> list[dict[str, Any]]:
        """Últimos N partidos de un equipo (forma reciente)."""
        return self._get(
            "fixtures",
            {"team": team, "league": league, "season": season, "last": last},
        )


def normalize_apifootball_odds(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convierte la respuesta del endpoint /odds de API-Football a filas internas
    {bookmaker, market, selection, odd}, con el mismo vocabulario que usa el
    modelo (1X2 HOME/DRAW/AWAY · OU_2.5 OVER/UNDER · BTTS YES/NO).
    """
    rows: list[dict[str, Any]] = []
    for event in events or []:
        for bk in event.get("bookmakers", []):
            bk_name = bk.get("name", str(bk.get("id", "")))
            for bet in bk.get("bets", []):
                bname = (bet.get("name") or "").strip().lower()
                for val in bet.get("values", []):
                    raw = (val.get("value") or "").strip()
                    try:
                        odd = float(val.get("odd"))
                    except (TypeError, ValueError):
                        continue
                    selection, market_label = _map_apifootball_value(bname, raw)
                    if selection is None:
                        continue
                    rows.append({
                        "bookmaker": bk_name,
                        "market": market_label,
                        "selection": selection,
                        "odd": odd,
                    })
    return rows


def _map_apifootball_value(bet_name: str, value: str) -> tuple[str | None, str]:
    """Mapea (nombre de apuesta, valor) de API-Football al formato interno."""
    v = value.strip().lower()

    if bet_name == "match winner":          # 1X2
        if v == "home":
            return "HOME", "1X2"
        if v == "draw":
            return "DRAW", "1X2"
        if v == "away":
            return "AWAY", "1X2"
        return None, "1X2"

    if bet_name == "goals over/under":       # Over/Under (solo línea 2.5)
        if v == "over 2.5":
            return "OVER", "OU_2.5"
        if v == "under 2.5":
            return "UNDER", "OU_2.5"
        return None, "OU_2.5"

    if bet_name == "both teams score":       # BTTS
        if v == "yes":
            return "YES", "BTTS"
        if v == "no":
            return "NO", "BTTS"
        return None, "BTTS"

    return None, bet_name


def parse_statistic_value(stats: list[dict[str, Any]], wanted: str) -> float | None:
    """Extrae un valor concreto de la estructura statistics de un fixture."""
    for item in stats:
        if item.get("type") == wanted:
            value = item.get("value")
            if value is None:
                return None
            if isinstance(value, str) and value.endswith("%"):
                try:
                    return float(value.rstrip("%"))
                except ValueError:
                    return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None
