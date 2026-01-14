"""Backpack 行情订阅（bookTicker 与 depth）。"""
import json
from typing import Iterable, List, Optional, Tuple

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
