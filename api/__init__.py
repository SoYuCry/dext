"""API 模塊：與各交易所 API 通訊（ccxt-style 布局）。"""

from importlib import import_module
from typing import Any

__all__ = [
    "Backpack",
    "Aster",
    "Lighter",
    "Hyperliquid",
    "BPClient",
    "get_client",
]


def _load(module: str, attr: str) -> Any:
    """Lazy loader to avoid importing heavy exchange modules at package import time."""
    return getattr(import_module(module), attr)


def get_client(name: str, *args, **kwargs):
    """按名稱返回對應交易所客户端（懶加載其他交易所）。"""
    name = (name or "").lower()
    if name in ("backpack", "bp"):
        return _load("api.backpack", "backpack")(*args, **kwargs)
    if name == "lighter":
        return _load("api.lighter", "lighter")(*args, **kwargs)
    if name == "aster":
        return _load("api.aster", "aster")(*args, **kwargs)
    if name in ("hyperliquid", "hyper"):
        return _load("api.hyperliquid", "hyperliquid")(*args, **kwargs)
    raise ValueError(f"未知交易所: {name}")


def __getattr__(name: str):
    if name == "Backpack":
        return _load("api.backpack", "backpack")
    if name in ("BPClient", "BP"):
        return _load("api.backpack", "backpack")
    if name == "Aster":
        return _load("api.aster", "aster")
    if name == "Lighter":
        return _load("api.lighter", "lighter")
    if name == "Hyperliquid":
        return _load("api.hyperliquid", "hyperliquid")
    # Legacy aliases
    if name == "AsterClient":
        return _load("api.aster", "aster")
    if name == "LighterClient":
        return _load("api.lighter", "lighter")
    if name == "HyperliquidClient":
        return _load("api.hyperliquid", "hyperliquid")
    raise AttributeError(name)
