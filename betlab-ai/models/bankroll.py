"""
MODULE 4 - BANKROLL MANAGER
===========================

Gestión automática de riesgo sobre la curva de bankroll (capital inicial +
beneficio realizado). Calcula el drawdown respecto al máximo histórico (peak)
y fija el modo de operación:

  * Drawdown > 10%  -> modo REDUCED      : stakes al 50%.
  * Drawdown > 20%  -> modo CONSERVATION : solo confianza > 90, stake máx. 1%,
                                           y SIN combinadas.
  * En otro caso    -> modo NORMAL.

`get_state()` recalcula y persiste el estado en la tabla `bankroll_state`, y
expone los parámetros que el resto del sistema debe respetar.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import settings
from database import query_df, session


@dataclass
class BankrollState:
    initial: float
    current: float
    peak: float
    drawdown: float          # fracción [0,1]
    mode: str                # NORMAL / REDUCED / CONSERVATION
    stake_multiplier: float  # factor a aplicar al stake (1.0 / 0.5 / cap 1%)
    min_confidence: float    # confianza mínima exigida en este modo
    allow_parlays: bool

    @property
    def conservation(self) -> bool:
        return self.mode == "CONSERVATION"


def _initial_bankroll() -> float:
    df = query_df("SELECT initial_bankroll FROM bankroll_state WHERE id = 1")
    if df.empty:
        return settings.bankroll
    return float(df["initial_bankroll"].iloc[0])


def _equity_curve(initial: float) -> tuple[float, float]:
    """Devuelve (bankroll_actual, peak) a partir del bet_log liquidado."""
    df = query_df(
        "SELECT profit FROM bet_log "
        "WHERE status IN ('WON','LOST','VOID') AND settled_at IS NOT NULL "
        "ORDER BY settled_at, id"
    )
    bankroll = initial
    peak = initial
    for profit in df["profit"] if not df.empty else []:
        bankroll += float(profit)
        peak = max(peak, bankroll)
    return bankroll, peak


def get_state(persist: bool = True) -> BankrollState:
    """Recalcula el estado del bankroll y (opcionalmente) lo persiste."""
    initial = _initial_bankroll()
    current, peak = _equity_curve(initial)
    drawdown = (peak - current) / peak if peak > 0 else 0.0

    if drawdown > settings.drawdown_conserve:
        mode = "CONSERVATION"
        stake_multiplier = 1.0     # el stake se topa por % en lugar de escalar
        min_conf = settings.conserve_min_confidence
        allow_parlays = False
    elif drawdown > settings.drawdown_reduce:
        mode = "REDUCED"
        stake_multiplier = 0.5
        min_conf = settings.min_confidence
        allow_parlays = True
    else:
        mode = "NORMAL"
        stake_multiplier = 1.0
        min_conf = settings.min_confidence
        allow_parlays = True

    state = BankrollState(
        initial=round(initial, 2),
        current=round(current, 2),
        peak=round(peak, 2),
        drawdown=round(drawdown, 4),
        mode=mode,
        stake_multiplier=stake_multiplier,
        min_confidence=min_conf,
        allow_parlays=allow_parlays,
    )

    if persist:
        with session() as conn:
            conn.execute(
                "INSERT INTO bankroll_state (id, initial_bankroll, current_bankroll, "
                " mode, stake_multiplier, updated_at) "
                "VALUES (1, ?, ?, ?, ?, datetime('now')) "
                "ON CONFLICT(id) DO UPDATE SET current_bankroll=excluded.current_bankroll, "
                " mode=excluded.mode, stake_multiplier=excluded.stake_multiplier, "
                " updated_at=excluded.updated_at",
                (state.initial, state.current, state.mode, state.stake_multiplier),
            )
    return state


def apply_risk_rules(stake_amount: float, stake_pct: float,
                     state: BankrollState) -> float:
    """
    Ajusta un stake a las reglas de riesgo activas:
      * REDUCED      -> ×0.5
      * CONSERVATION -> topado al 1% del bankroll actual
    """
    adjusted = stake_amount * state.stake_multiplier
    if state.conservation:
        cap = settings.conserve_max_stake_pct * state.current
        adjusted = min(adjusted, cap)
    return round(adjusted, 2)
