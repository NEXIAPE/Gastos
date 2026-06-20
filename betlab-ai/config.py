"""
BETLAB AI - Configuración central
==================================

Carga la configuración desde variables de entorno (.env) con valores por
defecto seguros. Centraliza claves de API, rutas y parámetros del modelo para
que el resto del sistema no use constantes mágicas.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# --- Carga opcional de .env -------------------------------------------------
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv es opcional
    pass


# --- Rutas base -------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
DB_DIR = BASE_DIR / "database"
DB_PATH = DB_DIR / "betlab.db"

for _d in (DATA_DIR, REPORTS_DIR, DB_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """Parámetros globales del sistema."""

    # --- Claves de API ------------------------------------------------------
    api_football_key: str = field(default_factory=lambda: os.getenv("API_FOOTBALL_KEY", ""))
    api_football_host: str = field(
        default_factory=lambda: os.getenv("API_FOOTBALL_HOST", "v3.football.api-sports.io")
    )
    odds_api_key: str = field(default_factory=lambda: os.getenv("ODDS_API_KEY", ""))

    # --- Parámetros del Value Bet Engine ------------------------------------
    # EV mínimo para considerar una apuesta de valor (5% -> 0.05).
    min_ev: float = field(default_factory=lambda: _get_float("MIN_EV", 0.05))

    # --- Kelly Criterion ----------------------------------------------------
    # Fracción de Kelly aplicada (25% -> 0.25).
    kelly_fraction: float = field(default_factory=lambda: _get_float("KELLY_FRACTION", 0.25))
    # Bankroll inicial usado para calcular el stake monetario.
    bankroll: float = field(default_factory=lambda: _get_float("BANKROLL", 1000.0))
    # Tope máximo de stake como % del bankroll (protección).
    max_stake_pct: float = field(default_factory=lambda: _get_float("MAX_STAKE_PCT", 0.10))

    # --- Modelo de Poisson --------------------------------------------------
    # Ventaja de localía multiplicativa por defecto cuando no hay datos.
    default_home_advantage: float = field(
        default_factory=lambda: _get_float("HOME_ADVANTAGE", 1.35)
    )
    # Máximo de goles a modelar en la matriz de probabilidades.
    max_goals: int = 10

    # --- Datos --------------------------------------------------------------
    # Número de partidos recientes usados para calcular la "forma".
    form_matches: int = 5
    # Modo demo: si no hay claves de API se generan datos sintéticos.
    demo_mode: bool = field(
        default_factory=lambda: os.getenv("DEMO_MODE", "").lower() in {"1", "true", "yes"}
    )

    @property
    def has_football_key(self) -> bool:
        return bool(self.api_football_key)

    @property
    def has_odds_key(self) -> bool:
        return bool(self.odds_api_key)


settings = Settings()
