"""Symbol helpers for XAU arbitrage."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolMap:
    aster: str = "XAUUSDC"
    backpack: str = "XAU_USDC"


DEFAULT_SYMBOLS = SymbolMap()
