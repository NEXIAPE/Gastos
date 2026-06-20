"""Modelos analíticos de BETLAB AI."""

from .backtest import BacktestResult, run_backtest
from .bankroll import BankrollState, apply_risk_rules, get_state
from .confidence import ConfidenceModel, ConfidenceResult, classify
from .elo import compute_elo, win_probability
from .kelly import StakeRecommendation, kelly_fraction, recommend_stake
from .league_analyzer import analyze as analyze_leagues
from .nobet import NoBetEngine
from .poisson_model import PoissonModel
from .performance import (
    bankroll_curve,
    ledger,
    metrics as performance_metrics,
    profit_by_league,
    profit_by_market,
)
from .roi import log_value_bets, roi_metrics, settle_bet, settle_by_results
from .strategies import Parlay, StrategyReport, build_strategies
from .team_strength import TeamRating, compute_ratings, expected_lambdas
from .value_bet import ValueBet, detect_value_bets, value_bets_dataframe

__all__ = [
    "BacktestResult",
    "BankrollState",
    "ConfidenceModel",
    "ConfidenceResult",
    "NoBetEngine",
    "Parlay",
    "PoissonModel",
    "StakeRecommendation",
    "StrategyReport",
    "TeamRating",
    "ValueBet",
    "analyze_leagues",
    "apply_risk_rules",
    "backtest",
    "bankroll_curve",
    "build_strategies",
    "classify",
    "compute_elo",
    "compute_ratings",
    "detect_value_bets",
    "expected_lambdas",
    "get_state",
    "kelly_fraction",
    "ledger",
    "log_value_bets",
    "performance_metrics",
    "profit_by_league",
    "profit_by_market",
    "recommend_stake",
    "roi_metrics",
    "run_backtest",
    "settle_bet",
    "settle_by_results",
    "value_bets_dataframe",
    "win_probability",
]
