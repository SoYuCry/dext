"""Price feed aggregator using existing WS clients."""
import asyncio
from dataclasses import dataclass
from typing import Dict, Optional

from api.ws import get_ws_client
from logger import setup_logger

logger = setup_logger("xau.feeds")


@dataclass
class PriceSnapshot:
    exchange: str
    symbol: str
    bid: Optional[float]
    ask: Optional[float]
    ts_exchange: Optional[int]
    ts_local: int

    @property
    def mid(self) -> Optional[float]:
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return None


class PriceFeed:
    """Maintains latest BBO for Aster & Backpack."""

    def __init__(self, aster_symbol: str, backpack_symbol: str) -> None:
        self.aster_symbol = aster_symbol
        self.backpack_symbol = backpack_symbol
        self.snapshots: Dict[str, PriceSnapshot] = {}
        self._tasks = []

    async def start(self) -> None:
        # Aster depth (l2) gives bids/asks
        aster_ws = get_ws_client("aster", [self.aster_symbol], self._on_event)
        bp_ws = get_ws_client("backpack", [self.backpack_symbol], self._on_event, include_depth=True)
        self._tasks = [
            asyncio.create_task(aster_ws.run_forever()),
            asyncio.create_task(bp_ws.run_forever()),
        ]
        # Warn if snapshot not received shortly after start
        await asyncio.sleep(3)
        if "aster" not in self.snapshots:
            logger.warning(f"No Aster depth snapshot yet for symbol={self.aster_symbol} (check symbol correctness or WS health)")
        if "backpack" not in self.snapshots:
            logger.warning(f"No Backpack depth snapshot yet for symbol={self.backpack_symbol} (check symbol correctness or WS health)")

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._tasks = []

    async def _on_event(self, event: Dict) -> None:
        bids = event.get("bids") or []
        asks = event.get("asks") or []
        bid = bids[0][0] if bids else None
        ask = asks[0][0] if asks else None
        snap = PriceSnapshot(
            exchange=event.get("exchange"),
            symbol=event.get("symbol"),
            bid=bid,
            ask=ask,
            ts_exchange=event.get("ts_exchange"),
            ts_local=event.get("ts_local"),
        )
        self.snapshots[snap.exchange] = snap

    def get_bbo(self, exchange: str) -> Optional[PriceSnapshot]:
        return self.snapshots.get(exchange)
