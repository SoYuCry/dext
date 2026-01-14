"""轻量 WebSocket 客户端基类，用于行情/用户流订阅（asyncio）。"""
import asyncio
import json
import time
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
    """基础 WebSocket 客户端，负责连接、重连、订阅与消息循环。"""

    def __init__(
        self,
        name: str,
        stream_url: str,
        on_event: EventHandler,
        reconnect_delay: float = 3.0,
    ) -> None:
        self.name = name
        self.stream_url = stream_url
        self.on_event = on_event
        self.reconnect_delay = reconnect_delay

    # ---- 钩子，子类可覆写 ----
    async def subscribe(self, ws: WebSocketClientProtocol) -> None:
        """发送订阅请求（子类实现）。"""
        raise NotImplementedError

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        """解析并处理消息（子类实现）。"""
        raise NotImplementedError

    async def get_stream_url(self) -> str:
        """返回当前连接要使用的 WS URL，子类可动态生成（如 listenKey）。"""
        return self.stream_url

    async def on_connect(self, ws: WebSocketClientProtocol) -> None:
        """连接建立后的额外处理（可选，例如启动保活任务）。"""
        return None

    async def on_disconnect(self) -> None:
        """连接断开后的清理（可选）。"""
        return None

    async def run_forever(self) -> None:
        """保持重连的运行循环。"""
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
            async with connect(
                url,
                max_queue=None,
                ping_interval=15,
                ping_timeout=10,
            ) as ws:
                await self.on_connect(ws)
                await self.subscribe(ws)
                print(f"[{self.name}] connected -> {url}")
                async for raw in ws:
                    ts_local_ms = int(time.time() * 1000)
                    await self.handle_message(raw, ts_local_ms)
        finally:
            await self.on_disconnect()

    @staticmethod
    def decode(raw: str) -> Dict[str, Any]:
        return json.loads(raw)
