"""
dext — lightweight unified exchange library for DEX.

Usage:
    import dext

    # List supported exchanges
    print(dext.exchanges)  # ['aster', 'backpack', 'binance', 'lighter', 'variational']

    # Instantiate by name
    exchange = dext.lighter({'privateKey': '...'})
    ticker = exchange.fetch_ticker('ETH/USDC')

    # Or use the factory
    exchange = dext.get_client('lighter', {'privateKey': '...'})
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exchanges.aster import aster as aster
    from exchanges.backpack import backpack as backpack
    from exchanges.binance import binance as binance
    from exchanges.lighter import lighter as lighter
    from exchanges.variational import VariationalClient as variational

from exchanges import exchanges, get_client
from exchanges.base.errors import (
    ExchangeError,
    AuthenticationError,
    NetworkError,
    BadRequest,
    InvalidOrder,
    InsufficientFunds,
    OrderNotFound,
    RateLimitExceeded,
    ExchangeNotAvailable,
    NotSupported,
    ArgumentsRequired,
)

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "exchanges",
    "get_client",
    "aster",
    "backpack",
    "binance",
    "lighter",
    "variational",
    # Error classes
    "ExchangeError",
    "AuthenticationError",
    "NetworkError",
    "BadRequest",
    "InvalidOrder",
    "InsufficientFunds",
    "OrderNotFound",
    "RateLimitExceeded",
    "ExchangeNotAvailable",
    "NotSupported",
    "ArgumentsRequired",
]


def __getattr__(name: str):
    """Allow dext.lighter(...), dext.backpack(...), etc."""
    from exchanges import __getattr__ as _exchanges_getattr
    return _exchanges_getattr(name)

