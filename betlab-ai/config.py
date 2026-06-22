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

    # Carga el .env de la carpeta del proyecto, sin depender del directorio
    # de trabajo desde el que se ejecute el comando.
    _ENV_PATH = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=_ENV_PATH if _ENV_PATH.exists() else None)
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


def _get_secret(name: str) -> str:
    """Lee una clave de entorno limpiando espacios y comentarios inline (#...)
    que algunas versiones de dotenv no eliminan. Las claves reales no llevan
    espacios ni '#', así que esto es seguro."""
    raw = os.getenv(name, "") or ""
    return raw.split("#", 1)[0].strip()


@dataclass(frozen=True)
class Settings:
    """Parámetros globales del sistema."""

    # --- Claves de API ------------------------------------------------------
    api_football_key: str = field(default_factory=lambda: _get_secret("API_FOOTBALL_KEY"))
    api_football_host: str = field(
        default_factory=lambda: os.getenv("API_FOOTBALL_HOST") or "v3.football.api-sports.io"
    )
    odds_api_key: str = field(default_factory=lambda: _get_secret("ODDS_API_KEY"))
    # Clave de competición de The Odds API (p.ej. soccer_fifa_world_cup,
    # soccer_epl, soccer_spain_la_liga, upcoming). Solo aplica a esa fuente.
    odds_sport: str = field(default_factory=lambda: os.getenv("ODDS_SPORT", "upcoming"))
    odds_regions: str = field(default_factory=lambda: os.getenv("ODDS_REGIONS", "eu"))
    # football-data.org: fuente gratuita con temporadas ACTUALES (incl. Mundial).
    footballdata_token: str = field(default_factory=lambda: _get_secret("FOOTBALLDATA_TOKEN"))
    # Código de competición de football-data.org (WC, PL, PD, CL, SA, BL1, FL1...).
    fd_competition: str = field(default_factory=lambda: (os.getenv("FD_COMPETITION", "") or "").strip())
    # Base pública de TODOS los partidos internacionales (selecciones) para el
    # historial. Se activa con FD_COMPETITION=INTL.
    intl_results_url: str = field(default_factory=lambda: (os.getenv("INTL_RESULTS_URL", "") or "").strip())
    # Año desde el que se carga historial internacional (recencia vs volumen).
    intl_since: int = field(default_factory=lambda: int(_get_float("INTL_SINCE", 2018)))
    # Filtro opcional de ingesta para no agotar la cuota de la API: limita la
    # descarga a una liga/competición y temporada concretas. Mundial -> 1 / 2026.
    league_id: int | None = field(
        default_factory=lambda: int(os.environ["LEAGUE_ID"]) if os.getenv("LEAGUE_ID") else None
    )
    season: int | None = field(
        default_factory=lambda: int(os.environ["SEASON"]) if os.getenv("SEASON") else None
    )

    # --- Value Bet Engine ---------------------------------------------------
    # EV mínimo para considerar una apuesta de valor (5% -> 0.05).
    min_ev: float = field(default_factory=lambda: _get_float("MIN_EV", 0.05))
    # Score de confianza mínimo (0-100) para mostrar una apuesta.
    # 80 => Value Pick (80-84), Strong (85-89) y Elite (90-100).
    min_confidence: float = field(default_factory=lambda: _get_float("MIN_CONFIDENCE", 80.0))
    # Diferencia mínima |prob_modelo - prob_implícita| (No Bet si es menor).
    min_prob_edge: float = field(default_factory=lambda: _get_float("MIN_PROB_EDGE", 0.03))
    # Rango de cuota elegible para estrategias/combinadas.
    # Por defecto sin restricción; fija ODD_MIN/ODD_MAX en .env para activarlo.
    odd_min: float = field(default_factory=lambda: _get_float("ODD_MIN", 1.01))
    odd_max: float = field(default_factory=lambda: _get_float("ODD_MAX", 1000.0))

    # --- No Bet Engine ------------------------------------------------------
    # Nº de bajas importantes a partir del cual se marca NO BET.
    max_key_injuries: int = field(default_factory=lambda: int(_get_float("MAX_KEY_INJURIES", 3)))
    # Mínimo de partidos históricos por equipo para considerar info suficiente.
    min_history_matches: int = field(default_factory=lambda: int(_get_float("MIN_HISTORY", 5)))

    # --- Bankroll Manager ---------------------------------------------------
    # Caída de bankroll que reduce stakes al 50%.
    drawdown_reduce: float = field(default_factory=lambda: _get_float("DD_REDUCE", 0.10))
    # Caída que activa modo conservación.
    drawdown_conserve: float = field(default_factory=lambda: _get_float("DD_CONSERVE", 0.20))
    # En modo conservación: confianza mínima y stake máximo.
    conserve_min_confidence: float = field(
        default_factory=lambda: _get_float("CONSERVE_MIN_CONF", 90.0))
    conserve_max_stake_pct: float = field(
        default_factory=lambda: _get_float("CONSERVE_MAX_STAKE", 0.01))

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
    # Vida media (días) para ponderar partidos por recencia en los ratings.
    # Partidos más viejos pesan menos. ~540 días ≈ 1.5 años.
    recency_halflife_days: float = field(
        default_factory=lambda: _get_float("RECENCY_HALFLIFE_DAYS", 540.0))
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
