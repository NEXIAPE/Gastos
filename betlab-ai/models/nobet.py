"""
MODULE 3 - NO BET ENGINE
========================

Descarta automáticamente partidos/selecciones y SIEMPRE explica el motivo.

Reglas a nivel de PARTIDO (descartan el fixture completo):
  * Demasiadas bajas importantes (>= MAX_KEY_INJURIES en algún equipo).
  * Rotaciones masivas (proxy: bajas/sanciones muy elevadas en un equipo).
  * Partido amistoso (la liga es de tipo friendly).
  * Información insuficiente (histórico < MIN_HISTORY partidos en algún equipo).

Reglas a nivel de SELECCIÓN (descartan una apuesta concreta):
  * EV menor a 5%.
  * Diferencia de probabilidades (modelo vs mercado) menor a 3%.

Devuelve listas de razones legibles; nunca descarta en silencio.
"""

from __future__ import annotations

from config import settings
from database import query_df

# Umbral proxy para "rotaciones masivas" cuando no hay datos de alineación.
ROTATION_PROXY = 5
FRIENDLY_KEYWORDS = ("friendly", "amistoso", "club friendlies")


class NoBetEngine:
    """Evalúa fixtures y selecciones; precarga conteos de bajas e historial."""

    def __init__(self) -> None:
        self.injuries = self._injury_counts()
        self.history = self._history_counts()

    @staticmethod
    def _injury_counts() -> dict[int, int]:
        df = query_df("SELECT team_id, COUNT(*) AS n FROM injuries GROUP BY team_id")
        return {int(r.team_id): int(r.n) for r in df.itertuples()} if not df.empty else {}

    @staticmethod
    def _history_counts() -> dict[int, int]:
        df = query_df(
            "SELECT team_id, COUNT(*) AS n FROM ("
            "  SELECT home_team_id AS team_id FROM fixtures WHERE home_goals IS NOT NULL "
            "  UNION ALL "
            "  SELECT away_team_id AS team_id FROM fixtures WHERE home_goals IS NOT NULL"
            ") GROUP BY team_id"
        )
        return {int(r.team_id): int(r.n) for r in df.itertuples()} if not df.empty else {}

    # --- nivel partido -----------------------------------------------------
    def evaluate_fixture(self, home_id: int, away_id: int,
                         league_name: str | None = None) -> list[str]:
        """Devuelve razones de NO BET a nivel partido (vacío => apostable)."""
        reasons: list[str] = []

        inj_h = self.injuries.get(home_id, 0)
        inj_a = self.injuries.get(away_id, 0)
        if inj_h >= settings.max_key_injuries or inj_a >= settings.max_key_injuries:
            reasons.append(
                f"Demasiadas bajas importantes (local={inj_h}, visitante={inj_a})")
        elif inj_h >= ROTATION_PROXY or inj_a >= ROTATION_PROXY:
            reasons.append("Posibles rotaciones masivas (bajas/sanciones elevadas)")

        if league_name and any(k in league_name.lower() for k in FRIENDLY_KEYWORDS):
            reasons.append("Partido amistoso")

        hist_h = self.history.get(home_id, 0)
        hist_a = self.history.get(away_id, 0)
        if hist_h < settings.min_history_matches or hist_a < settings.min_history_matches:
            reasons.append(
                f"Información insuficiente (partidos: local={hist_h}, visitante={hist_a})")

        return reasons

    # --- nivel selección ---------------------------------------------------
    @staticmethod
    def evaluate_selection(model_prob: float, implied_prob: float, ev: float) -> list[str]:
        """Razones de NO BET para una selección concreta."""
        reasons: list[str] = []
        if ev < settings.min_ev:
            reasons.append(f"EV menor a {settings.min_ev:.0%} (EV={ev:.1%})")
        if abs(model_prob - implied_prob) < settings.min_prob_edge:
            reasons.append(
                f"Diferencia de probabilidades < {settings.min_prob_edge:.0%} "
                f"(|{model_prob:.0%}-{implied_prob:.0%}|)")
        return reasons
