"""Aster WebSocket 客户端集合

提供三种 WebSocket 客户端：
- AsterWS: 增量更新流（高频交易）
- AsterDepthWS: 完整快照流（普通场景，推荐）
- AsterUserWS: 用户数据流（账户监控）

使用示例：
    # 市场深度快照流（推荐）
    from api.ws.aster import AsterDepthWS
    ws = AsterDepthWS(['xauusdt'], on_event, depth_level=20)
    await ws.run_forever()
    
    # 用户数据流
    from api.ws.aster import AsterUserWS
    ws = AsterUserWS(api_key='your_key', on_event=on_event)
    await ws.run_forever()
"""

import asyncio
from typing import Any, Dict, Iterable, List, Optional

import requests

from api.proxy_utils import get_proxy_config
from logger import setup_logger
from .base import WebsocketClient

logger = setup_logger("ws.aster")


# ============================================================
# 公共工具函数
# ============================================================

def _parse_levels(levels: Iterable[List[str]]) -> List[List[float]]:
    """解析价格档位数据
    
    Args:
        levels: 价格档位列表，格式为 [[price, qty], ...]
        
    Returns:
        解析后的列表，过滤掉数量为 0 的档位
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
# 市场数据流（公开数据，无需认证）
# ============================================================

class AsterWS(WebsocketClient):
    """Aster 增量更新流
    
    订阅市场深度的增量更新，适合高频交易。
    
    特点：
    - 实时推送（延迟 < 10ms）
    - 只推送变化的价格档位
    - 需要客户端维护完整订单簿状态
    
    WebSocket URL:
        wss://fstream.asterdex.com/stream?streams={symbol}@depth
    
    使用示例：
        ws = AsterWS(['xauusdt', 'btcusdt'], on_event)
        await ws.run_forever()
    """

    def __init__(self, symbols: Iterable[str], on_event) -> None:
        """初始化增量更新流客户端
        
        Args:
            symbols: 交易对列表，例如 ['xauusdt', 'btcusdt']
            on_event: 事件处理回调函数
        """
        self.symbols = [s.lower() for s in symbols]
        streams = "/".join(f"{s}@depth" for s in self.symbols)
        url = f"wss://fstream.asterdex.com/stream?streams={streams}"
        super().__init__(name="aster", stream_url=url, on_event=on_event)

    async def subscribe(self, ws) -> None:
        # Aster 使用 URL 聚合流，无需额外订阅消息
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
    """Aster 完整快照流（推荐）
    
    每 250ms 推送完整的订单簿快照，适合大多数场景。
    
    特点：
    - 固定频率推送（250ms）
    - 完整的 N 档买卖盘数据
    - 无需维护状态，直接使用
    
    WebSocket URL:
        wss://fstream.asterdex.com/stream?streams={symbol}@depth{level}
    
    使用示例：
        ws = AsterDepthWS(['xauusdt'], on_event, depth_level=20)
        await ws.run_forever()
    """

    def __init__(self, symbols: Iterable[str], on_event, depth_level: int = 20) -> None:
        """初始化订单簿深度 WebSocket 客户端
        
        Args:
            symbols: 交易对列表，例如 ["xauusdt"]
            on_event: 事件处理回调函数
            depth_level: 订单簿深度档位，支持 5, 10, 20（默认 20）
        """
        self.symbols = [s.lower() for s in symbols]
        self.depth_level = depth_level
        
        # 构建订阅流 URL
        streams = "/".join(f"{s}@depth{depth_level}" for s in self.symbols)
        url = f"wss://fstream.asterdex.com/stream?streams={streams}"
        super().__init__(name=f"aster_depth{depth_level}", stream_url=url, on_event=on_event)

    async def subscribe(self, ws) -> None:
        # Aster 使用 URL 聚合流，无需额外订阅消息
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
# 用户数据流（私有数据，需要认证）
# ============================================================

class AsterUserWS(WebsocketClient):
    """Aster 用户数据流
    
    订阅账户订单、持仓、余额等私有数据。
    
    特点：
    - 需要 API Key 认证
    - 实时推送账户变化
    - 自动保活（每 30 分钟续期）
    
    认证流程：
        1. 使用 API Key 创建 listenKey
        2. 使用 listenKey 连接 WebSocket
        3. 每 30 分钟自动续期
    
    WebSocket URL:
        wss://fstream.asterdex.com/ws/<listenKey>
    
    使用示例：
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
        """初始化用户数据流客户端
        
        Args:
            api_key: Aster API Key
            on_event: 事件处理回调函数
            rest_base: REST API 基础 URL
            ws_base: WebSocket 基础 URL
            keepalive_interval: listenKey 保活间隔（秒），默认 30 分钟
            proxies: 代理配置，None 则使用环境变量
            reconnect_delay: 重连延迟（秒）
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
        """创建 listenKey"""
        url = f"{self.rest_base}/fapi/v1/listenKey"
        resp = self.session.post(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        listen_key = data.get("listenKey")
        if not listen_key:
            raise RuntimeError("缺少 listenKey 字段")
        return listen_key

    def _keepalive_listen_key(self, listen_key: str) -> None:
        """续期 listenKey"""
        url = f"{self.rest_base}/fapi/v1/listenKey"
        resp = self.session.put(url, params={"listenKey": listen_key}, timeout=10)
        resp.raise_for_status()

    # ---- Hooks into base lifecycle ----
    async def get_stream_url(self) -> str:
        """获取 WebSocket URL（每次重连都创建新的 listenKey）"""
        self._listen_key = await asyncio.to_thread(self._create_listen_key)
        return f"{self.ws_base}/ws/{self._listen_key}"

    async def on_connect(self, ws) -> None:
        """连接建立后启动保活任务"""
        if not self._listen_key:
            return
        # 启动 listenKey 保活
        self._keepalive_task = asyncio.create_task(self._keepalive_loop(self._listen_key))
        logger.info(f"[aster-user] connected with listenKey: {self._listen_key[:8]}...")

    async def on_disconnect(self) -> None:
        """断开连接后清理保活任务"""
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
        self._keepalive_task = None

    async def _keepalive_loop(self, listen_key: str) -> None:
        """listenKey 保活循环"""
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
        """处理用户数据流消息"""
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
