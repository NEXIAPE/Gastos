"""
FUENTE - PARTIDOS INTERNACIONALES (SELECCIONES)
===============================================

Carga la base pública (CSV) de TODOS los partidos entre selecciones desde 1872
hasta el presente (incluye Mundiales, Eurocopas, Copas América, Nations League,
eliminatorias y amistosos), más los fixtures del Mundial en curso.

Es una única fuente con nombres de equipo consistentes, lo que permite construir
historial real para cada selección (cientos de partidos) y evaluar el Mundial.

Si no hay conexión, usa una copia local cacheada en data/.
"""

from __future__ import annotations

import csv
import io
import zlib
from typing import Any

import requests

from config import DATA_DIR, settings

DEFAULT_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
CACHE_PATH = DATA_DIR / "intl_results.csv"
TIMEOUT = 60


def team_id(name: str) -> int:
    """ID estable derivado del nombre normalizado (misma selección => mismo id)."""
    return zlib.crc32(name.strip().lower().encode("utf-8"))


def fixture_id(date: str, home: str, away: str) -> int:
    """ID estable de un partido (evita duplicados al recargar)."""
    return zlib.crc32(f"{date}|{home.lower()}|{away.lower()}".encode("utf-8"))


def _download() -> str | None:
    url = settings.intl_results_url or DEFAULT_URL
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(resp.text, encoding="utf-8")
        return resp.text
    except Exception:
        if CACHE_PATH.exists():
            return CACHE_PATH.read_text(encoding="utf-8")
        return None


def load_results(since_year: int | None = None) -> list[dict[str, Any]]:
    """Devuelve los partidos internacionales (opcionalmente desde un año)."""
    text = _download()
    if not text:
        return []
    out: list[dict[str, Any]] = []
    for row in csv.DictReader(io.StringIO(text)):
        date = row.get("date", "") or ""
        year = int(date[:4]) if date[:4].isdigit() else 0
        if since_year and year < since_year:
            continue
        out.append(row)
    return out


def normalize_intl_match(row: dict[str, Any]) -> dict[str, Any] | None:
    """Convierte una fila del CSV al formato interno (teams/fixture)."""
    home = (row.get("home_team") or "").strip()
    away = (row.get("away_team") or "").strip()
    if not home or not away:
        return None

    def _score(x: Any) -> int | None:
        try:
            return int(x)
        except (TypeError, ValueError):
            return None

    hg, ag = _score(row.get("home_score")), _score(row.get("away_score"))
    status = "FT" if (hg is not None and ag is not None) else "NS"
    date = row.get("date", "") or ""
    year = int(date[:4]) if date[:4].isdigit() else None

    return {
        "home": {"id": team_id(home), "name": home},
        "away": {"id": team_id(away), "name": away},
        "fixture_id": fixture_id(date, home, away),
        "match_date": date,
        "status": status,
        "home_goals": hg,
        "away_goals": ag,
        "season": year,
        "tournament": row.get("tournament", ""),
    }
