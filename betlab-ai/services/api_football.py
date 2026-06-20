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

    def get_team_form(self, team: int, league: int, season: int,
                      last: int = 5) -> list[dict[str, Any]]:
        """Últimos N partidos de un equipo (forma reciente)."""
        return self._get(
            "fixtures",
            {"team": team, "league": league, "season": season, "last": last},
        )


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
