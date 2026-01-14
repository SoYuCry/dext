"""WebSocket 订阅工厂。"""
from typing import Any, Callable, Dict, Iterable

from .aster import AsterWS
from .aster_user import AsterUserWS
from .backpack import BackpackWS

__all__ = ["get_ws_client", "get_user_ws_client", "BackpackWS", "AsterWS", "AsterUserWS"]


def get_ws_client(name: str, symbols: Iterable[str], on_event: Callable[[Dict[str, Any]], Any], **kwargs):
    """按交易所名称返回公开行情 WS 客户端。"""
    name = (name or "").lower()
    if name in ("backpack", "bp"):
        return BackpackWS(symbols, on_event, **kwargs)
    if name == "aster":
        return AsterWS(symbols, on_event)
    raise ValueError(f"未知交易所: {name}")


def get_user_ws_client(name: str, on_event: Callable[[Dict[str, Any]], Any], **kwargs):
    """按交易所名称返回用户数据流（订单/成交） WS 客户端。"""
    name = (name or "").lower()
    if name == "aster":
        api_key = kwargs.get("api_key")
        if not api_key:
            raise ValueError("Aster 用户流需要 api_key")
        return AsterUserWS(api_key=api_key, on_event=on_event, **kwargs)
    raise ValueError(f"未知交易所: {name}")
