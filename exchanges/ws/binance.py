"""Binance WS clients (market + user streams)."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from exchanges.base.utils import async_with_timeout
from exchanges.proxy_utils import get_proxy_config
from exchanges.logger import setup_logger
from .base import WebsocketClient

logger = setup_logger("ws.binance")


def _parse_levels(levels: List[List[str]]) -> List[List[float]]:
    parsed: List[List[float]] = []
    for price, qty in levels:
        try:
            p = float(price)
            q = float(qty)
        except (TypeError, ValueError):
            continue
        if q > 0:
            parsed.append([p, q])
    return parsed


def _parse_book_ticker(data: dict) -> Optional[Tuple[float, float, float, float]]:
    bid = data.get("b")
    ask = data.get("a")
    bid_qty = data.get("B")
    ask_qty = data.get("A")
    try:
        bid_price = float(bid)
        ask_price = float(ask)
    except (TypeError, ValueError):
        return None
    try:
        bid_qty_f = float(bid_qty) if bid_qty is not None else 0.0
    except (TypeError, ValueError):
        bid_qty_f = 0.0
    try:
        ask_qty_f = float(ask_qty) if ask_qty is not None else 0.0
    except (TypeError, ValueError):
        ask_qty_f = 0.0
    return bid_price, bid_qty_f, ask_price, ask_qty_f


def _normalize_symbol(raw: str) -> str:
    if not raw:
        return ""
    symbol = raw.replace("/", "").replace("_", "")
    return symbol.upper()


class BinanceWS(WebsocketClient):
    """Binance WS market data client (bookTicker + optional depth).

    By default only subscribes to bookTicker. Set include_depth=True to
    also subscribe to depth snapshots.
    """

    def __init__(
        self,
        symbols: Iterable[str],
        on_event,
        include_depth: bool = False,
        depth_level: int = 5,
        depth_interval_ms: int = 100,
    ) -> None:
        self.symbols = [_normalize_symbol(s) for s in symbols]
        self.include_depth = include_depth
        self.depth_level = depth_level
        self.depth_interval_ms = depth_interval_ms
        self._last_bbo: Dict[str, Tuple[float, float, float, float]] = {}  # symbol → (bid, bid_qty, ask, ask_qty)

        streams = [f"{s.lower()}@bookTicker" for s in self.symbols]
        if self.include_depth:
            streams.extend(
                f"{s.lower()}@depth{depth_level}@{depth_interval_ms}ms" for s in self.symbols
            )
        url = "wss://stream.binance.com:9443/stream?streams=" + "/".join(streams)
        super().__init__(name="binance", stream_url=url, on_event=on_event)

    async def subscribe(self, ws) -> None:
        # Binance combined stream uses URL subscription
        return None

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        msg = self.decode(raw)
        stream = msg.get("stream") or ""
        data = msg.get("data") if "data" in msg else msg
        if not data:
            return

        if stream.endswith("@bookTicker"):
            # Binance bookTicker fields: u, s, b, B, a, A — no E or T
            symbol = data.get("s", "").upper()
            if symbol not in self.symbols:
                return
            parsed = _parse_book_ticker(data)
            if not parsed:
                return
            bid_price, bid_qty, ask_price, ask_qty = parsed
            # Deduplicate: skip if BBO unchanged
            prev = self._last_bbo.get(symbol)
            current = (bid_price, bid_qty, ask_price, ask_qty)
            if prev == current:
                return
            self._last_bbo[symbol] = current
            event = {
                "exchange": "binance",
                "symbol": symbol,
                "stream": "bbo",
                "ts_exchange": None,  # bookTicker has no server timestamp
                "ts_local": ts_local_ms,
                "bids": [[bid_price, bid_qty]],
                "asks": [[ask_price, ask_qty]],
                "raw": data,
            }
            await self.on_event(event)
            return

        if "@depth" in stream:
            # Binance depth has two formats:
            #   - Partial depth snapshot (@depth5/@depth10/@depth20): keys "bids", "asks", "lastUpdateId"
            #   - Diff depth (@depth): keys "b", "a", "E", "s"
            symbol = data.get("s", "").upper()
            if symbol not in self.symbols:
                return
            bids_raw = data.get("b") if "b" in data else data.get("bids", [])
            asks_raw = data.get("a") if "a" in data else data.get("asks", [])
            event = {
                "exchange": "binance",
                "symbol": symbol,
                "stream": "l2",
                "ts_exchange": data.get("E"),  # event time (present in diff; None in partial snapshot)
                "ts_local": ts_local_ms,
                "bids": _parse_levels(bids_raw),
                "asks": _parse_levels(asks_raw),
                "raw": data,
            }
            await self.on_event(event)


class BinanceAggTradeWS(WebsocketClient):
    """Binance aggregated trade stream.

    Pushes individual trades in real-time — essential for order flow analysis.
    Each event contains: price, quantity, side (buyer_is_maker), timestamp.

    Usage:
        ws = BinanceAggTradeWS(['BTCUSDT'], on_event)
        await ws.run_forever()
    """

    def __init__(self, symbols: Iterable[str], on_event) -> None:
        self.symbols = [_normalize_symbol(s) for s in symbols]
        streams = "/".join(f"{s.lower()}@aggTrade" for s in self.symbols)
        url = "wss://stream.binance.com:9443/stream?streams=" + streams
        super().__init__(name="binance_aggtrade", stream_url=url, on_event=on_event)

    async def subscribe(self, ws) -> None:
        return None

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        msg = self.decode(raw)
        data = msg.get("data") or {}
        if not data or data.get("e") != "aggTrade":
            return
        symbol = data.get("s", "")
        if symbol.upper() not in self.symbols:
            return
        event = {
            "exchange": "binance",
            "symbol": symbol.upper(),
            "stream": "aggTrade",
            "ts_exchange": data.get("T"),
            "ts_local": ts_local_ms,
            "agg_trade_id": data.get("a"),
            "price": float(data.get("p", 0)),
            "quantity": float(data.get("q", 0)),
            "first_trade_id": data.get("f"),
            "last_trade_id": data.get("l"),
            "buyer_is_maker": data.get("m", False),
            "raw": data,
        }
        await self.on_event(event)


class BinanceUserWS(WebsocketClient):
    """Binance user data stream (orders + balances)."""

    def __init__(
        self,
        api_key: str,
        on_event,
        *,
        rest_base: str = "https://api.binance.com",
        ws_base: str = "wss://stream.binance.com:9443",
        keepalive_interval: float = 30 * 60,
        proxies: Optional[Dict[str, str]] = None,
        reconnect_delay: float = 3.0,
    ) -> None:
        self.api_key = api_key
        self.rest_base = rest_base.rstrip("/")
        self.ws_base = ws_base.rstrip("/")
        self.keepalive_interval = keepalive_interval
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": api_key})
        proxy_config = proxies if proxies is not None else get_proxy_config()
        if proxy_config:
            self.session.proxies.update(proxy_config)

        self._listen_key: Optional[str] = None
        self._keepalive_task: Optional[asyncio.Task] = None

        super().__init__(name="binance-user", stream_url="", on_event=on_event, reconnect_delay=reconnect_delay)

    def _create_listen_key(self) -> str:
        url = f"{self.rest_base}/api/v3/userDataStream"
        resp = self.session.post(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        listen_key = data.get("listenKey")
        if not listen_key:
            raise RuntimeError("missing listenKey")
        return listen_key

    def _keepalive_listen_key(self, listen_key: str) -> None:
        url = f"{self.rest_base}/api/v3/userDataStream"
        resp = self.session.put(url, params={"listenKey": listen_key}, timeout=10)
        resp.raise_for_status()

    async def get_stream_url(self) -> str:
        self._listen_key = await async_with_timeout(self._create_listen_key, timeout_sec=10)
        return f"{self.ws_base}/ws/{self._listen_key}"

    async def on_connect(self, ws) -> None:
        if not self._listen_key:
            logger.error("[binance-user] no listenKey available, user stream will not receive keepalive")
            return
        self._keepalive_task = asyncio.create_task(self._keepalive_loop(self._listen_key))
        logger.info("[binance-user] connected with listenKey: %s...", self._listen_key[:8])

    async def on_disconnect(self) -> None:
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
        self._keepalive_task = None

    async def _keepalive_loop(self, listen_key: str) -> None:
        while True:
            await asyncio.sleep(self.keepalive_interval)
            try:
                await async_with_timeout(self._keepalive_listen_key, listen_key, timeout_sec=10)
                logger.debug("[binance-user] listenKey keepalive ok")
            except Exception as exc:  # noqa
                logger.warning("[binance-user] listenKey keepalive failed: %s", exc)

    async def subscribe(self, ws) -> None:
        return None

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        msg = self.decode(raw)
        event_type = msg.get("e")
        base_event: Dict[str, Any] = {
            "exchange": "binance",
            "stream": "user",
            "event_type": event_type,
            "ts_exchange": msg.get("E"),  # all user stream events have E (event time)
            "ts_local": ts_local_ms,
            "raw": msg,
        }

        if event_type == "executionReport":
            parsed = {
                "type": "order",
                "symbol": msg.get("s"),
                "order_id": str(msg.get("i")) if msg.get("i") is not None else None,
                "client_order_id": msg.get("c"),
                "side": msg.get("S"),
                "order_type": msg.get("o"),
                "status": msg.get("X"),
                "execution_type": msg.get("x"),
                "time_in_force": msg.get("f"),
                "orig_qty": msg.get("q"),
                "filled_qty": msg.get("z"),
                "last_qty": msg.get("l"),
                "price": msg.get("p"),
                "avg_price": msg.get("ap"),
                "last_price": msg.get("L"),
                "trade_id": msg.get("t"),
                "is_maker": msg.get("m"),
                "fee_asset": msg.get("N"),
                "fee": msg.get("n"),
            }
            base_event.update(parsed)
        elif event_type == "outboundAccountPosition":
            base_event.update({"type": "account", "balances": msg.get("B")})
        elif event_type == "balanceUpdate":
            base_event.update({"type": "balance_update", "asset": msg.get("a"), "delta": msg.get("d")})
        elif event_type == "listStatus":
            base_event.update({"type": "list_status", "order_list_id": msg.get("l")})

        await self.on_event(base_event)
