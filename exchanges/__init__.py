"""Unified DEX exchange library."""

from importlib import import_module
from typing import Any, Dict, List, Tuple

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

# All supported exchanges
exchanges = ["aster", "backpack", "binance", "lighter", "variational"]

# Canonical exchange → (module, class_attr) mapping
_EXCHANGE_MAP: Dict[str, Tuple[str, str]] = {
    "aster": ("exchanges.aster", "aster"),
    "backpack": ("exchanges.backpack", "backpack"),
    "binance": ("exchanges.binance", "binance"),
    "lighter": ("exchanges.lighter", "lighter"),
    "variational": ("exchanges.variational", "VariationalClient"),
}

# Aliases
_ALIASES: Dict[str, str] = {
    "bp": "backpack",
    "omni": "variational",
}

__all__ = [
    "exchanges",
    "aster",
    "backpack",
    "binance",
    "lighter",
    "variational",
    "get_client",
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


def _load(module: str, attr: str) -> Any:
    """Lazy loader to avoid importing heavy exchange modules at package import time."""
    return getattr(import_module(module), attr)


def _resolve(name: str) -> Tuple[str, str]:
    """Resolve exchange name (with alias support) to (module, attr)."""
    key = (name or "").lower()
    key = _ALIASES.get(key, key)
    if key not in _EXCHANGE_MAP:
        raise ValueError(f"Unknown exchange: {name}. Supported: {', '.join(exchanges)}")
    return _EXCHANGE_MAP[key]


def get_client(name: str, *args, **kwargs):
    """Return an exchange client instance by name (lazy-loaded).

    Usage:
        client = get_client('lighter', {'privateKey': '...'})
        ticker = client.fetch_ticker('ETH/USDC')
    """
    module, attr = _resolve(name)
    return _load(module, attr)(*args, **kwargs)


def __getattr__(name: str):
    """Allow attribute-style access: exchanges.lighter, exchanges.backpack, etc."""
    if name in _EXCHANGE_MAP:
        module, attr = _EXCHANGE_MAP[name]
        return _load(module, attr)
    raise AttributeError(name)
