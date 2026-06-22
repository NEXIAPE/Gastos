"""
MODULE 4 - POISSON MODEL
========================

Modela el número de goles de cada equipo como variables de Poisson
independientes con medias `lambda_home` y `lambda_away`. A partir de la
matriz conjunta de marcadores deriva:

  * resultado más probable,
  * P(victoria local / empate / victoria visitante),
  * P(Over X.5),
  * P(BTTS - ambos marcan),
  * P(marcador exacto).

La independencia entre goles es la hipótesis estándar del modelo de Poisson
para fútbol (Maher, 1982). Es una aproximación: subestima ligeramente empates,
pero es robusta y totalmente basada en probabilidad, no en intuición.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import poisson


@dataclass
class PoissonModel:
    """Modelo de goles esperados para un partido."""

    lambda_home: float
    lambda_away: float
    max_goals: int = 10

    def __post_init__(self) -> None:
        self.lambda_home = max(0.05, float(self.lambda_home))
        self.lambda_away = max(0.05, float(self.lambda_away))
        self._matrix = self._score_matrix()

    # --- matriz conjunta de marcadores -------------------------------------
    def _score_matrix(self) -> np.ndarray:
        """Matriz (max_goals+1)x(max_goals+1): P(home=i, away=j)."""
        goals = np.arange(0, self.max_goals + 1)
        home_pmf = poisson.pmf(goals, self.lambda_home)
        away_pmf = poisson.pmf(goals, self.lambda_away)
        # producto externo = independencia
        return np.outer(home_pmf, away_pmf)

    @property
    def matrix(self) -> np.ndarray:
        return self._matrix

    # --- mercados -----------------------------------------------------------
    def prob_home_win(self) -> float:
        return float(np.tril(self._matrix, -1).sum())

    def prob_draw(self) -> float:
        return float(np.trace(self._matrix))

    def prob_away_win(self) -> float:
        return float(np.triu(self._matrix, 1).sum())

    def prob_over(self, line: float = 2.5) -> float:
        """P(total de goles > line). Para .5 no hay push."""
        i, j = np.indices(self._matrix.shape)
        totals = i + j
        return float(self._matrix[totals > line].sum())

    def prob_under(self, line: float = 2.5) -> float:
        return 1.0 - self.prob_over(line)

    def prob_btts(self) -> float:
        """P(ambos equipos marcan al menos 1 gol)."""
        no_home = self._matrix[0, :].sum()      # local no marca
        no_away = self._matrix[:, 0].sum()      # visitante no marca
        none = self._matrix[0, 0]               # 0-0 (contado dos veces)
        return float(1.0 - (no_home + no_away - none))

    def prob_handicap(self, side: str, line: float) -> float:
        """P(el equipo 'side' cubre el hándicap 'line'), p.ej. +1.5 o -0.5.
        Exacto en líneas .5 (sin push). 'side' = 'HOME' o 'AWAY'."""
        i, j = np.indices(self._matrix.shape)
        margin = (i - j) if side.upper() == "HOME" else (j - i)
        return float(self._matrix[margin + line > 0].sum())

    def prob_exact_score(self, home_goals: int, away_goals: int) -> float:
        if home_goals > self.max_goals or away_goals > self.max_goals:
            return 0.0
        return float(self._matrix[home_goals, away_goals])

    def most_likely_score(self) -> tuple[int, int, float]:
        idx = np.unravel_index(np.argmax(self._matrix), self._matrix.shape)
        return int(idx[0]), int(idx[1]), float(self._matrix[idx])

    def expected_goals(self) -> tuple[float, float]:
        return self.lambda_home, self.lambda_away

    def summary(self) -> dict[str, float]:
        """Diccionario con todas las probabilidades de mercado principales."""
        h, a, p = self.most_likely_score()
        return {
            "lambda_home": self.lambda_home,
            "lambda_away": self.lambda_away,
            "home_win": self.prob_home_win(),
            "draw": self.prob_draw(),
            "away_win": self.prob_away_win(),
            "over_2_5": self.prob_over(2.5),
            "under_2_5": self.prob_under(2.5),
            "btts": self.prob_btts(),
            "most_likely_home": h,
            "most_likely_away": a,
            "most_likely_prob": p,
        }
