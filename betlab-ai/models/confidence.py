"""
BETLAB AI - Score Final de Confianza
====================================

Combina 10 factores en un único Score de Confianza de 0 a 100 para cada
candidata a value bet. Cada factor se orienta a la *selección concreta*
(p.ej. HOME, OVER, BTTS YES) y devuelve un valor en [0,1] que indica cuánto
apoya esa apuesta; el score es la media ponderada (renormalizada según los
factores aplicables al mercado).

Factores y peso base:

    1. Expected Goals (xG) ............ 14
    2. Elo Rating .................... 16
    3. Forma últimos 5 partidos ...... 10
    4. Forma últimos 10 partidos ......  8
    5. Lesiones ponderadas ...........  8
    6. Fatiga por calendario .........  6
    7. Rendimiento local ............. 10
    8. Rendimiento visitante ......... 10
    9. Historial H2H .................  8
   10. Movimiento de cuotas .......... 10
                                       ---
                                       100

Clasificación del score:
    90-100 -> Elite Pick
    80-89  -> Strong Pick
    70-79  -> Lean
    < 70   -> No Bet
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from database import query_df
from models.elo import BASE_ELO, compute_elo

# --- Pesos base de cada factor (suman 100) ---------------------------------
FACTOR_WEIGHTS = {
    "poisson": 16.0,        # convicción del modelo de Poisson (edge vs mercado)
    "xg": 14.0,
    "elo": 14.0,
    "form5": 8.0,           # forma reciente (corto plazo)
    "form10": 6.0,          # forma reciente (medio plazo)
    "injuries": 8.0,
    "fatigue": 6.0,
    "home_perf": 8.0,
    "away_perf": 8.0,
    "h2h": 6.0,
    "odds_movement": 6.0,
}

# Peso aproximado de una lesión según rol (no tenemos posición real en demo;
# se usa un peso medio). Sirve para "lesiones ponderadas".
INJURY_WEIGHT = 1.0


# --- utilidades -------------------------------------------------------------
def _logistic(x: float, k: float) -> float:
    """Logística centrada en 0; k controla la pendiente. Devuelve (0,1)."""
    try:
        return 1.0 / (1.0 + math.exp(-x * k))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _dir(home_support: float, selection: str) -> float | None:
    """Mapea un soporte direccional [0,1] (a favor del local) a la selección."""
    if selection == "HOME":
        return home_support
    if selection == "AWAY":
        return 1.0 - home_support
    if selection == "DRAW":
        # El empate es más probable cuanto más parejo es el partido.
        return 1.0 - 2.0 * abs(home_support - 0.5)
    return None


def _att(att_support: float, selection: str) -> float | None:
    """Mapea un soporte 'ofensivo' [0,1] a selecciones de goles."""
    if selection in ("OVER", "YES"):
        return att_support
    if selection in ("UNDER", "NO"):
        return 1.0 - att_support
    return None


# --- contenedores -----------------------------------------------------------
@dataclass
class TeamFactors:
    team_id: int
    xg_for: float
    xg_against: float
    form5: float
    form10: float
    home_pts: float
    away_pts: float
    last_played: datetime | None
    injuries: float = 0.0


@dataclass
class ConfidenceResult:
    score: float
    tier: str
    breakdown: dict[str, float] = field(default_factory=dict)


def classify(score: float) -> str:
    if score >= 90:
        return "Elite Pick"
    if score >= 85:
        return "Strong Pick"
    if score >= 80:
        return "Value Pick"
    return "No Bet"


# ---------------------------------------------------------------------------
class ConfidenceModel:
    """Precalcula todos los agregados y puntúa cada (fixture, market, selection)."""

    def __init__(self) -> None:
        self.elo = compute_elo()
        self.team_factors = self._load_team_factors()
        self.league = self._league_baselines()
        self.league_multipliers = self._load_league_multipliers()

    @staticmethod
    def _load_league_multipliers() -> dict[int, float]:
        """Multiplicador de confianza por liga (League Analyzer). 1.0 si falta."""
        df = query_df("SELECT league_id, confidence_multiplier FROM league_ratings")
        return {int(r.league_id): float(r.confidence_multiplier)
                for r in df.itertuples()} if not df.empty else {}

    # --- carga de datos ----------------------------------------------------
    def _load_played(self) -> pd.DataFrame:
        return query_df(
            "SELECT f.id, f.match_date, f.home_team_id, f.away_team_id, "
            "       f.home_goals, f.away_goals, "
            "       sh.xg AS home_xg, sa.xg AS away_xg "
            "FROM fixtures f "
            "LEFT JOIN match_stats sh ON sh.fixture_id=f.id AND sh.team_id=f.home_team_id "
            "LEFT JOIN match_stats sa ON sa.fixture_id=f.id AND sa.team_id=f.away_team_id "
            "WHERE f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL "
            "ORDER BY f.match_date"
        )

    def _load_team_factors(self) -> dict[int, TeamFactors]:
        df = self._load_played()
        if df.empty:
            return {}
        df["match_date"] = pd.to_datetime(df["match_date"])
        df["home_xg"] = df["home_xg"].fillna(df["home_goals"])
        df["away_xg"] = df["away_xg"].fillna(df["away_goals"])

        injuries = query_df(
            "SELECT team_id, COUNT(*) AS n FROM injuries GROUP BY team_id"
        )
        inj_map = {int(r.team_id): float(r.n) for r in injuries.itertuples()}

        team_ids = pd.unique(df[["home_team_id", "away_team_id"]].values.ravel())
        factors: dict[int, TeamFactors] = {}
        for tid in team_ids:
            tid = int(tid)
            home = df[df["home_team_id"] == tid]
            away = df[df["away_team_id"] == tid]

            xg_for = (home["home_xg"].sum() + away["away_xg"].sum())
            xg_against = (home["away_xg"].sum() + away["home_xg"].sum())
            n = len(home) + len(away)

            factors[tid] = TeamFactors(
                team_id=tid,
                xg_for=xg_for / n if n else 1.3,
                xg_against=xg_against / n if n else 1.3,
                form5=self._form(df, tid, 5),
                form10=self._form(df, tid, 10),
                home_pts=self._side_points(home, "home"),
                away_pts=self._side_points(away, "away"),
                last_played=df[(df["home_team_id"] == tid) | (df["away_team_id"] == tid)]
                ["match_date"].max(),
                injuries=inj_map.get(tid, 0.0) * INJURY_WEIGHT,
            )
        return factors

    @staticmethod
    def _form(df: pd.DataFrame, tid: int, last: int) -> float:
        mask = (df["home_team_id"] == tid) | (df["away_team_id"] == tid)
        recent = df[mask].sort_values("match_date").tail(last)
        if recent.empty:
            return 0.5
        pts = 0
        for _, r in recent.iterrows():
            is_home = r["home_team_id"] == tid
            gf = r["home_goals"] if is_home else r["away_goals"]
            ga = r["away_goals"] if is_home else r["home_goals"]
            pts += 3 if gf > ga else (1 if gf == ga else 0)
        return pts / (3 * len(recent))

    @staticmethod
    def _side_points(side_df: pd.DataFrame, side: str) -> float:
        """Puntos por partido [0,1] jugando como local o visitante."""
        if side_df.empty:
            return 0.5
        pts = 0
        for _, r in side_df.iterrows():
            if side == "home":
                gf, ga = r["home_goals"], r["away_goals"]
            else:
                gf, ga = r["away_goals"], r["home_goals"]
            pts += 3 if gf > ga else (1 if gf == ga else 0)
        return pts / (3 * len(side_df))

    def _league_baselines(self) -> dict[str, float]:
        if not self.team_factors:
            return {"xg_for": 1.3, "total_xg": 2.6}
        xgs = [tf.xg_for for tf in self.team_factors.values()]
        avg = sum(xgs) / len(xgs)
        return {"xg_for": avg, "total_xg": 2 * avg}

    # --- H2H y movimiento de cuotas (por partido) --------------------------
    def _h2h(self, home_id: int, away_id: int) -> dict[str, float] | None:
        df = query_df(
            "SELECT home_team_id, away_team_id, home_goals, away_goals "
            "FROM fixtures "
            "WHERE home_goals IS NOT NULL AND ("
            "  (home_team_id=? AND away_team_id=?) OR "
            "  (home_team_id=? AND away_team_id=?))",
            [home_id, away_id, away_id, home_id],
        )
        if df.empty:
            return None
        a_pts = over = btts = 0
        for _, r in df.iterrows():
            a_is_home = r["home_team_id"] == home_id
            gf = r["home_goals"] if a_is_home else r["away_goals"]
            ga = r["away_goals"] if a_is_home else r["home_goals"]
            a_pts += 3 if gf > ga else (1 if gf == ga else 0)
            total = r["home_goals"] + r["away_goals"]
            over += 1 if total > 2.5 else 0
            btts += 1 if (r["home_goals"] > 0 and r["away_goals"] > 0) else 0
        n = len(df)
        return {
            "home_support": a_pts / (3 * n),
            "over_rate": over / n,
            "btts_rate": btts / n,
        }

    def _odds_movement(self, fixture_id: int, market: str, selection: str) -> float:
        """
        Soporte por movimiento de cuota: si la cuota se ha *acortado* desde la
        apertura (entró dinero) el factor sube por encima de 0.5.
        """
        df = query_df(
            "SELECT captured_at, AVG(odd) AS odd FROM odds "
            "WHERE fixture_id=? AND market=? AND selection=? "
            "GROUP BY captured_at ORDER BY captured_at",
            [fixture_id, market, selection],
        )
        if len(df) < 2:
            return 0.5  # sin histórico de movimiento -> neutral
        opening = float(df["odd"].iloc[0])
        current = float(df["odd"].iloc[-1])
        if opening <= 0:
            return 0.5
        rel_move = (opening - current) / opening   # >0 si se acortó
        return _logistic(rel_move, 60.0)

    # --- factores individuales --------------------------------------------
    def _factor_poisson(self, model_prob, implied_prob, selection, market):
        """Convicción del modelo de Poisson: edge de probabilidad vs mercado."""
        if model_prob is None:
            return None
        if implied_prob is None or implied_prob <= 0:
            return _logistic(model_prob - 0.5, 4.0)
        # Cuanto más supera la prob. del modelo a la implícita, mayor el soporte.
        return _logistic(model_prob - implied_prob, 12.0)

    def _factor_xg(self, hf, af, selection, market):
        if market == "1X2":
            net_h = hf.xg_for - hf.xg_against
            net_a = af.xg_for - af.xg_against
            return _dir(_logistic(net_h - net_a, 1.2), selection)
        if market.startswith("OU_"):
            total = hf.xg_for + af.xg_for
            return _att(_logistic(total - self.league["total_xg"], 1.4), selection)
        if market == "BTTS":
            both = min(hf.xg_for, af.xg_for)
            return _att(_logistic(both - 0.95, 2.2), selection)
        return None

    def _factor_elo(self, home_id, away_id, selection, market):
        if market != "1X2":
            return None
        rh = self.elo.get(home_id, BASE_ELO)
        ra = self.elo.get(away_id, BASE_ELO)
        return _dir(_logistic((rh - ra) / 100.0, 1.0), selection)

    def _factor_form(self, hf, af, attr, selection, market):
        h, a = getattr(hf, attr), getattr(af, attr)
        if market == "1X2":
            return _dir(_logistic(h - a, 4.0), selection)
        # Para goles: equipos en forma suelen ser más fiables ofensivamente.
        return _att(_logistic((h + a) / 2.0 - 0.5, 3.0), selection)

    def _factor_injuries(self, hf, af, selection, market):
        if market != "1X2":
            return None
        # Más lesiones del rival favorece a tu equipo.
        diff = af.injuries - hf.injuries
        return _dir(_logistic(diff, 0.8), selection)

    def _factor_fatigue(self, hf, af, fixture_date, selection, market):
        if market != "1X2" or hf.last_played is None or af.last_played is None:
            return None
        rest_h = (fixture_date - hf.last_played).days
        rest_a = (fixture_date - af.last_played).days
        return _dir(_logistic(rest_h - rest_a, 0.4), selection)

    def _factor_home_perf(self, hf, selection, market):
        if market != "1X2":
            return None
        # Rendimiento como local: apoya HOME, penaliza AWAY.
        s = _logistic(hf.home_pts - 0.5, 5.0)
        return _dir(s, selection)

    def _factor_away_perf(self, af, selection, market):
        if market != "1X2":
            return None
        # Rendimiento como visitante: apoya AWAY -> soporte 'local' = 1 - perf.
        s = _logistic(af.away_pts - 0.5, 5.0)
        return _dir(1.0 - s, selection)

    def _factor_h2h(self, home_id, away_id, selection, market):
        h2h = self._h2h(home_id, away_id)
        if h2h is None:
            return None
        if market == "1X2":
            return _dir(h2h["home_support"], selection)
        if market.startswith("OU_"):
            return _att(h2h["over_rate"], selection)
        if market == "BTTS":
            return _att(h2h["btts_rate"], selection)
        return None

    # --- score final -------------------------------------------------------
    def score(self, fixture_id: int, home_id: int, away_id: int,
              match_date: str, market: str, selection: str,
              model_prob: float | None = None, implied_prob: float | None = None,
              league_id: int | None = None) -> ConfidenceResult:
        hf = self.team_factors.get(home_id)
        af = self.team_factors.get(away_id)
        if hf is None or af is None:
            return ConfidenceResult(0.0, "No Bet", {})

        fixture_date = pd.to_datetime(match_date)

        values: dict[str, float | None] = {
            "poisson": self._factor_poisson(model_prob, implied_prob, selection, market),
            "xg": self._factor_xg(hf, af, selection, market),
            "elo": self._factor_elo(home_id, away_id, selection, market),
            "form5": self._factor_form(hf, af, "form5", selection, market),
            "form10": self._factor_form(hf, af, "form10", selection, market),
            "injuries": self._factor_injuries(hf, af, selection, market),
            "fatigue": self._factor_fatigue(hf, af, fixture_date, selection, market),
            "home_perf": self._factor_home_perf(hf, selection, market),
            "away_perf": self._factor_away_perf(af, selection, market),
            "h2h": self._factor_h2h(home_id, away_id, selection, market),
            "odds_movement": _att_or_dir_oddsmove(
                self._odds_movement(fixture_id, market, selection)
            ),
        }

        weighted = 0.0
        total_w = 0.0
        breakdown: dict[str, float] = {}
        for name, v in values.items():
            if v is None:
                continue
            w = FACTOR_WEIGHTS[name]
            weighted += w * v
            total_w += w
            breakdown[name] = round(v * 100, 1)

        score = (weighted / total_w * 100.0) if total_w else 0.0

        # Ajuste por desempeño histórico de la liga (League Analyzer).
        mult = self.league_multipliers.get(league_id, 1.0) if league_id else 1.0
        if mult != 1.0:
            score = max(0.0, min(100.0, score * mult))
            breakdown["league_adj"] = round(mult, 3)

        score = round(score, 1)
        return ConfidenceResult(score, classify(score), breakdown)


def _att_or_dir_oddsmove(support: float) -> float:
    """El movimiento de cuota ya viene orientado a la selección (cuota propia)."""
    return support
