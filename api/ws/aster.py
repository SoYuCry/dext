"""Aster 行情订阅（深度）。"""
from typing import Iterable, List

from .base import WebsocketClient


def _parse_levels(levels: Iterable[List[str]]) -> List[List[float]]:
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


class AsterWS(WebsocketClient):
    """
    Aster WebSocket:
    - Endpoint: wss://fstream.asterdex.com/stream?streams={symbol@depth/...}
    """

    def __init__(self, symbols: Iterable[str], on_event) -> None:
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
            "type": "l2",
            "ts_exchange": data.get("E") or data.get("T"),
            "ts_local": ts_local_ms,
            "bids": _parse_levels(data.get("b", [])),
            "asks": _parse_levels(data.get("a", [])),
            "raw": data,
        }
        await self.on_event(event)
