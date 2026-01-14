"""Strategy orchestration."""
import asyncio
from typing import Dict, Optional

from logger import setup_logger
from .config import StrategyConfig
from .exchanges import ExchangeWrapper
from .feeds import PriceFeed
from .hedge import FillEvent, HedgeManager
from .quotes import QuoteManager
from api.ws import get_user_ws_client

logger = setup_logger("xau.strategy")


class XauArbitrageStrategy:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.feed = PriceFeed(config.aster_symbol, config.backpack_symbol)
        self.aster = ExchangeWrapper(
            "aster",
            {**config.to_client_kwargs(config.aster), "symbol": config.aster_symbol},
        )
        self.backpack = ExchangeWrapper(
            "backpack",
            {**config.to_client_kwargs(config.backpack), "symbol": config.backpack_symbol},
        )
        self.quote_mgr = QuoteManager(
            exchange=self.aster,
            feed=self.feed,
            symbol=config.aster_symbol,
            order_size=config.order_size,
            price_offsets=config.price_offsets,
            quote_interval_sec=config.quote_interval_sec,
            max_open_quotes=config.max_open_quotes,
            dry_run=config.dry_run,
        )
        self.hedge_mgr = HedgeManager(
            exchange=self.backpack,
            feed=self.feed,
            symbol=config.backpack_symbol,
            timeout_sec=config.hedge_timeout_sec,
            poll_interval_sec=config.poll_interval_sec,
            aggressive_slippage=config.aggressive_slippage,
            dry_run=config.dry_run,
        )
        self._tasks = []

    async def start(self) -> None:
        await self.feed.start()
        self._tasks.append(asyncio.create_task(self.quote_mgr.start()))
        if self.config.use_user_stream:
            await self._start_aster_user_stream()
        logger.info("XAU arbitrage strategy started.")

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
        await self.feed.stop()
        await self.quote_mgr.stop()

    async def _start_aster_user_stream(self) -> None:
        ws = get_user_ws_client(
            "aster",
            api_key=self.config.aster.api_key,
            on_event=self._handle_aster_event,
        )
        task = asyncio.create_task(ws.run_forever())
        self._tasks.append(task)

    async def _handle_aster_event(self, event: Dict) -> None:
        if event.get("stream") != "user":
            return
        if event.get("type") != "order":
            return
        status = (event.get("status") or "").upper()
        # Use last_qty as delta fill; fall back to filled_qty if provided
        last_qty = event.get("last_qty")
        filled_qty = event.get("filled_qty")
        qty = float(last_qty or filled_qty or 0)
        if qty <= 0:
            return
        fill = FillEvent(
            symbol=event.get("symbol"),
            side=(event.get("side") or "").upper(),
            qty=qty,
            price=float(event.get("last_price") or event.get("avg_price") or 0),
            order_id=event.get("order_id") or event.get("client_order_id") or "",
        )
        logger.info(f"Aster fill detected {fill.order_id} {fill.side} {fill.qty} @ {fill.price}")
        self.hedge_mgr.handle_fill(fill)
