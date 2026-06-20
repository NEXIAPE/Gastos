"""
MODULE 2 - ODDS SCRAPER
=======================

Cliente para The Odds API (the-odds-api.com). Extrae cuotas de mercados
1X2 (h2h), Over/Under (totals), BTTS y Asian Handicap (spreads), y las
normaliza al formato interno (market, selection, odd).

Si no hay clave configurada devuelve listas vacías.
"""

from __future__ import annotations

from typing import Any

import requests

from config import settings

BASE_URL = "https://api.the-odds-api.com/v4"
TIMEOUT = 20

# Mapeo de markets de The Odds API -> markets internos de BETLAB.
MARKET_MAP = {
    "h2h": "1X2",
    "totals": "OU",
    "spreads": "AH",
    "btts": "BTTS",
}


class OddsAPIClient:
    """Wrapper sobre The Odds API."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.odds_api_key
        self.session = requests.Session()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def get_odds(self, sport: str = "soccer", regions: str = "eu",
                 markets: str = "h2h,totals", odds_format: str = "decimal"
                 ) -> list[dict[str, Any]]:
        """Devuelve cuotas crudas de The Odds API para un deporte."""
        if not self.enabled:
            return []
        url = f"{BASE_URL}/sports/{sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        }
        resp = self.session.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json() or []


def normalize_event_odds(event: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convierte un evento de The Odds API a filas internas:
        {bookmaker, market, selection, odd}

    Toma la *mejor* cuota se calcula después; aquí se aplana cada outcome.
    """
    home = event.get("home_team", "")
    away = event.get("away_team", "")
    rows: list[dict[str, Any]] = []

    for bookmaker in event.get("bookmakers", []):
        bk_name = bookmaker.get("title", bookmaker.get("key", ""))
        for market in bookmaker.get("markets", []):
            mkey = market.get("key")
            internal = MARKET_MAP.get(mkey)
            if internal is None:
                continue
            for outcome in market.get("outcomes", []):
                name = outcome.get("name", "")
                price = outcome.get("price")
                point = outcome.get("point")
                if price is None:
                    continue
                selection, market_label = _map_selection(internal, name, home, away, point)
                if selection is None:
                    continue
                rows.append(
                    {
                        "bookmaker": bk_name,
                        "market": market_label,
                        "selection": selection,
                        "odd": float(price),
                    }
                )
    return rows


def _map_selection(internal: str, name: str, home: str, away: str,
                   point: float | None) -> tuple[str | None, str]:
    """Normaliza el nombre de la selección y deriva la etiqueta del mercado."""
    if internal == "1X2":
        if name == home:
            return "HOME", "1X2"
        if name == away:
            return "AWAY", "1X2"
        if name.lower() == "draw":
            return "DRAW", "1X2"
        return None, "1X2"

    if internal == "OU":
        label = f"OU_{point}" if point is not None else "OU_2.5"
        if name.lower() == "over":
            return "OVER", label
        if name.lower() == "under":
            return "UNDER", label
        return None, label

    if internal == "BTTS":
        if name.lower() in {"yes", "btts yes"}:
            return "YES", "BTTS"
        if name.lower() in {"no", "btts no"}:
            return "NO", "BTTS"
        return None, "BTTS"

    if internal == "AH":
        label = f"AH_{point}" if point is not None else "AH"
        if name == home:
            return "HOME", label
        if name == away:
            return "AWAY", label
        return None, label

    return None, internal
