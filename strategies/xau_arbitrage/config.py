"""Strategy configuration for XAU arbitrage."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ExchangeKeys:
    api_key: str
    secret: Optional[str] = None
    passphrase: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class StrategyConfig:
    # Exchange credentials
    aster: ExchangeKeys
    backpack: ExchangeKeys

    # Trading symbols
    aster_symbol: str = "XAUUSDT"
    backpack_symbol: str = "PAXG_USDC_PERP"

    # Quoting (multi-tier orders to catch big fingers)
    order_sizes: List[float] = field(default_factory=lambda: [30.0, 30.0, 40.0])  # USD sizes: 30u, 30u, 40u
    price_offsets: List[float] = field(default_factory=lambda: [0.0015, 0.0025, 0.004])  # 0.15%/0.25%/0.40%
    quote_interval_sec: float = 10.0

    # Hedging
    hedge_timeout_sec: float = 30.0
    poll_interval_sec: float = 1.0
    aggressive_slippage: float = 0.0005  # extra 0.05% to force fill when timing out

    # Safety
    dry_run: bool = True
    max_open_quotes: int = 50  # guardrail to avoid runaway orders

    # Optional overrides
    use_user_stream: bool = True  # use Aster user stream to detect fills

    def to_client_kwargs(self, keys: ExchangeKeys) -> Dict[str, str]:
        payload = {
            "apiKey": keys.api_key,
        }
        if keys.secret:
            payload["secret"] = keys.secret
        if keys.passphrase:
            payload["password"] = keys.passphrase
        payload.update(keys.extra)
        return payload
