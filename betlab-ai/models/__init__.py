"""Modelos analíticos de BETLAB AI (Poisson, ratings, value, Kelly, ROI)."""

from .confidence import ConfidenceModel, ConfidenceResult, classify
from .elo import compute_elo, win_probability
from .kelly import StakeRecommendation, kelly_fraction, recommend_stake
from .poisson_model import PoissonModel
from .roi import (
    bankroll_curve,
    log_value_bets,
    roi_metrics,
    settle_bet,
    settle_by_results,
)
from .team_strength import TeamRating, compute_ratings, expected_lambdas
from .value_bet import ValueBet, detect_value_bets, value_bets_dataframe

__all__ = [
    "ConfidenceModel",
    "ConfidenceResult",
    "PoissonModel",
    "StakeRecommendation",
    "TeamRating",
    "ValueBet",
    "bankroll_curve",
    "classify",
    "compute_elo",
    "compute_ratings",
    "win_probability",
    "detect_value_bets",
    "expected_lambdas",
    "kelly_fraction",
    "log_value_bets",
    "recommend_stake",
    "roi_metrics",
    "settle_bet",
    "settle_by_results",
    "value_bets_dataframe",
]
