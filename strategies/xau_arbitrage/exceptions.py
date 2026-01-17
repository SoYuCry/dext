"""XAU arbitrage strategy-specific exceptions.

This module extends the base exception system with XAU-specific exceptions.
"""

from strategies.base_exceptions import (
    # Re-export base exceptions for convenience
    Severity,
    StrategyException,
    CriticalException,
    WarningException,
    InfoException,
    # Re-export common exceptions
    HedgeFailed,
    InsufficientMarginCritical,
    InsufficientMarginWarning,
    PositionImbalance,
    ExchangeConnectionLost,
    OrderFailed,
    HighFailureRate,
    PriceFeedStale,
    OrderPartiallyFilled,
    StrategyPaused,
    StrategyResumed,
)

# All base exceptions are available
# Add XAU-specific exceptions below if needed

__all__ = [
    # Severity
    "Severity",
    # Base classes
    "StrategyException",
    "CriticalException",
    "WarningException",
    "InfoException",
    # Critical exceptions
    "HedgeFailed",
    "InsufficientMarginCritical",
    "PositionImbalance",
    "ExchangeConnectionLost",
    # Warning exceptions
    "OrderFailed",
    "InsufficientMarginWarning",
    "HighFailureRate",
    "PriceFeedStale",
    # Info exceptions
    "OrderPartiallyFilled",
    "StrategyPaused",
    "StrategyResumed",
]

