"""WebSocket entrypoints and unified dispatcher."""
from typing import Any, Callable, Dict, Iterable

from .aster import AsterWS, AsterDepthWS, AsterUserWS
from .backpack import BackpackWS, BackpackUserWS
from .binance import BinanceWS, BinanceUserWS
from .dispatcher import WSDispatcher, create_dispatcher
from .lighter import LighterWS
from .normalizer import (
    AsterNormalizer,
    BinanceNormalizer,
    BackpackNormalizer,
    LighterNormalizer,
    Normalizer,
    VariationalNormalizer,
)
from .types import (
    BBOData,
    BBOUpdate,
    EventMetadata,
    EventType,
    OrderData,
    OrderSide,
    OrderStatus,
    OrderUpdate,
)
from .variational import VariationalPricePoller, VariationalFillPoller, VariationalEventsWS

__all__ = [
    "get_ws_client",
    "get_user_ws_client",
    "WSDispatcher",
    "create_dispatcher",
    "Normalizer",
    "AsterNormalizer",
    "LighterNormalizer",
    "BackpackNormalizer",
    "BinanceNormalizer",
    "VariationalNormalizer",
    "BBOData",
    "BBOUpdate",
    "EventMetadata",
    "EventType",
    "OrderData",
    "OrderSide",
    "OrderStatus",
    "OrderUpdate",
    "BackpackWS",
    "BackpackUserWS",
    "BinanceWS",
    "BinanceUserWS",
    "AsterWS",
    "AsterDepthWS",
    "AsterUserWS",
    "LighterWS",
    "VariationalPricePoller",
    "VariationalFillPoller",
    "VariationalEventsWS",
]


def get_ws_client(name: str, symbols: Iterable[str], on_event: Callable[[Dict[str, Any]], Any], **kwargs):
    """Return a public market-data WS client by exchange name."""
    name = (name or "").lower()
    if name in ("backpack", "bp"):
        return BackpackWS(symbols, on_event, **kwargs)
    if name == "binance":
        return BinanceWS(symbols, on_event, **kwargs)
    if name == "aster":
        return AsterWS(symbols, on_event)
    if name == "lighter":
        market_index = kwargs.pop("market_index", 0)
        return LighterWS(market_index=market_index, on_event=on_event, **kwargs)
    if name in ("variational", "omni"):
        client = kwargs.pop("client", None) or kwargs.pop("variational_client", None)
        if client is None:
            from exchanges.variational import VariationalClient
            config = kwargs.pop("config", None)
            if config is None:
                raise ValueError("Variational price poller requires client or config")
            client = VariationalClient(config)

        symbols_list = list(symbols) if symbols is not None else []
        instrument = kwargs.pop("instrument", None)
        if instrument is None and symbols_list:
            candidate = symbols_list[0]
            if isinstance(candidate, dict):
                instrument = candidate
            elif isinstance(candidate, str):
                instrument = {
                    "underlying": candidate,
                    "funding_interval_s": 3600,
                    "settlement_asset": "USDC",
                    "instrument_type": "perpetual_future",
                }
        if instrument is None:
            raise ValueError("Variational price poller requires instrument (dict)")

        qty = kwargs.pop("qty", "0.01")
        interval = kwargs.pop("interval", 1.0)
        return VariationalPricePoller(
            client=client,
            instrument=instrument,
            qty=qty,
            interval=interval,
            on_event=on_event,
        )
    raise ValueError(f"Unknown exchange: {name}")


def get_user_ws_client(name: str, on_event: Callable[[Dict[str, Any]], Any], **kwargs):
    """Return a user-data WS client by exchange name."""
    name = (name or "").lower()

    if name in ("backpack", "bp"):
        api_key = kwargs.pop("api_key", None)
        secret = kwargs.pop("secret", None)
        if not api_key or not secret:
            raise ValueError("Backpack user stream requires api_key + secret")
        return BackpackUserWS(api_key=api_key, secret=secret, on_event=on_event, **kwargs)

    if name == "aster":
        api_key = kwargs.pop("api_key", None)
        if not api_key:
            raise ValueError("Aster user stream requires api_key")
        return AsterUserWS(api_key=api_key, on_event=on_event, **kwargs)

    if name == "binance":
        api_key = kwargs.pop("api_key", None)
        if not api_key:
            raise ValueError("Binance user stream requires api_key")
        return BinanceUserWS(api_key=api_key, on_event=on_event, **kwargs)

    if name == "lighter":
        market_index = kwargs.pop("market_index", None)
        if market_index is None:
            raise ValueError("Lighter user stream requires market_index")

        lighter_client = kwargs.pop("lighter_client", None)
        if lighter_client is None:
            raise ValueError("Lighter user stream requires lighter_client")

        account_index = kwargs.pop("account_index", None)
        if account_index is None:
            raise ValueError("Lighter user stream requires account_index")
        api_key_index = kwargs.pop("api_key_index", 0)

        return LighterWS(
            market_index=market_index,
            on_event=on_event,
            account_index=account_index,
            lighter_client=lighter_client,
            api_key_index=api_key_index,
            **kwargs,
        )

    if name in ("variational", "omni"):
        mode = kwargs.pop("mode", None) or kwargs.pop("stream", None)
        use_ws = kwargs.pop("use_ws", False)
        if use_ws or mode in ("ws", "events", "event"):
            auth_token = kwargs.pop("auth_token", None) or kwargs.pop("ws_auth", None)
            cookie = kwargs.pop("cookie", None)
            query_params = kwargs.pop("query_params", None) or kwargs.pop("ws_query", None)
            claims_token = kwargs.pop("claims_token", None) or kwargs.pop("ws_claims", None)
            ws_url = kwargs.pop(
                "ws_url",
                "wss://omni-ws-server.prod.ap-northeast-1.variational.io/events",
            )
            origin = kwargs.pop("origin", "https://omni.variational.io")
            if auth_token is None and cookie is None:
                config = kwargs.pop("config", None)
                if config:
                    auth_token = config.get("ws_auth") or config.get("auth_token")
                    cookie = cookie or config.get("cookie")
                    query_params = query_params or config.get("ws_query")
                    claims_token = claims_token or config.get("ws_claims")
            return VariationalEventsWS(
                on_event=on_event,
                ws_url=ws_url,
                auth_token=auth_token,
                query_params=query_params,
                claims_token=claims_token,
                cookie=cookie,
                origin=origin,
                **kwargs,
            )

        client = kwargs.pop("client", None) or kwargs.pop("variational_client", None)
        if client is None:
            from exchanges.variational import VariationalClient
            config = kwargs.pop("config", None)
            if config is None:
                raise ValueError("Variational fill poller requires client or config")
            client = VariationalClient(config)
        interval = kwargs.pop("interval", 2.0)
        limit = kwargs.pop("limit", 50)
        return VariationalFillPoller(client=client, on_event=on_event, interval=interval, limit=limit)

    raise ValueError(f"Unknown exchange: {name}")
