"""
BETLAB AI - Estrategias y combinadas
====================================

A partir de los picks generados por el Value Bet Engine construye los
productos de la estrategia diaria:

  * Ordena todas las apuestas por EV, Probabilidad y Confianza.
  * Filtra el pool elegible:  EV > 5%  ·  Confianza ≥ mínimo activo
    (· rango de cuota [ODD_MIN, ODD_MAX] opcional, desactivado por defecto).
  * A) PICK PREMIUM DEL DÍA  — mejor combinación de EV y confianza.
  * B) TOP 5 VALUE BETS.
  * C) COMBINADA CONSERVADORA (máx. 2 selecciones).
  * D) COMBINADA MODERADA    (máx. 3 selecciones).
  * E) COMBINADA AGRESIVA     (máx. 5 selecciones).

Para cada combinada: cuota total, probabilidad conjunta, EV estimado y riesgo.
Una combinada con EV ≤ 0 se descarta automáticamente y nunca se fuerza: si no
hay ninguna combinación con valor positivo, `has_combos` es False y la capa de
presentación muestra "NO HAY COMBINADAS DE VALOR HOY".

La probabilidad conjunta y la cuota total son el producto de las patas, lo que
asume independencia entre partidos; por eso cada combinada usa como máximo una
selección por fixture (no se combinan resultados correlacionados del mismo
partido).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config import settings
from models.bankroll import BankrollState, get_state
from models.value_bet import ValueBet, detect_value_bets


@dataclass
class Leg:
    match: str
    market: str
    selection: str
    odd: float
    model_prob: float
    ev: float
    confidence: float


@dataclass
class Parlay:
    name: str
    max_legs: int
    legs: list[Leg]
    total_odd: float
    joint_prob: float
    ev: float
    risk: str


@dataclass
class StrategyReport:
    by_ev: list[ValueBet]
    by_prob: list[ValueBet]
    by_confidence: list[ValueBet]
    pool: list[ValueBet]
    premium: ValueBet | None
    top5: list[ValueBet]
    parlays: list[Parlay]            # solo combinadas con EV > 0
    has_combos: bool
    bankroll_mode: str = "NORMAL"
    parlays_blocked: bool = False    # True si el modo conservación las bloquea


# --- utilidades -------------------------------------------------------------
def _premium_score(b: ValueBet) -> float:
    """Combinación equilibrada de confianza (0-1) y EV (normalizado a 20%)."""
    return 0.5 * (b.confidence / 100.0) + 0.5 * min(b.ev / 0.20, 1.0)


def _risk_adjusted_ev(b: ValueBet) -> float:
    """EV ajustado por riesgo: pondera el EV por la confianza del pick."""
    return b.ev * (b.confidence / 100.0)


def _parlay_risk(joint_prob: float, n_legs: int) -> str:
    """Riesgo cualitativo según la probabilidad conjunta de acierto."""
    if joint_prob >= 0.40:
        return "Bajo"
    if joint_prob >= 0.25:
        return "Medio"
    if joint_prob >= 0.12:
        return "Alto"
    return "Muy alto"


def _to_leg(b: ValueBet) -> Leg:
    return Leg(match=b.match, market=b.market, selection=b.selection,
               odd=b.odd, model_prob=b.model_prob, ev=b.ev, confidence=b.confidence)


def fmt_market(market: str) -> str:
    """Etiqueta legible del mercado: O/U 1.5, Hándicap -1.5, 1X2, BTTS."""
    if market.startswith("OU_"):
        return f"O/U {market[3:]}"
    if market.startswith("AH_"):
        return f"Hándicap {market[3:]}"
    return market


def fmt_selection(selection: str) -> str:
    """Etiqueta legible de la selección."""
    return {"HOME": "Local", "DRAW": "Empate", "AWAY": "Visitante",
            "OVER": "Over", "UNDER": "Under", "YES": "Sí", "NO": "No"}.get(selection, selection)


def describe_pick(match: str, market: str, selection: str) -> str:
    """Explica en lenguaje simple QUÉ apostar (con el nombre del equipo).
    Es lo que tenés que marcar en la casa de apuestas."""
    home, _, away = match.partition(" vs ")
    home, away = home.strip(), away.strip()
    if market == "1X2":
        return {"HOME": f"Gana {home}",
                "DRAW": "Empate",
                "AWAY": f"Gana {away}"}.get(selection, selection)
    if market.startswith("OU_"):
        line = market[3:]
        if selection == "OVER":
            return f"Más de {line} goles en el partido (sumando ambos equipos)"
        if selection == "UNDER":
            return f"Menos de {line} goles en el partido (sumando ambos equipos)"
    if market == "BTTS":
        return ("Ambos equipos marcan: SÍ" if selection == "YES"
                else "Ambos equipos marcan: NO")
    if market.startswith("AH_"):
        team = home if selection == "HOME" else away
        try:
            line = float(market[3:])
        except ValueError:
            return f"Hándicap asiático: {home if selection=='HOME' else away} {market[3:]}"
        meanings = {
            -0.5: f"gana {team}",
            0.5: f"{team} gana o empata",
            -1.5: f"{team} gana por 2 goles o más",
            1.5: f"{team} gana, empata o pierde por 1 gol",
            -2.5: f"{team} gana por 3 goles o más",
            2.5: f"{team} gana, empata o pierde por 1 o 2 goles",
        }
        meaning = meanings.get(line, f"{team} con línea {line:+g}")
        return f"Hándicap asiático ({line:+g}): {meaning}"
    return f"{fmt_market(market)} {fmt_selection(selection)}"


def _select_legs(max_legs: int, bets: list[ValueBet]) -> list[ValueBet]:
    """Elige hasta `max_legs` patas (una por fixture) por _premium_score."""
    chosen: list[ValueBet] = []
    used_fixtures: set[int] = set()
    for b in sorted(bets, key=_premium_score, reverse=True):
        if b.fixture_id in used_fixtures:
            continue
        chosen.append(b)
        used_fixtures.add(b.fixture_id)
        if len(chosen) == max_legs:
            break
    return chosen


def _build_parlay(name: str, max_legs: int, bets: list[ValueBet]) -> Parlay | None:
    """
    Construye una combinada con HASTA `max_legs` selecciones (una por fixture).
    Devuelve None si no hay al menos 2 patas o si el EV resultante no es positivo.
    """
    chosen = _select_legs(max_legs, bets)
    if len(chosen) < 2:
        return None  # una combinada necesita al menos 2 selecciones

    total_odd = 1.0
    joint_prob = 1.0
    for b in chosen:
        total_odd *= b.odd
        joint_prob *= b.model_prob

    ev = joint_prob * total_odd - 1.0
    if ev <= 0:
        return None  # descarte automático de EV negativo

    return Parlay(
        name=name,
        max_legs=max_legs,
        legs=[_to_leg(b) for b in chosen],
        total_odd=round(total_odd, 2),
        joint_prob=round(joint_prob, 4),
        ev=round(ev, 4),
        risk=_parlay_risk(joint_prob, len(chosen)),
    )


def build_strategies(bets: list[ValueBet] | None = None,
                     state: BankrollState | None = None) -> StrategyReport:
    """Genera el informe de estrategias del día a partir de los picks."""
    if bets is None:
        bets = detect_value_bets()
    if state is None:
        state = get_state()

    # 1) Ordenaciones de TODAS las apuestas detectadas.
    by_ev = sorted(bets, key=lambda b: b.ev, reverse=True)
    by_prob = sorted(bets, key=lambda b: b.model_prob, reverse=True)
    by_confidence = sorted(bets, key=lambda b: b.confidence, reverse=True)

    # 2) Pool elegible: EV>5% y confianza por encima del mínimo activo.
    #    El rango de cuota [odd_min, odd_max] está desactivado por defecto
    #    (configurable con ODD_MIN/ODD_MAX en .env).
    min_conf = state.min_confidence
    pool = [
        b for b in bets
        if b.ev > settings.min_ev
        and b.confidence >= min_conf
        and settings.odd_min <= b.odd <= settings.odd_max
    ]

    # A) Pick premium: mayor EV AJUSTADO POR RIESGO.
    premium = max(pool, key=_risk_adjusted_ev) if pool else None

    # B) Top 5 value bets (por EV) dentro del pool elegible.
    top5 = sorted(pool, key=lambda b: b.ev, reverse=True)[:5]

    # C/D/E) Combinadas (descartando EV<=0 y sin forzar patas).
    # En modo conservación NO se permiten combinadas.
    parlays: list[Parlay] = []
    parlays_blocked = not state.allow_parlays
    if state.allow_parlays:
        seen_sizes: set[int] = set()
        for name, max_legs in (("Conservadora", 2), ("Moderada", 3), ("Agresiva", 5)):
            parlay = _build_parlay(name, max_legs, pool)
            # Evita combinadas duplicadas (mismo nº de patas que otra ya incluida).
            if parlay is not None and len(parlay.legs) not in seen_sizes:
                parlays.append(parlay)
                seen_sizes.add(len(parlay.legs))

    return StrategyReport(
        by_ev=by_ev,
        by_prob=by_prob,
        by_confidence=by_confidence,
        pool=pool,
        premium=premium,
        top5=top5,
        parlays=parlays,
        has_combos=bool(parlays),
        bankroll_mode=state.mode,
        parlays_blocked=parlays_blocked,
    )
