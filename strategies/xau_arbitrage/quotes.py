"""Quote manager: places/cancels staggered orders on Aster."""
import asyncio
from typing import Dict, List, Optional

from logger import setup_logger
from .exchanges import ExchangeWrapper
from .feeds import PriceFeed

logger = setup_logger("xau.quotes")


class QuoteManager:
    def __init__(
        self,
        exchange: ExchangeWrapper,
        feed: PriceFeed,
        symbol: str,
        order_size: float,
        price_offsets: List[float],
        quote_interval_sec: float,
        max_open_quotes: int,
        dry_run: bool = True,
    ) -> None:
        self.exchange = exchange
        self.feed = feed
        self.symbol = symbol
        self.order_size = order_size
        self.price_offsets = price_offsets
        self.quote_interval_sec = quote_interval_sec
        self.max_open_quotes = max_open_quotes
        self.dry_run = dry_run
        self.active_order_ids: List[str] = []
        self._stop = asyncio.Event()

    async def start(self) -> None:
        while not self._stop.is_set():
            await self._cycle_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.quote_interval_sec)
            except asyncio.TimeoutError:
                continue

    async def stop(self) -> None:
        self._stop.set()
        if self.active_order_ids:
            await self.exchange.cancel_orders(self.symbol, self.active_order_ids)

    async def _cycle_once(self) -> None:
        snap = self.feed.get_bbo("aster")
        if not snap or snap.mid is None:
            logger.warning("quote skipped: no mid price")
            return

        # Cancel previous quotes
        if self.active_order_ids:
            await self.exchange.cancel_orders(self.symbol, self.active_order_ids)
            self.active_order_ids = []

        price = snap.mid
        new_orders: List[str] = []
        for off in self.price_offsets:
            buy_price = price * (1 - off)
            sell_price = price * (1 + off)
            # Enforce guardrail
            if len(new_orders) >= self.max_open_quotes:
                logger.warning("quote skipped: reached max_open_quotes")
                break

            # Place buy
            if not self.dry_run:
                order = await self.exchange.create_limit_order(self.symbol, "buy", self.order_size, buy_price)
                if order:
                    new_orders.append(order.order_id)
            else:
                new_orders.append(f"dry-buy-{off}")
                logger.info(f"[dry-run] buy {self.order_size} @ {buy_price:.4f}")

            # Place sell
            if len(new_orders) >= self.max_open_quotes:
                break
            if not self.dry_run:
                order = await self.exchange.create_limit_order(self.symbol, "sell", self.order_size, sell_price)
                if order:
                    new_orders.append(order.order_id)
            else:
                new_orders.append(f"dry-sell-{off}")
                logger.info(f"[dry-run] sell {self.order_size} @ {sell_price:.4f}")

        self.active_order_ids = new_orders
