"""Unified WebSocket dispatcher for normalized events."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List, Optional, Set

from exchanges.logger import setup_logger

from .normalizer import (
    AsterNormalizer,
    BinanceNormalizer,
    BackpackNormalizer,
    LighterNormalizer,
    Normalizer,
    VariationalNormalizer,
)
from .types import BBOUpdate, OrderUpdate

logger = setup_logger("ws.dispatcher")


class WSDispatcher:
    """Route raw WS events into normalized queues."""

    def __init__(
        self,
        market_data_queue_maxsize: int = 1000,
        order_update_queue_maxsize: int = 500,
    ) -> None:
        self.market_data_queue: asyncio.Queue[BBOUpdate] = asyncio.Queue(
            maxsize=market_data_queue_maxsize
        )
        self.order_update_queue: asyncio.Queue[OrderUpdate] = asyncio.Queue(
            maxsize=order_update_queue_maxsize
        )

        self.normalizers: Dict[str, Normalizer] = {}

        self.stats = {
            "market_data_received": 0,
            "market_data_normalized": 0,
            "order_updates_received": 0,
            "order_updates_normalized": 0,
            "normalization_errors": 0,
            "queue_full_drops": 0,
        }

        self.enabled_exchanges: Optional[Set[str]] = None
        self.enabled_symbols: Optional[Set[str]] = None

    def register_normalizer(self, exchange: str, normalizer: Normalizer) -> None:
        self.normalizers[(exchange or "").lower()] = normalizer
        logger.info("registered normalizer for %s", exchange)

    def set_filters(
        self,
        *,
        exchanges: Optional[Iterable[str]] = None,
        symbols: Optional[Iterable[str]] = None,
    ) -> None:
        self.enabled_exchanges = (
            {e.lower() for e in exchanges} if exchanges else None
        )
        self.enabled_symbols = {s.upper() for s in symbols} if symbols else None

    def _should_process(self, exchange: str, symbol: str) -> bool:
        if self.enabled_exchanges and exchange.lower() not in self.enabled_exchanges:
            return False
        if self.enabled_symbols and symbol.upper() not in self.enabled_symbols:
            return False
        return True

    async def on_raw_event(self, raw_event: Dict[str, Any]) -> None:
        if not isinstance(raw_event, dict):
            return
        exchange = (raw_event.get("exchange") or "").lower()
        if not exchange:
            return
        normalizer = self.normalizers.get(exchange)
        if not normalizer:
            logger.debug("no normalizer registered for %s", exchange)
            return

        stream = (raw_event.get("stream") or "").lower()

        try:
            if stream in ("orderbook", "bbo", "l2", "rfq_quote"):
                self.stats["market_data_received"] += 1
                normalized = normalizer.normalize_bbo(raw_event)
                if normalized and self._should_process(normalized.exchange, normalized.symbol):
                    self.stats["market_data_normalized"] += 1
                    try:
                        self.market_data_queue.put_nowait(normalized)
                    except asyncio.QueueFull:
                        self.stats["queue_full_drops"] += 1
                        logger.warning(
                            "market data queue full, drop %s %s",
                            normalized.exchange,
                            normalized.symbol,
                        )
                return

            if stream in ("account_orders", "user", "fills", "events"):
                self.stats["order_updates_received"] += 1
                normalized = normalizer.normalize_order(raw_event)
                if not normalized:
                    return
                updates: List[OrderUpdate]
                if isinstance(normalized, list):
                    updates = normalized
                else:
                    updates = [normalized]

                for update in updates:
                    if not self._should_process(update.exchange, update.symbol):
                        continue
                    self.stats["order_updates_normalized"] += 1
                    try:
                        self.order_update_queue.put_nowait(update)
                    except asyncio.QueueFull:
                        self.stats["queue_full_drops"] += 1
                        logger.warning(
                            "order update queue full, drop %s %s",
                            update.exchange,
                            update.symbol,
                        )
                return
        except Exception as exc:  # pragma: no cover - defensive
            self.stats["normalization_errors"] += 1
            logger.error("dispatcher error: %s", exc, exc_info=True)

    async def get_market_data(self) -> BBOUpdate:
        return await self.market_data_queue.get()

    async def get_order_update(self) -> OrderUpdate:
        return await self.order_update_queue.get()

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.stats,
            "market_data_queue_size": self.market_data_queue.qsize(),
            "order_update_queue_size": self.order_update_queue.qsize(),
        }

    def log_stats(self) -> None:
        stats = self.get_stats()
        logger.info(
            "dispatcher stats market=%s/%s order=%s/%s errors=%s drops=%s queues=(%s,%s)",
            stats["market_data_normalized"],
            stats["market_data_received"],
            stats["order_updates_normalized"],
            stats["order_updates_received"],
            stats["normalization_errors"],
            stats["queue_full_drops"],
            stats["market_data_queue_size"],
            stats["order_update_queue_size"],
        )


def create_dispatcher(
    *,
    lighter_market_mapping: Optional[Dict[int, str]] = None,
) -> WSDispatcher:
    dispatcher = WSDispatcher()
    dispatcher.register_normalizer(
        "lighter", LighterNormalizer(lighter_market_mapping or {})
    )
    dispatcher.register_normalizer("backpack", BackpackNormalizer())
    dispatcher.register_normalizer("binance", BinanceNormalizer())
    dispatcher.register_normalizer("variational", VariationalNormalizer())
    dispatcher.register_normalizer("aster", AsterNormalizer())
    return dispatcher
