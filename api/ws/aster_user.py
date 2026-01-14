"""Aster 账户/订单私有流订阅（USER_STREAM）。"""
import asyncio
import time
from typing import Any, Dict, Optional

import requests

from api.proxy_utils import get_proxy_config
from logger import setup_logger
from .base import WebsocketClient

logger = setup_logger("ws.aster_user")


class AsterUserWS(WebsocketClient):
    """
    Aster User Data Stream (Binance 风格):
    - 创建 listenKey: POST https://fapi.asterdex.com/fapi/v1/listenKey (Header: X-MBX-APIKEY)
    - 续期 listenKey: PUT  同路由，建议 30 分钟内保活一次
    - WebSocket:      wss://fstream.asterdex.com/ws/<listenKey>
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
        url = f"{self.rest_base}/fapi/v1/listenKey"
        resp = self.session.post(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        listen_key = data.get("listenKey")
        if not listen_key:
            raise RuntimeError("缺少 listenKey 字段")
        return listen_key

    def _keepalive_listen_key(self, listen_key: str) -> None:
        url = f"{self.rest_base}/fapi/v1/listenKey"
        resp = self.session.put(url, params={"listenKey": listen_key}, timeout=10)
        resp.raise_for_status()

    # ---- Hooks into base lifecycle ----
    async def get_stream_url(self) -> str:
        # 每次重连都创建新的 listenKey，避免过期
        self._listen_key = await asyncio.to_thread(self._create_listen_key)
        return f"{self.ws_base}/ws/{self._listen_key}"

    async def on_connect(self, ws) -> None:
        if not self._listen_key:
            return
        # 启动 listenKey 保活
        self._keepalive_task = asyncio.create_task(self._keepalive_loop(self._listen_key))
        logger.info(f"[aster-user] connected with listenKey: {self._listen_key[:8]}...")

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
                await asyncio.to_thread(self._keepalive_listen_key, listen_key)
                logger.debug("[aster-user] listenKey keepalive ok")
            except Exception as exc:  # noqa
                logger.warning(f"[aster-user] listenKey keepalive failed: {exc}")

    # ---- WS handlers ----
    async def subscribe(self, ws) -> None:
        # 用户流无需额外订阅消息
        return None

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
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
