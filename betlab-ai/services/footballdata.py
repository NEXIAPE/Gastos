"""
FUENTE ALTERNATIVA - FOOTBALL-DATA.ORG
======================================

Cliente para football-data.org (v4). A diferencia del plan gratuito de
API-Football, su capa gratuita SÍ cubre temporadas actuales de las grandes
competiciones, incluido el Mundial (FIFA World Cup, código 'WC').

Provee fixtures, resultados e historial; las CUOTAS se obtienen aparte
(The Odds API). Si no hay token configurado, los métodos devuelven listas
vacías para que el orquestador recurra a otra fuente o al modo demo.

Competiciones gratuitas (código): WC, CL, EC, PL, PD, SA, BL1, FL1, DED,
PPL, ELC, BSA, CLI.
"""

from __future__ import annotations

from typing import Any

import requests

from config import settings

BASE_URL = "https://api.football-data.org/v4"
TIMEOUT = 20


class FootballDataClient:
    """Wrapper mínimo sobre football-data.org."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token if token is not None else settings.footballdata_token
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({"X-Auth-Token": self.token})

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def get_matches(self, competition: str, season: int | None = None,
                    date_from: str | None = None, date_to: str | None = None,
                    status: str | None = None) -> list[dict[str, Any]]:
        """Partidos de una competición (código, p.ej. 'WC', 'PL')."""
        if not self.enabled or not competition:
            return []
        url = f"{BASE_URL}/competitions/{competition}/matches"
        params: dict[str, Any] = {}
        if season:
            params["season"] = season
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if status:
            params["status"] = status
        resp = self.session.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("matches", []) or []


def normalize_fd_match(match: dict[str, Any]) -> dict[str, Any] | None:
    """
    Convierte un partido de football-data.org a la estructura interna usada
    para almacenar fixtures/teams/leagues.
    """
    home = match.get("homeTeam") or {}
    away = match.get("awayTeam") or {}
    if not (home.get("id") and away.get("id")):
        return None

    comp = match.get("competition") or {}
    area = match.get("area") or {}
    season_info = match.get("season") or {}
    start = str(season_info.get("startDate") or "")[:4]
    season = int(start) if start.isdigit() else None

    full_time = (match.get("score") or {}).get("fullTime") or {}
    status = "FT" if match.get("status") == "FINISHED" else "NS"

    def _team(t: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": t["id"],
            "name": t.get("name") or t.get("shortName") or str(t["id"]),
            "logo": t.get("crest", ""),
        }

    return {
        "home_team": _team(home),
        "away_team": _team(away),
        "league": {
            "id": comp.get("id"),
            "name": comp.get("name"),
            "country": area.get("name"),
            "season": season,
        },
        "fixture": {
            "id": match["id"],
            "match_date": match.get("utcDate"),
            "status": status,
            "home_goals": full_time.get("home"),
            "away_goals": full_time.get("away"),
        },
    }
