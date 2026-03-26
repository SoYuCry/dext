"""Aster WebSocket client collection

Provides five WebSocket clients:
- AsterWS: Incremental update stream (high-frequency trading)
- AsterDepthWS: Full snapshot stream (general use, recommended)
- AsterAggTradeWS: Aggregated trade stream (order flow analysis)
- AsterBookTickerWS: Real-time best bid/ask (BBO, lowest latency)
- AsterUserWS: User data stream (account monitoring)

Usage examples:
    # Market depth snapshot stream (recommended)
    from exchanges.ws.aster import AsterDepthWS
    ws = AsterDepthWS(['xauusdt'], on_event, depth_level=20)
    await ws.run_forever()

    # User data stream
    from exchanges.ws.aster import AsterUserWS
    ws = AsterUserWS(api_key='your_key', on_event=on_event)
    await ws.run_forever()
"""

import asyncio
from typing import Any, Dict, Iterable, List, Optional

import requests

from exchanges.base.utils import async_with_timeout
from exchanges.proxy_utils import get_proxy_config
from exchanges.logger import setup_logger
from .base import WebsocketClient

logger = setup_logger("ws.aster")


# ============================================================
# Public utility functions
# ============================================================

def _parse_levels(levels: Iterable[List[str]]) -> List[List[float]]:
    """Parse price level data

    Args:
        levels: List of price levels in [[price, qty], ...] format

    Returns:
        Parsed list with zero-quantity levels filtered out
    """
    parsed = []
    for price, qty in levels:
        try:
            p = float(price)
            q = float(qty)
        except (TypeError, ValueError):
            continue
        if q > 0:
            parsed.append([p, q])
    return parsed


# ============================================================
# Market data stream (public data, no authentication required)
# ============================================================

class AsterWS(WebsocketClient):
    """Aster incremental update stream

    Subscribes to incremental order book updates, suitable for high-frequency trading.

    Features:
    - Real-time push (latency < 10ms)
    - Only pushes changed price levels
    - Client must maintain full order book state

    WebSocket URL:
        wss://fstream.asterdex.com/stream?streams={symbol}@depth

    Usage example:
        ws = AsterWS(['xauusdt', 'btcusdt'], on_event)
        await ws.run_forever()
    """

    def __init__(self, symbols: Iterable[str], on_event) -> None:
        """Initialize the incremental update stream client

        Args:
            symbols: List of trading pairs, e.g. ['xauusdt', 'btcusdt']
            on_event: Event handler callback function
        """
        self.symbols = [s.lower() for s in symbols]
        streams = "/".join(f"{s}@depth" for s in self.symbols)
        url = f"wss://fstream.asterdex.com/stream?streams={streams}"
        super().__init__(name="aster", stream_url=url, on_event=on_event)

    async def subscribe(self, ws) -> None:
        # Aster uses URL-based aggregated streams; no additional subscribe message needed
        return None

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        msg = self.decode(raw)
        data = msg.get("data") or {}
        if not data:
            return
        symbol = data.get("s")
        if symbol and symbol.lower() not in self.symbols:
            return
        event = {
            "exchange": "aster",
            "symbol": symbol,
            "stream": "l2",
            "ts_exchange": data.get("E") or data.get("T"),
            "ts_local": ts_local_ms,
            "bids": _parse_levels(data.get("b", [])),
            "asks": _parse_levels(data.get("a", [])),
            "raw": data,
        }
        await self.on_event(event)


class AsterDepthWS(WebsocketClient):
    """Aster full snapshot stream (recommended)

    Pushes complete order book snapshots every 250ms, suitable for most use cases.

    Features:
    - Fixed-frequency push (250ms)
    - Complete N-level bid/ask data
    - No state maintenance needed, ready to use directly

    WebSocket URL:
        wss://fstream.asterdex.com/stream?streams={symbol}@depth{level}

    Usage example:
        ws = AsterDepthWS(['xauusdt'], on_event, depth_level=20)
        await ws.run_forever()
    """

    def __init__(self, symbols: Iterable[str], on_event, depth_level: int = 20) -> None:
        """Initialize the order book depth WebSocket client

        Args:
            symbols: List of trading pairs, e.g. ["xauusdt"]
            on_event: Event handler callback function
            depth_level: Order book depth levels, supports 5, 10, 20 (default 20)
        """
        self.symbols = [s.lower() for s in symbols]
        self.depth_level = depth_level

        # Build subscription stream URL
        streams = "/".join(f"{s}@depth{depth_level}" for s in self.symbols)
        url = f"wss://fstream.asterdex.com/stream?streams={streams}"
        super().__init__(name=f"aster_depth{depth_level}", stream_url=url, on_event=on_event)

    async def subscribe(self, ws) -> None:
        # Aster uses URL-based aggregated streams; no additional subscribe message needed
        return None

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        msg = self.decode(raw)
        data = msg.get("data") or {}
        if not data:
            return
        symbol = data.get("s")
        if symbol and symbol.lower() not in self.symbols:
            return

        event = {
            "exchange": "aster",
            "symbol": symbol,
            "stream": f"depth{self.depth_level}",
            "ts_exchange": data.get("E") or data.get("T"),
            "ts_local": ts_local_ms,
            "bids": _parse_levels(data.get("b", [])),
            "asks": _parse_levels(data.get("a", [])),
            "raw": data,
        }
        await self.on_event(event)


# ============================================================
# aggTrade stream (real-time trade-by-trade data)
# ============================================================

class AsterAggTradeWS(WebsocketClient):
    """Aster aggregated trade stream.

    Pushes individual trades in real-time — essential for order flow analysis
    and market-making strategies.

    Each event contains: price, quantity, side (buyer_is_maker), timestamp.

    WebSocket URL:
        wss://fstream.asterdex.com/stream?streams={symbol}@aggTrade

    Usage:
        ws = AsterAggTradeWS(['xauusdt'], on_event)
        await ws.run_forever()
    """

    def __init__(self, symbols: Iterable[str], on_event) -> None:
        self.symbols = [s.lower() for s in symbols]
        streams = "/".join(f"{s}@aggTrade" for s in self.symbols)
        url = f"wss://fstream.asterdex.com/stream?streams={streams}"
        super().__init__(name="aster_aggtrade", stream_url=url, on_event=on_event)

    async def subscribe(self, ws) -> None:
        return None

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        msg = self.decode(raw)
        data = msg.get("data") or {}
        if not data or data.get("e") != "aggTrade":
            return
        symbol = data.get("s")
        if symbol and symbol.lower() not in self.symbols:
            return
        event = {
            "exchange": "aster",
            "symbol": symbol,
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


# ============================================================
# bookTicker stream (real-time best bid/ask)
# ============================================================

class AsterBookTickerWS(WebsocketClient):
    """Aster individual symbol book ticker stream.

    Pushes real-time best bid/ask price and quantity updates — faster and
    lighter than depth snapshots for BBO-only strategies.

    WebSocket URL:
        wss://fstream.asterdex.com/stream?streams={symbol}@bookTicker

    Usage:
        ws = AsterBookTickerWS(['xauusdt'], on_event)
        await ws.run_forever()
    """

    def __init__(self, symbols: Iterable[str], on_event) -> None:
        self.symbols = [s.lower() for s in symbols]
        streams = "/".join(f"{s}@bookTicker" for s in self.symbols)
        url = f"wss://fstream.asterdex.com/stream?streams={streams}"
        super().__init__(name="aster_bookticker", stream_url=url, on_event=on_event)

    async def subscribe(self, ws) -> None:
        return None

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        msg = self.decode(raw)
        data = msg.get("data") or {}
        if not data:
            return
        symbol = data.get("s")
        if symbol and symbol.lower() not in self.symbols:
            return
        try:
            best_bid = float(data.get("b", 0))
            best_ask = float(data.get("a", 0))
            bid_qty = float(data.get("B", 0))
            ask_qty = float(data.get("A", 0))
        except (TypeError, ValueError):
            return
        event = {
            "exchange": "aster",
            "symbol": symbol,
            "stream": "bookTicker",
            "ts_exchange": data.get("T") or data.get("E"),
            "ts_local": ts_local_ms,
            # Unified format: bids/asks arrays, same as depth streams
            "bids": [[best_bid, bid_qty]],
            "asks": [[best_ask, ask_qty]],
            "raw": data,
        }
        await self.on_event(event)


# ============================================================
# User data stream (private data, authentication required)
# ============================================================

class AsterUserWS(WebsocketClient):
    """Aster user data stream

    Subscribes to private data including account orders, positions, and balances.

    Features:
    - Requires API Key authentication
    - Real-time push of account changes
    - Automatic keepalive (renewed every 30 minutes)

    Authentication flow:
        1. Create a listenKey using the API Key
        2. Connect to WebSocket using the listenKey
        3. Auto-renew every 30 minutes

    WebSocket URL:
        wss://fstream.asterdex.com/ws/<listenKey>

    Usage example:
        ws = AsterUserWS(api_key='your_key', on_event=on_event)
        await ws.run_forever()
    """

    def __init__(
        self,
        api_key: str,
        on_event,
        *,
        rest_base: str = "https://fapi.asterdex.com",
        ws_base: str = "wss://fstream.asterdex.com",
        keepalive_interval: float = 30 * 60,
        proxies: Optional[Dict[str, str]] = None,
        reconnect_delay: float = 3.0,
    ) -> None:
        """Initialize the user data stream client

        Args:
            api_key: Aster API Key
            on_event: Event handler callback function
            rest_base: REST API base URL
            ws_base: WebSocket base URL
            keepalive_interval: listenKey keepalive interval in seconds (default 30 minutes)
            proxies: Proxy configuration; None uses environment variables
            reconnect_delay: Reconnection delay in seconds
        """
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

        super().__init__(name="aster-user", stream_url="", on_event=on_event, reconnect_delay=reconnect_delay)

    # ---- REST helpers ----
    def _create_listen_key(self) -> str:
        """Create a listenKey"""
        url = f"{self.rest_base}/fapi/v1/listenKey"
        resp = self.session.post(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        listen_key = data.get("listenKey")
        if not listen_key:
            raise RuntimeError("Missing listenKey field")
        return listen_key

    def _keepalive_listen_key(self, listen_key: str) -> None:
        """Renew the listenKey"""
        url = f"{self.rest_base}/fapi/v1/listenKey"
        resp = self.session.put(url, params={"listenKey": listen_key}, timeout=10)
        resp.raise_for_status()

    # ---- Hooks into base lifecycle ----
    async def get_stream_url(self) -> str:
        """Get WebSocket URL (creates a new listenKey on each reconnect)"""
        self._listen_key = await async_with_timeout(self._create_listen_key, timeout_sec=10)
        return f"{self.ws_base}/ws/{self._listen_key}"

    async def on_connect(self, ws) -> None:
        """Start keepalive task after connection is established"""
        if not self._listen_key:
            logger.error("[aster-user] no listenKey available, user stream will not receive keepalive")
            return
        # Start listenKey keepalive
        self._keepalive_task = asyncio.create_task(self._keepalive_loop(self._listen_key))
        logger.info(f"[aster-user] connected with listenKey: {self._listen_key[:8]}...")

    async def on_disconnect(self) -> None:
        """Clean up keepalive task after disconnection"""
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
        self._keepalive_task = None

    async def _keepalive_loop(self, listen_key: str) -> None:
        """listenKey keepalive loop"""
        while True:
            await asyncio.sleep(self.keepalive_interval)
            try:
                await async_with_timeout(self._keepalive_listen_key, listen_key, timeout_sec=10)
                logger.debug("[aster-user] listenKey keepalive ok")
            except Exception as exc:  # noqa
                logger.warning(f"[aster-user] listenKey keepalive failed: {exc}")

    # ---- WS handlers ----
    async def subscribe(self, ws) -> None:
        # User stream requires no additional subscribe message
        return None

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        """Handle user data stream messages"""
        msg = self.decode(raw)
        event_type = msg.get("e")
        base_event: Dict[str, Any] = {
            "exchange": "aster",
            "stream": "user",
            "event_type": event_type,
            "ts_exchange": msg.get("E") or msg.get("T"),
            "ts_local": ts_local_ms,
            "raw": msg,
        }

        if event_type == "ORDER_TRADE_UPDATE":
            order = msg.get("o") or {}
            parsed = {
                "type": "order",
                "symbol": order.get("s"),
                "order_id": str(order.get("i")) if order.get("i") is not None else None,
                "client_order_id": order.get("c"),
                "side": order.get("S"),
                "order_type": order.get("o"),
                "status": order.get("X"),
                "execution_type": order.get("x"),
                "orig_qty": order.get("q"),
                "filled_qty": order.get("z"),
                "last_qty": order.get("l"),
                "price": order.get("p"),
                "avg_price": order.get("ap"),
                "last_price": order.get("L"),
                "trade_id": order.get("t"),
                "is_maker": order.get("m"),
                "reduce_only": order.get("R"),
                "fee_asset": order.get("N"),
                "fee": order.get("n"),
            }
            base_event.update(parsed)
        elif event_type == "ACCOUNT_UPDATE":
            base_event.update({"type": "account", "account": msg.get("a")})
        elif event_type == "MARGIN_CALL":
            base_event.update({"type": "margin_call", "positions": msg.get("p")})
        elif event_type == "ACCOUNT_CONFIG_UPDATE":
            base_event.update({"type": "config_update", "config": msg.get("ac")})
        elif event_type == "listenKeyExpired":
            base_event.update({"type": "expired"})

        await self.on_event(base_event)
