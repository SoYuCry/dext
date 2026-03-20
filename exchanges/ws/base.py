"""Lightweight WebSocket client base class for market data / user stream subscriptions (asyncio)."""
import asyncio
import json
import time
import inspect
from typing import Any, Awaitable, Callable, Dict, Optional

try:
    import websockets
    from websockets import connect
    from websockets.client import WebSocketClientProtocol
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "websockets>=11.0.0 is required; please install it first (pip install websockets>=11)"
    ) from exc

EventHandler = Callable[[Dict[str, Any]], Awaitable[None]]


class WebsocketClient:
    """Base WebSocket client handling connection, reconnection, subscription, and message loop."""

    def __init__(
        self,
        name: str,
        stream_url: str,
        on_event: EventHandler,
        reconnect_delay: float = 3.0,
        warn_on_no_message_after: float = 5.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.name = name
        self.stream_url = stream_url
        self.on_event = on_event
        self.reconnect_delay = reconnect_delay
        self.warn_on_no_message_after = warn_on_no_message_after
        self.extra_headers = extra_headers
        self._first_message = asyncio.Event()

    # ---- Hooks, subclasses may override ----
    async def subscribe(self, ws: WebSocketClientProtocol) -> None:
        """Send subscription request (subclass implementation)."""
        raise NotImplementedError

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        """Parse and handle a message (subclass implementation)."""
        raise NotImplementedError

    async def get_stream_url(self) -> str:
        """Return the WS URL for the current connection; subclasses may generate dynamically (e.g. listenKey)."""
        return self.stream_url

    async def on_connect(self, ws: WebSocketClientProtocol) -> None:
        """Additional handling after connection is established (optional, e.g. start keepalive task)."""
        return None

    async def on_disconnect(self) -> None:
        """Cleanup after disconnection (optional)."""
        return None

    async def run_forever(self) -> None:
        """Reconnecting run loop."""
        while True:
            try:
                await self._run_once()
            except websockets.exceptions.ConnectionClosed as exc:
                print(f"[{self.name}] connection closed ({exc}), reconnecting in {self.reconnect_delay}s")
                await asyncio.sleep(self.reconnect_delay)
            except Exception as exc:
                print(f"[{self.name}] error: {exc}, reconnecting in {self.reconnect_delay}s")
                await asyncio.sleep(self.reconnect_delay)

    async def _run_once(self) -> None:
        url = await self.get_stream_url()
        try:
            connect_kwargs = {
                "max_queue": None,
                "ping_interval": 15,
                "ping_timeout": 10,
            }
            if self.extra_headers:
                params = inspect.signature(connect).parameters
                if "additional_headers" in params:
                    connect_kwargs["additional_headers"] = self.extra_headers
                else:
                    connect_kwargs["extra_headers"] = self.extra_headers
            async with connect(url, **connect_kwargs) as ws:
                await self.on_connect(ws)
                await self.subscribe(ws)
                print(f"[{self.name}] connected -> {url}")
                watchdog = None
                if self.warn_on_no_message_after and self.warn_on_no_message_after > 0:
                    watchdog = asyncio.create_task(self._wait_first_message(url))
                try:
                    async for raw in ws:
                        ts_local_ms = int(time.time() * 1000)
                        self._first_message.set()
                        await self.handle_message(raw, ts_local_ms)
                finally:
                    if watchdog:
                        watchdog.cancel()
                        try:
                            await watchdog
                        except asyncio.CancelledError:
                            pass
        finally:
            await self.on_disconnect()

    @staticmethod
    def decode(raw: str) -> Dict[str, Any]:
        return json.loads(raw)

    async def _wait_first_message(self, url: str) -> None:
        try:
            await asyncio.wait_for(self._first_message.wait(), timeout=self.warn_on_no_message_after)
        except asyncio.TimeoutError:
            print(f"[{self.name}] warning: no message received within {self.warn_on_no_message_after}s after connect (url={url})")
