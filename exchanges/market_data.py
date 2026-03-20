"""Market data cache with background WS/poller synchronization."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

from exchanges.ws import get_ws_client
from exchanges.logger import setup_logger

logger = setup_logger("market_data")


@dataclass
class PriceSnapshot:
    exchange: str
    bid: Optional[float]
    ask: Optional[float]
    ts_exchange: Optional[int]
    ts_local: int
    symbol: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def mid(self) -> Optional[float]:
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return None


@dataclass
class PositionSnapshot:
    """Local position snapshot maintained from WebSocket updates."""
    exchange: str
    symbol: Optional[str]
    position: float  # Current position (positive=long, negative=short)
    ts_local: int    # Last update timestamp (milliseconds)
    source: str      # "ws" or "api" (data source)


@dataclass
class _VariationalQuoteState:
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_quote_id: Optional[str] = None
    ask_quote_id: Optional[str] = None
    last_quote_id: Optional[str] = None
    ts_local: int = 0


class MarketDataManager:
    """Maintain latest market data snapshots from WS/pollers.

    The cache is updated by background tasks; reads are synchronous.
    """

    def __init__(self, *, stale_ms: int = 1500) -> None:
        self.stale_ms = stale_ms
        self._snapshots: Dict[str, PriceSnapshot] = {}
        self._positions: Dict[str, PositionSnapshot] = {}
        self._sources: List[Any] = []
        self._tasks: List[asyncio.Task] = []
        self._listeners: List[Callable[[Dict[str, Any]], Awaitable[None]]] = []
        self._listener_tasks: set[asyncio.Task] = set()
        self._variational_state: Dict[str, _VariationalQuoteState] = {}
        self._last_event_ts: int = 0
        self._event_count: int = 0

    def add_listener(self, handler: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Register a non-blocking event listener (fire-and-forget)."""
        self._listeners.append(handler)

    def add_ws_source(
        self,
        name: str,
        symbols: Iterable[str],
        *,
        source_key: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        async def _handler(event: Dict[str, Any]) -> None:
            await self._on_event(event, source_key=source_key, source_exchange=name)

        ws = get_ws_client(name, symbols, _handler, **kwargs)
        self._sources.append(ws)
        return ws

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def start(self) -> None:
        self._tasks = [asyncio.create_task(src.run_forever()) for src in self._sources]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = []
        for src in self._sources:
            stop = getattr(src, "stop", None)
            if callable(stop):
                try:
                    await stop()
                except Exception:
                    pass
        self._sources = []
        for task in list(self._listener_tasks):
            task.cancel()
        self._listener_tasks.clear()

    def get_snapshot(
        self,
        *,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        market_index: Optional[int] = None,
        key: Optional[str] = None,
    ) -> Optional[PriceSnapshot]:
        lookup_key = key or self._make_key(exchange, symbol=symbol, market_index=market_index)
        return self._snapshots.get(lookup_key)

    def get_snapshot_with_status(
        self,
        *,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        market_index: Optional[int] = None,
        key: Optional[str] = None,
        stale_ms: Optional[int] = None,
    ) -> tuple[Optional[PriceSnapshot], bool, int]:
        snap = self.get_snapshot(exchange=exchange, symbol=symbol, market_index=market_index, key=key)
        if not snap:
            return None, False, 0
        now_ms = int(time.time() * 1000)
        latency = max(0, now_ms - int(snap.ts_local or 0))
        threshold = stale_ms if stale_ms is not None else self.stale_ms
        is_fresh = latency <= threshold
        return snap, is_fresh, latency

    def get_ticker(
        self,
        *,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        market_index: Optional[int] = None,
        key: Optional[str] = None,
        stale_ms: Optional[int] = None,
    ) -> Optional[Dict[str, Optional[float]]]:
        snap, fresh, _ = self.get_snapshot_with_status(
            exchange=exchange, symbol=symbol, market_index=market_index, key=key, stale_ms=stale_ms
        )
        if not snap or not fresh:
            return None
        return {"bid": snap.bid, "ask": snap.ask}

    def get_orderbook(
        self,
        *,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        market_index: Optional[int] = None,
        key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        snap = self.get_snapshot(exchange=exchange, symbol=symbol, market_index=market_index, key=key)
        if not snap:
            return None
        bids = snap.meta.get("bids")
        asks = snap.meta.get("asks")
        if bids is None or asks is None:
            return None
        return {"bids": bids, "asks": asks, "timestamp": snap.ts_exchange, "ts_local": snap.ts_local}

    def get_quote_id(
        self,
        *,
        exchange: str,
        symbol: Optional[str] = None,
        market_index: Optional[int] = None,
        side: Optional[str] = None,
        key: Optional[str] = None,
    ) -> Optional[str]:
        snap = self.get_snapshot(exchange=exchange, symbol=symbol, market_index=market_index, key=key)
        if not snap:
            return None
        quote_id = snap.meta.get("quote_id")
        if quote_id is not None:
            return quote_id
        if not side:
            return None
        side = side.lower()
        if side == "buy":
            return snap.meta.get("ask_quote_id")
        if side == "sell":
            return snap.meta.get("bid_quote_id")
        return None

    def set_snapshot(self, key: str, snapshot: PriceSnapshot) -> None:
        """Manually set a snapshot (useful for externally sourced events)."""
        self._snapshots[key] = snapshot

    def get_health(self, *, stale_ms: Optional[int] = None) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        threshold = stale_ms if stale_ms is not None else self.stale_ms
        stale_keys = [
            key
            for key, snap in self._snapshots.items()
            if snap.ts_local and now_ms - int(snap.ts_local) > threshold
        ]
        last_update_ms = 0
        if self._snapshots:
            last_update_ms = max(int(snap.ts_local or 0) for snap in self._snapshots.values())
        return {
            "source_count": len(self._sources),
            "snapshot_count": len(self._snapshots),
            "stale_count": len(stale_keys),
            "stale_keys": stale_keys,
            "last_update_ms": last_update_ms,
            "last_event_ts": self._last_event_ts,
            "event_count": self._event_count,
        }

    def export_metrics(self, *, stale_ms: Optional[int] = None) -> Dict[str, Any]:
        health = self.get_health(stale_ms=stale_ms)
        return {
            "market_data_sources": health["source_count"],
            "market_data_snapshots": health["snapshot_count"],
            "market_data_stale": health["stale_count"],
            "market_data_last_update_ms": health["last_update_ms"],
            "market_data_last_event_ts": health["last_event_ts"],
            "market_data_event_count": health["event_count"],
        }

    def _make_key(
        self, exchange: Optional[str], *, symbol: Optional[str], market_index: Optional[int]
    ) -> str:
        exchange = exchange or "unknown"
        if symbol:
            return f"{exchange}:{symbol}"
        if market_index is not None:
            return f"{exchange}:market_index={market_index}"
        return exchange

    def _event_key(self, event: Dict[str, Any], source_exchange: Optional[str]) -> str:
        exchange = event.get("exchange") or source_exchange or "unknown"
        symbol = event.get("symbol")
        if not symbol:
            instrument = event.get("instrument")
            if isinstance(instrument, dict):
                symbol = instrument.get("underlying") or instrument.get("symbol")
        if symbol:
            return f"{exchange}:{symbol}"
        market_index = event.get("market_index")
        if market_index is not None:
            return f"{exchange}:market_index={market_index}"
        return exchange

    async def _on_event(
        self,
        event: Dict[str, Any],
        *,
        source_key: Optional[str],
        source_exchange: Optional[str],
    ) -> None:
        if not isinstance(event, dict):
            return
        self._event_count += 1
        self._last_event_ts = int(time.time() * 1000)
        if event.get("stream") == "account_orders":
            self._update_position_from_orders(event, source_key, source_exchange)
            self._emit_event(event)
            return
        exchange = event.get("exchange") or source_exchange or "unknown"
        key = source_key or self._event_key(event, source_exchange)

        if exchange == "variational":
            self._handle_variational_event(event, key)
        else:
            self._handle_orderbook_event(event, key, exchange)

        self._emit_event(event)

    def _handle_orderbook_event(self, event: Dict[str, Any], key: str, exchange: str) -> None:
        bids = event.get("bids") or []
        asks = event.get("asks") or []
        bid = self._coerce_float(event.get("best_bid"))
        ask = self._coerce_float(event.get("best_ask"))
        if bid is None and bids:
            try:
                bid = self._coerce_float(bids[0][0])
            except Exception:
                bid = None
        if ask is None and asks:
            try:
                ask = self._coerce_float(asks[0][0])
            except Exception:
                ask = None
        ts_local = int(event.get("ts_local") or time.time() * 1000)
        snap = PriceSnapshot(
            exchange=exchange,
            symbol=event.get("symbol"),
            bid=bid,
            ask=ask,
            ts_exchange=event.get("ts_exchange"),
            ts_local=ts_local,
            meta={"bids": bids, "asks": asks},
        )
        self._snapshots[key] = snap

    def _handle_variational_event(self, event: Dict[str, Any], key: str) -> None:
        state = self._variational_state.get(key)
        if state is None:
            state = _VariationalQuoteState()
            self._variational_state[key] = state

        bid = self._coerce_float(event.get("bid"))
        ask = self._coerce_float(event.get("ask"))
        if bid is None or ask is None:
            return
        state.bid = bid
        state.ask = ask
        quote_id = event.get("quote_id")
        if quote_id is not None:
            state.bid_quote_id = str(quote_id)
            state.ask_quote_id = str(quote_id)
            state.last_quote_id = str(quote_id)

        state.ts_local = int(event.get("ts_local") or time.time() * 1000)
        instrument = event.get("instrument")
        symbol = None
        if isinstance(instrument, dict):
            symbol = instrument.get("underlying") or instrument.get("symbol")
        snap = PriceSnapshot(
            exchange="variational",
            symbol=symbol,
            bid=state.bid,
            ask=state.ask,
            ts_exchange=None,
            ts_local=state.ts_local,
            meta={
                "quote_id": state.last_quote_id,
                "bid_quote_id": state.bid_quote_id,
                "ask_quote_id": state.ask_quote_id,
                "last_quote_id": state.last_quote_id,
            },
        )
        self._snapshots[key] = snap

    def _update_position_from_orders(
        self,
        event: Dict[str, Any],
        source_key: Optional[str],
        source_exchange: Optional[str],
    ) -> None:
        """Update local position cache from account_orders stream."""
        exchange = event.get("exchange") or source_exchange or "lighter"
        market_index = event.get("market_index")
        symbol = event.get("symbol")

        # Construct position cache key (same format as price snapshots)
        pos_key = source_key or self._make_key(exchange, symbol=symbol, market_index=market_index)

        # Get or create position snapshot
        if pos_key not in self._positions:
            self._positions[pos_key] = PositionSnapshot(
                exchange=exchange,
                symbol=symbol,
                position=0.0,
                ts_local=int(time.time() * 1000),
                source="ws",
            )

        pos_snap = self._positions[pos_key]
        orders = event.get("orders") or []

        # Dedup: track processed order IDs to prevent double-counting
        if not hasattr(pos_snap, "_processed_order_ids"):
            pos_snap._processed_order_ids = set()

        for order in orders:
            if not isinstance(order, dict):
                continue

            status = (order.get("status") or "").lower()
            # Only process fully filled orders
            if status != "filled":
                continue

            # Deduplicate by order ID
            order_id = order.get("order_id") or order.get("id")
            if order_id is not None:
                if order_id in pos_snap._processed_order_ids:
                    logger.debug("Skipping duplicate order %s for %s", order_id, pos_key)
                    continue
                pos_snap._processed_order_ids.add(order_id)

            # Get fill information
            filled_base = order.get("filled_base_amount")
            is_ask = order.get("is_ask", False)

            if filled_base is None:
                continue

            try:
                filled_qty = float(filled_base)
            except (TypeError, ValueError):
                continue

            # Calculate position change: buy increases position, sell decreases
            delta = -filled_qty if is_ask else filled_qty
            pos_snap.position += delta
            pos_snap.ts_local = int(time.time() * 1000)
            pos_snap.source = "ws"

            logger.debug(
                "Position updated from WS: %s side=%s qty=%.4f new_pos=%.4f",
                pos_key,
                "sell" if is_ask else "buy",
                filled_qty,
                pos_snap.position,
            )

    def get_position(
        self,
        *,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        market_index: Optional[int] = None,
        key: Optional[str] = None,
    ) -> Optional[float]:
        """Get locally cached position (real-time, no API call needed)."""
        lookup_key = key or self._make_key(exchange, symbol=symbol, market_index=market_index)
        pos_snap = self._positions.get(lookup_key)
        return pos_snap.position if pos_snap else None

    def set_position(
        self,
        position: float,
        *,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        market_index: Optional[int] = None,
        key: Optional[str] = None,
        source: str = "api",
    ) -> None:
        """Manually set position (used for API verification sync)."""
        lookup_key = key or self._make_key(exchange, symbol=symbol, market_index=market_index)

        if lookup_key not in self._positions:
            self._positions[lookup_key] = PositionSnapshot(
                exchange=exchange or "unknown",
                symbol=symbol,
                position=position,
                ts_local=int(time.time() * 1000),
                source=source,
            )
        else:
            pos_snap = self._positions[lookup_key]
            pos_snap.position = position
            pos_snap.ts_local = int(time.time() * 1000)
            pos_snap.source = source

    def get_position_snapshot(
        self,
        *,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        market_index: Optional[int] = None,
        key: Optional[str] = None,
    ) -> Optional[PositionSnapshot]:
        """Get full position snapshot (including timestamp and source)."""
        lookup_key = key or self._make_key(exchange, symbol=symbol, market_index=market_index)
        return self._positions.get(lookup_key)

    def _emit_event(self, event: Dict[str, Any]) -> None:
        if not self._listeners:
            return
        loop = asyncio.get_running_loop()
        for handler in self._listeners:
            task = loop.create_task(handler(event))
            self._listener_tasks.add(task)
            task.add_done_callback(self._on_listener_task_done)

    def _on_listener_task_done(self, task: asyncio.Task) -> None:
        self._listener_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("Listener task failed: %s", exc, exc_info=exc)
