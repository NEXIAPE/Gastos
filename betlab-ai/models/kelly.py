"""
MODULE 6 - KELLY CRITERION
==========================

Calcula el stake óptimo según el criterio de Kelly, aplicando una fracción
conservadora (por defecto 25% -> "Kelly Fraccionado"). El Kelly completo
maximiza el crecimiento logarítmico del bankroll a largo plazo pero es muy
volátil; usar 1/4 de Kelly reduce drásticamente la varianza con un coste
mínimo en crecimiento esperado.

Fórmula (cuota decimal `o`, probabilidad `p`):

    b = o - 1                      (ganancia neta por unidad apostada)
    f* = (b * p - (1 - p)) / b     (fracción de Kelly completo)
    stake = max(0, f*) * fraccion  (fracción aplicada, nunca negativa)
"""

from __future__ import annotations

from dataclasses import dataclass

from config import settings


@dataclass
class StakeRecommendation:
    kelly_full: float       # fracción de Kelly completo
    kelly_fraction: float   # fracción aplicada (p.ej. 25% de la completa)
    stake_pct: float        # % del bankroll a apostar (tras tope)
    stake_amount: float     # importe monetario
    risk: str               # etiqueta cualitativa de riesgo


def kelly_fraction(prob: float, odd: float) -> float:
    """Fracción de Kelly completo (puede ser negativa => no apostar)."""
    b = odd - 1.0
    if b <= 0:
        return 0.0
    f = (b * prob - (1.0 - prob)) / b
    return f


def _risk_label(stake_pct: float) -> str:
    if stake_pct <= 0:
        return "Sin valor"
    if stake_pct < 0.01:
        return "Bajo"
    if stake_pct < 0.03:
        return "Medio"
    if stake_pct < 0.06:
        return "Alto"
    return "Muy alto"


def recommend_stake(prob: float, odd: float,
                    bankroll: float | None = None,
                    fraction: float | None = None,
                    max_stake_pct: float | None = None) -> StakeRecommendation:
    """Devuelve la recomendación de stake (Kelly fraccionado + tope de riesgo)."""
    bankroll = settings.bankroll if bankroll is None else bankroll
    fraction = settings.kelly_fraction if fraction is None else fraction
    max_stake_pct = settings.max_stake_pct if max_stake_pct is None else max_stake_pct

    full = kelly_fraction(prob, odd)
    applied = max(0.0, full) * fraction
    stake_pct = min(applied, max_stake_pct)   # tope de protección
    stake_amount = round(stake_pct * bankroll, 2)

    return StakeRecommendation(
        kelly_full=round(full, 4),
        kelly_fraction=round(applied, 4),
        stake_pct=round(stake_pct, 4),
        stake_amount=stake_amount,
        risk=_risk_label(stake_pct),
    )
