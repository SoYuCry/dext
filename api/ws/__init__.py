"""WebSocket 行情订阅工厂。"""
from typing import Any, Callable, Dict, Iterable

from .aster import AsterWS
from .backpack import BackpackWS

__all__ = ["get_ws_client", "BackpackWS", "AsterWS"]


def get_ws_client(name: str, symbols: Iterable[str], on_event: Callable[[Dict[str, Any]], Any], **kwargs):
    """按交易所名称返回对应的 WS 客户端。"""
    name = (name or "").lower()
    if name in ("backpack", "bp"):
        return BackpackWS(symbols, on_event, **kwargs)
    if name == "aster":
        return AsterWS(symbols, on_event)
    raise ValueError(f"未知交易所: {name}")
