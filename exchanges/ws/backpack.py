"""Backpack WS clients (market + user streams)."""
from __future__ import annotations

import base64
import json
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import nacl.signing

from .base import WebsocketClient


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


class BackpackWS(WebsocketClient):
    """Backpack WS market data client."""

    def __init__(
        self,
        symbols: Iterable[str],
        on_event,
        include_depth: bool = True,
    ) -> None:
        self.symbols = [s.upper() for s in symbols]
        self.include_depth = include_depth
        super().__init__(name="backpack", stream_url="wss://ws.backpack.exchange", on_event=on_event)

    async def subscribe(self, ws) -> None:
        params = [f"bookTicker.{s}" for s in self.symbols]
        if self.include_depth:
            params.extend(f"depth.{s}" for s in self.symbols)
        await ws.send(json.dumps({"method": "SUBSCRIBE", "params": params}))

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        msg = self.decode(raw)
        stream = msg.get("stream")
        if not stream:
            return

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
                "ts_exchange": data.get("T") or data.get("E") or None,
                "ts_local": ts_local_ms,
                "bids": [[bid_price, bid_qty]],
                "asks": [[ask_price, ask_qty]],
                "raw": data,
            }
            await self.on_event(event)
            return

        if stream.startswith("depth."):
            symbol = stream.split(".")[-1].upper()
            if symbol not in self.symbols:
                return
            data = msg.get("data") or {}
            event = {
                "exchange": "backpack",
                "symbol": symbol,
                "stream": "l2",
                "ts_exchange": data.get("T") or data.get("E") or None,
                "ts_local": ts_local_ms,
                "bids": _parse_levels(data.get("b", [])),
                "asks": _parse_levels(data.get("a", [])),
                "raw": data,
            }
            await self.on_event(event)


class BackpackUserWS(WebsocketClient):
    """Backpack user data stream (orders + fills)."""

    def __init__(
        self,
        api_key: str,
        secret: str,
        on_event,
        *,
        window: int = 5000,
        reconnect_delay: float = 3.0,
    ) -> None:
        self.api_key = api_key
        self.secret = secret
        self.window = window
        super().__init__(
            name="backpack-user",
            stream_url="wss://ws.backpack.exchange",
            on_event=on_event,
            reconnect_delay=reconnect_delay,
        )

    def _create_signature(self, instruction: str, timestamp: int, window: int) -> Tuple[str, str]:
        message = f"instruction={instruction}&timestamp={timestamp}&window={window}"
        decoded_secret = base64.b64decode(self.secret)
        signing_key = nacl.signing.SigningKey(decoded_secret)
        signature_bytes = signing_key.sign(message.encode("utf-8")).signature
        signature = base64.b64encode(signature_bytes).decode("utf-8")
        return self.api_key, signature

    async def subscribe(self, ws) -> None:
        timestamp = int(time.time() * 1000)
        verifying_key, signature = self._create_signature("subscribe", timestamp, self.window)
        params = ["account.orderUpdate", "account.fillUpdate"]
        sub = {
            "method": "SUBSCRIBE",
            "params": params,
            "signature": [verifying_key, signature, str(timestamp), str(self.window)],
        }
        await ws.send(json.dumps(sub))

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        msg = self.decode(raw)
        stream = msg.get("stream")
        if not stream:
            return

        data = msg.get("data") or {}
        if stream == "account.orderUpdate":
            event = self._parse_order_update(data, ts_local_ms)
            await self.on_event(event)
            return

        if stream == "account.fillUpdate":
            event = self._parse_fill_update(data, ts_local_ms)
            await self.on_event(event)
            return

    def _parse_order_update(self, data: dict, ts_local_ms: int) -> Dict[str, Any]:
        return {
            "exchange": "backpack",
            "stream": "user",
            "event_type": "ORDER_UPDATE",
            "type": "order",
            "ts_exchange": data.get("eventTime") or data.get("E") or None,
            "ts_local": ts_local_ms,
            "symbol": data.get("symbol"),
            "order_id": str(data.get("orderId")) if data.get("orderId") is not None else None,
            "client_order_id": data.get("clientOrderId"),
            "side": data.get("side"),
            "order_type": data.get("orderType"),
            "status": data.get("status"),
            "time_in_force": data.get("timeInForce"),
            "orig_qty": data.get("quantity"),
            "filled_qty": data.get("executedQuantity"),
            "price": data.get("price"),
            "trigger_price": data.get("triggerPrice"),
            "post_only": data.get("postOnly"),
            "self_trade_prevention": data.get("selfTradePrevention"),
            "raw": data,
        }

    def _parse_fill_update(self, data: dict, ts_local_ms: int) -> Dict[str, Any]:
        return {
            "exchange": "backpack",
            "stream": "user",
            "event_type": "FILL_UPDATE",
            "type": "trade",
            "ts_exchange": data.get("eventTime") or data.get("E") or None,
            "ts_local": ts_local_ms,
            "symbol": data.get("symbol"),
            "trade_id": str(data.get("tradeId")) if data.get("tradeId") is not None else None,
            "order_id": str(data.get("orderId")) if data.get("orderId") is not None else None,
            "client_order_id": data.get("clientOrderId"),
            "side": data.get("side"),
            "last_price": data.get("price"),
            "last_qty": data.get("quantity"),
            "fee": data.get("fee"),
            "fee_asset": data.get("feeSymbol"),
            "is_maker": data.get("isMaker"),
            "raw": data,
        }
