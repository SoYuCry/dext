"""Exchange implementations following ccxt-style layout."""

from importlib import import_module

__all__ = ["Backpack", "Aster", "Lighter", "Hyperliquid"]


def __getattr__(name: str):
    if name == "Backpack":
        return getattr(import_module("api.backpack"), "Backpack")
    if name == "Aster":
        return getattr(import_module("api.aster"), "Aster")
    if name == "Lighter":
        return getattr(import_module("api.lighter"), "Lighter")
    if name == "Hyperliquid":
        return getattr(import_module("api.hyperliquid"), "Hyperliquid")
    raise AttributeError(name)
