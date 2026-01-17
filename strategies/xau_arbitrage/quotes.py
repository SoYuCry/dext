"""Quote manager: places/cancels staggered orders on Aster."""
import asyncio
from typing import Dict, List, Optional

from logger import setup_logger
from .exchanges import ExchangeWrapper
from .feeds import PriceFeed
from .exceptions import QuoteOrderFailed
from .alerts import send_warning_alert

logger = setup_logger("xau.quotes")


class QuoteManager:
    def __init__(
        self,
        exchange: ExchangeWrapper,
        feed: PriceFeed,
        symbol: str,
        order_sizes: List[float],
        price_offsets: List[float],
        quote_interval_sec: float,
        max_open_quotes: int,
        dry_run: bool = True,
    ) -> None:
        self.exchange = exchange
        self.feed = feed
        self.symbol = symbol
        self.order_sizes = order_sizes
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
            logger.warning(f"quote skipped: no mid price for Aster symbol={self.symbol}")
            return

        # Cancel previous quotes
        if self.active_order_ids:
            await self.exchange.cancel_orders(self.symbol, self.active_order_ids)
            self.active_order_ids = []

        price = snap.mid
        new_orders: List[str] = []
        failed_orders = 0  # 🔧 Track failed orders

        # Place orders for each tier (offset + size pair)
        for i, (off, size_usd) in enumerate(zip(self.price_offsets, self.order_sizes)):
            buy_price = price * (1 - off)
            sell_price = price * (1 + off)

            # Convert USD amount to contract amount
            # size_usd is in USD, need to divide by price to get contracts
            buy_contracts = size_usd / buy_price
            sell_contracts = size_usd / sell_price

            # Enforce guardrail
            if len(new_orders) >= self.max_open_quotes:
                logger.warning("quote skipped: reached max_open_quotes")
                break

            # Place buy
            if not self.dry_run:
                order = await self.exchange.create_limit_order(self.symbol, "buy", buy_contracts, buy_price)
                if order:
                    new_orders.append(order.order_id)
                else:
                    failed_orders += 1  # 🔧 Count failure
            else:
                new_orders.append(f"dry-buy-tier{i}")
                logger.info(f"[dry-run] tier{i} buy ${size_usd:.1f} ({buy_contracts:.4f} XAU) @ {buy_price:.2f} (offset -{off*100:.2f}%)")

            # Place sell
            if len(new_orders) >= self.max_open_quotes:
                break
            if not self.dry_run:
                order = await self.exchange.create_limit_order(self.symbol, "sell", sell_contracts, sell_price)
                if order:
                    new_orders.append(order.order_id)
                else:
                    failed_orders += 1  # 🔧 Count failure
            else:
                new_orders.append(f"dry-sell-tier{i}")
                logger.info(f"[dry-run] tier{i} sell ${size_usd:.1f} ({sell_contracts:.4f} XAU) @ {sell_price:.2f} (offset +{off*100:.2f}%)")

        self.active_order_ids = new_orders
        
        # 🔧 Alert if too many failures
        total_expected = len(self.order_sizes) * 2  # buy + sell
        if failed_orders > 0:
            failure_rate = failed_orders / total_expected
            logger.warning(f"Quote cycle completed: {len(new_orders)}/{total_expected} orders placed ({failed_orders} failed)")
            
            if failure_rate >= 0.5:  # 50% or more failed
                send_warning_alert(
                    title="High Quote Failure Rate",
                    message=f"{failed_orders}/{total_expected} quote orders failed (likely insufficient margin)",
                    details={
                        'failed': failed_orders,
                        'total': total_expected,
                        'placed': len(new_orders),
                        'failure_rate': f"{failure_rate*100:.1f}%",
                    }
                )
