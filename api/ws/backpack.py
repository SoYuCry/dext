"""Backpack 行情订阅（bookTicker 与 depth）和用户数据流。"""
import base64
import json
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import nacl.signing

from .base import WebsocketClient


def _parse_levels(levels: List[List[str]]) -> List[List[float]]:
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


class BackpackWS(WebsocketClient):
    """
    Backpack WebSocket:
    - Endpoint: wss://ws.backpack.exchange
    - Streams: bookTicker.{SYMBOL} (默认)，depth.{SYMBOL}（可选）
    """

    def __init__(
        self,
        symbols: Iterable[str],
        on_event,
        include_depth: bool = True,
    ) -> None:
        self.symbols = [s.upper() for s in symbols]
        self.include_depth = include_depth
        url = "wss://ws.backpack.exchange"
        super().__init__(name="backpack", stream_url=url, on_event=on_event)

    async def subscribe(self, ws) -> None:
        params = [f"bookTicker.{s}" for s in self.symbols]
        if self.include_depth:
            params.extend(f"depth.{s}" for s in self.symbols)
        sub = {"method": "SUBSCRIBE", "params": params}
        await ws.send(json.dumps(sub))

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        msg = self.decode(raw)
        stream = msg.get("stream")
        if not stream:
            return

        # bookTicker
        if stream.startswith("bookTicker."):
            symbol = stream.split(".")[-1].upper()
            if symbol not in self.symbols:
                return
            data = msg.get("data") or {}
            parsed = _parse_book_ticker(data)
            if not parsed:
                return
            bid_price, bid_qty, ask_price, ask_qty = parsed
            event = {
                "exchange": "backpack",
                "symbol": symbol,
                "stream": "bbo",
                "ts_exchange": data.get("T") or data.get("E") or ts_local_ms,
                "ts_local": ts_local_ms,
                "bids": [[bid_price, bid_qty]],
                "asks": [[ask_price, ask_qty]],
                "raw": data,
            }
            await self.on_event(event)
            return

        # depth
        if stream.startswith("depth."):
            symbol = stream.split(".")[-1].upper()
            if symbol not in self.symbols:
                return
            data = msg.get("data") or {}
            event = {
                "exchange": "backpack",
                "symbol": symbol,
                "stream": "l2",
                "ts_exchange": data.get("T") or data.get("E") or ts_local_ms,
                "ts_local": ts_local_ms,
                "bids": _parse_levels(data.get("b", [])),
                "asks": _parse_levels(data.get("a", [])),
                "raw": data,
            }
            await self.on_event(event)


class BackpackUserWS(WebsocketClient):
    """Backpack 用户数据流

    订阅账户订单、成交、余额等私有数据。

    特点:
    - 需要 API Key + Secret 签名认证
    - 实时推送订单成交
    - 自动重连

    WebSocket URL:
        wss://ws.backpack.exchange

    认证方式:
        ED25519 签名，签名字符串格式：instruction=subscribe&timestamp=xxx&window=xxx

    使用示例:
        ws = BackpackUserWS(api_key='...', secret='...', on_event=handler)
        await ws.run_forever()
    """

    def __init__(
        self,
        api_key: str,
        secret: str,
        on_event,
        *,
        window: int = 5000,
        reconnect_delay: float = 3.0,
    ) -> None:
        """初始化用户数据流客户端

        Args:
            api_key: Backpack API Key (Base64 编码的公钥)
            secret: Backpack Secret (Base64 编码的私钥)
            on_event: 事件处理回调函数
            window: 签名时间窗口（毫秒），默认 5000ms
            reconnect_delay: 重连延迟（秒）
        """
        self.api_key = api_key
        self.secret = secret
        self.window = window

        url = "wss://ws.backpack.exchange"
        super().__init__(
            name="backpack-user",
            stream_url=url,
            on_event=on_event,
            reconnect_delay=reconnect_delay
        )

    def _create_signature(self, instruction: str, timestamp: int, window: int) -> Tuple[str, str]:
        """创建 ED25519 签名

        Args:
            instruction: 操作指令（如 "subscribe"）
            timestamp: Unix 时间戳（毫秒）
            window: 时间窗口（毫秒）

        Returns:
            (verifying_key, signature) 元组，均为 Base64 编码
        """
        # 构建签名字符串
        message = f"instruction={instruction}&timestamp={timestamp}&window={window}"

        # 解码私钥并签名
        decoded_secret = base64.b64decode(self.secret)
        signing_key = nacl.signing.SigningKey(decoded_secret)
        signature_bytes = signing_key.sign(message.encode('utf-8')).signature

        # Base64 编码签名
        signature = base64.b64encode(signature_bytes).decode('utf-8')

        # 返回公钥（API Key）和签名
        return self.api_key, signature

    async def subscribe(self, ws) -> None:
        """发送认证和订阅消息"""
        # 创建签名
        timestamp = int(time.time() * 1000)
        verifying_key, signature = self._create_signature("subscribe", timestamp, self.window)

        # 订阅所有账户相关的流
        # 参考文档：私有流以 account. 为前缀
        params = [
            "account.orderUpdate",  # 订单更新
            "account.fillUpdate",   # 成交更新
        ]

        # 构建订阅消息（包含签名）
        sub = {
            "method": "SUBSCRIBE",
            "params": params,
            "signature": [verifying_key, signature, str(timestamp), str(self.window)]
        }

        await ws.send(json.dumps(sub))

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        """处理用户数据流消息"""
        msg = self.decode(raw)
        stream = msg.get("stream")

        # 忽略订阅确认消息
        if not stream:
            return

        data = msg.get("data") or {}

        # 订单更新
        if stream == "account.orderUpdate":
            event = self._parse_order_update(data, ts_local_ms)
            await self.on_event(event)
            return

        # 成交更新
        if stream == "account.fillUpdate":
            event = self._parse_fill_update(data, ts_local_ms)
            await self.on_event(event)
            return

    def _parse_order_update(self, data: dict, ts_local_ms: int) -> Dict[str, Any]:
        """解析订单更新消息"""
        return {
            "exchange": "backpack",
            "stream": "user",
            "event_type": "ORDER_UPDATE",
            "type": "order",
            "ts_exchange": data.get("eventTime") or data.get("E") or ts_local_ms,
            "ts_local": ts_local_ms,

            # 订单信息
            "symbol": data.get("symbol"),
            "order_id": str(data.get("orderId")) if data.get("orderId") is not None else None,
            "client_order_id": data.get("clientOrderId"),
            "side": data.get("side"),  # Buy / Sell
            "order_type": data.get("orderType"),  # Limit / Market
            "status": data.get("status"),  # New / PartiallyFilled / Filled / Cancelled
            "time_in_force": data.get("timeInForce"),

            # 数量和价格
            "orig_qty": data.get("quantity"),
            "filled_qty": data.get("executedQuantity"),
            "price": data.get("price"),
            "trigger_price": data.get("triggerPrice"),

            # 其他字段
            "post_only": data.get("postOnly"),
            "self_trade_prevention": data.get("selfTradePrevention"),

            "raw": data,
        }

    def _parse_fill_update(self, data: dict, ts_local_ms: int) -> Dict[str, Any]:
        """解析成交更新消息"""
        return {
            "exchange": "backpack",
            "stream": "user",
            "event_type": "FILL_UPDATE",
            "type": "trade",
            "ts_exchange": data.get("eventTime") or data.get("E") or ts_local_ms,
            "ts_local": ts_local_ms,

            # 成交信息
            "symbol": data.get("symbol"),
            "trade_id": str(data.get("tradeId")) if data.get("tradeId") is not None else None,
            "order_id": str(data.get("orderId")) if data.get("orderId") is not None else None,
            "client_order_id": data.get("clientOrderId"),
            "side": data.get("side"),

            # 价格和数量
            "last_price": data.get("price"),
            "last_qty": data.get("quantity"),

            # 手续费
            "fee": data.get("fee"),
            "fee_asset": data.get("feeSymbol"),
            "is_maker": data.get("isMaker"),

            "raw": data,
        }
