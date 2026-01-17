"""Hedging manager: mirrors Aster fills on Backpack."""
import asyncio
from dataclasses import dataclass
from typing import Dict, Optional

from logger import setup_logger
from .exchanges import ExchangeWrapper
from .feeds import PriceFeed
from .exceptions import HedgeFailed
from .alerts import send_critical_alert

logger = setup_logger("xau.hedge")


@dataclass
class FillEvent:
    symbol: str
    side: str  # "BUY"/"SELL" from Aster
    qty: float
    price: float
    order_id: str


class HedgeManager:
    def __init__(
        self,
        exchange: ExchangeWrapper,
        feed: PriceFeed,
        symbol: str,
        timeout_sec: float,
        poll_interval_sec: float,
        aggressive_slippage: float,
        dry_run: bool = True,
    ) -> None:
        self.exchange = exchange
        self.feed = feed
        self.symbol = symbol
        self.timeout_sec = timeout_sec
        self.poll_interval_sec = poll_interval_sec
        self.aggressive_slippage = aggressive_slippage
        self.dry_run = dry_run
        self._tasks: Dict[str, asyncio.Task] = {}

    def handle_fill(self, fill: FillEvent) -> None:
        # Start hedging task keyed by order_id to avoid duplicates
        key = fill.order_id
        if key in self._tasks:
            return
        task = asyncio.create_task(self._hedge_fill(fill))
        self._tasks[key] = task

    async def _hedge_fill(self, fill: FillEvent) -> None:
        hedge_side = "sell" if fill.side.lower() == "buy" else "buy"
        initial_order_id: Optional[str] = None

        # Determine BBO for hedge
        bbo = self.feed.get_bbo("backpack")
        limit_price = self._calc_hedge_price(hedge_side, bbo, slip=0.0, fallback=fill.price)

        if self.dry_run:
            logger.info(f"[dry-run] hedge {hedge_side} {fill.qty} @ {limit_price:.4f} (from {fill.order_id})")
            return

        order = await self.exchange.create_limit_order(self.symbol, hedge_side, fill.qty, limit_price)
        
        # 🔧 CRITICAL: If hedge fails, stop strategy immediately
        if not order:
            fill_info = {
                'order_id': fill.order_id,
                'side': fill.side,
                'qty': fill.qty,
                'price': fill.price,
                'symbol': fill.symbol,
            }
            error_msg = f"Failed to place hedge order on {self.exchange.name}"
            
            # Send critical alert
            send_critical_alert(
                title="HEDGE FAILED - SINGLE-SIDED EXPOSURE",
                message=f"Aster {fill.side} {fill.qty} @ {fill.price} but Backpack hedge failed",
                details=fill_info
            )
            
            # Raise critical exception to stop strategy
            raise HedgeFailed(fill_info=fill_info, error=error_msg)
        
        initial_order_id = order.order_id
        logger.info(f"hedge order placed {order.order_id} {hedge_side} {fill.qty} @ {limit_price}")

        # Monitor and timeout
        if initial_order_id:
            done = await self._wait_fill(initial_order_id)
            if done:
                logger.info(f"hedge filled order {initial_order_id}")
                return
            # Timeout -> cancel and market/agg limit
            await self.exchange.cancel_orders(self.symbol, [initial_order_id])

        # Aggressive fallback
        fallback_price = self._calc_hedge_price(hedge_side, self.feed.get_bbo("backpack"), slip=self.aggressive_slippage, fallback=fill.price)
        if self.dry_run:
            logger.info(f"[dry-run] fallback hedge {hedge_side} {fill.qty} @ {fallback_price:.4f}")
            return
        
        mkt = await self.exchange.create_market_order(self.symbol, hedge_side, fill.qty)
        if mkt:
            logger.info(f"hedge market order placed {mkt.order_id}")
        else:
            # 🔧 CRITICAL: Market order also failed
            fill_info = {
                'order_id': fill.order_id,
                'side': fill.side,
                'qty': fill.qty,
                'price': fill.price,
                'symbol': fill.symbol,
            }
            error_msg = f"Both limit and market hedge orders failed on {self.exchange.name}"
            
            send_critical_alert(
                title="HEDGE FAILED - MARKET ORDER ALSO FAILED",
                message=f"Aster {fill.side} {fill.qty} @ {fill.price}, all hedge attempts failed",
                details=fill_info
            )
            
            raise HedgeFailed(fill_info=fill_info, error=error_msg)


    async def _wait_fill(self, order_id: str) -> bool:
        elapsed = 0.0
        while elapsed < self.timeout_sec:
            order = await self.exchange.fetch_order(self.symbol, order_id)
            if order and (order.get("status") in ("closed", "filled", "FILLED")):
                return True
            await asyncio.sleep(self.poll_interval_sec)
            elapsed += self.poll_interval_sec
        return False

    def _calc_hedge_price(self, side: str, bbo, slip: float, fallback: float) -> float:
        if not bbo:
            return fallback
        if side == "sell":
            if bbo.bid:
                return bbo.bid * (1 - slip)
        else:
            if bbo.ask:
                return bbo.ask * (1 + slip)
        return fallback
