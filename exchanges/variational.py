"""Variational (Omni) RFQ client using curl_cffi with browser impersonation."""
from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple

from curl_cffi import requests

from .base.exchange import Exchange
from .endpoints.variational import VariationalEndpoints
from .base.errors import AuthenticationError
from .proxy_utils import get_proxy_config
from exchanges.logger import setup_logger

logger = setup_logger("exchanges.variational")


# ---- Data Classes ----
@dataclass
class ApiResponse:
    """Standardized API response format"""
    success: bool
    data: Optional[Any] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class L1OrderbookInfo:
    """Standardized L1 order book info (best bid/ask)"""
    symbol: str
    exchange: str
    timestamp: int
    bid: Decimal                    # Best bid price
    ask: Decimal                    # Best ask price
    bid_volume: Decimal             # Best bid volume
    ask_volume: Decimal             # Best ask volume
    mid: Decimal                    # Mid price = (bid + ask) / 2
    spread: Decimal                 # Spread = ask - bid
    spread_bps: Decimal             # Spread in basis points = (spread / mid) * 10000
    # Optional fields
    mark_price: Optional[Decimal] = None
    index_price: Optional[Decimal] = None
    raw: Optional[Dict[str, Any]] = None


@dataclass
class PositionInfo:
    """Standardized position info"""
    symbol: str
    side: str  # "LONG", "SHORT", "FLAT"
    size: Decimal
    entry_price: Optional[Decimal] = None
    mark_price: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    margin: Optional[Decimal] = None


def parse_indicative_quote(payload: Any) -> Tuple[str, Decimal, Decimal]:
    """Parse a /quotes/indicative response with strict field requirements."""
    if not isinstance(payload, dict):
        raise ValueError("quote payload must be a dict")
    quote_id = payload.get("quote_id")
    bid_raw = payload.get("bid")
    ask_raw = payload.get("ask")
    if not quote_id:
        raise ValueError("quote_id missing")
    if bid_raw is None or ask_raw is None:
        raise ValueError("bid/ask missing")
    try:
        bid = Decimal(str(bid_raw))
        ask = Decimal(str(ask_raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid bid/ask: {exc}") from exc
    return str(quote_id), bid, ask


class VariationalClient(Exchange):
    """Variational (Omni) RFQ client with Exchange base inheritance."""
    endpoints = VariationalEndpoints()

    def __init__(self, config: Dict[str, Any]):
        # Initialize Exchange base class
        super().__init__(config)
        
        # Variational-specific configuration
        self.base_url = config.get("base_url", "https://omni.variational.io/api")
        self.api_version = config.get("api_version", "v2")
        self.cookie = config.get("cookie") or config.get("Cookie")
        self.connected_address = (
            config.get("vr_connected_address")
            or config.get("connected_address")
            or config.get("wallet_address")
        )
        self.counterparty = config.get("counterparty") or config.get("counterparty_id")
        self.impersonate = config.get("impersonate", "chrome120")
        self.timeout = float(config.get("timeout", 10))
        self.retry_sleep = float(config.get("retry_sleep", 0.5))
        self.default_instrument: Dict[str, Any] = config.get(
            "instrument",
            {
                "underlying": config.get("underlying", "ETH"),
                "funding_interval_s": int(config.get("funding_interval_s", 3600)),
                "settlement_asset": config.get("settlement_asset", "USDC"),
                "instrument_type": config.get("instrument_type", "perpetual_future"),
            },
        )
        self.origin = config.get("origin", "https://omni.variational.io")
        self.referer = config.get("referer", "https://omni.variational.io/")
        self.user_agent = config.get(
            "user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        self.session = requests.Session(impersonate=self.impersonate)
        proxies = get_proxy_config()
        if proxies:
            self.session.proxies.update(proxies)
            logger.info("Variational client using proxies: %s", proxies)

    # ---- Required exchange methods ----
    def describe(self) -> Dict[str, Any]:
        """Exchange description."""
        return self.deep_extend(super().describe(), {
            "id": "variational",
            "name": "Variational (Omni)",
            "countries": ["US"],
            "rateLimit": 1000,  # RFQ mode, more lenient rate limiting
            "certified": False,
            "pro": False,
            "has": {
                "CORS": None,
                "spot": False,
                "margin": False,
                "swap": True,
                "future": False,
                "option": False,
                "fetchMarkets": False,  # RFQ mode, no traditional markets
                "fetchOrderBook": False,  # RFQ mode, no order book
                "createOrder": False,  # Use custom RFQ methods instead
                "cancelOrder": True,
                "fetchPositions": True,
                "fetchBalance": False,
            },
            "urls": {
                "logo": "https://variational.io/logo.png",
                "www": "https://variational.io",
                "api": {
                    "public": "https://omni.variational.io/api",
                    "private": "https://omni.variational.io/api",
                },
                "doc": "https://docs.variational.io",
            },
            "requiredCredentials": {
                "apiKey": False,
                "secret": False,
                "cookie": True,  # Custom: Cookie-based auth
                "connectedAddress": True,  # Custom: Wallet address
            },
            "api": {
                "public": {
                    "get": ["instruments", "status"],
                },
                "private": {
                    "get": ["orders/v2", "positions", "transfers"],
                    "post": [
                        "quotes/indicative",
                        "orders/new/market",
                        "orders/new/limit",
                        "orders/cancel",
                    ],
                },
            },
        })

    def sign(
        self,
        path: str,
        api: str = "public",
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        body: Any = None,
    ) -> Dict[str, Any]:
        """
        Handle Cookie-based authentication for Variational

        Variational uses Cookie + wallet address authentication instead of
        API Key/Secret. This is required for browser impersonation with curl_cffi.

        Args:
            path: API endpoint path
            api: 'public' or 'private'
            method: HTTP method
            params: Query parameters
            headers: Additional headers
            body: Request body

        Returns:
            dict with 'url', 'method', 'body', and 'headers'

        Raises:
            AuthenticationError: If cookie or connected_address is missing for private endpoints
        """
        url = self._build_url(path)
        headers = headers or {}

        if api == "private":
            if not self.cookie or not self.connected_address:
                raise AuthenticationError(
                    f"{self.id} requires cookie and connected_address for private endpoints"
                )
            headers["Cookie"] = self.cookie
            headers["vr-connected-address"] = self.connected_address

        # Add browser impersonation headers
        headers.update({
            "Content-Type": "application/json",
            "Origin": self.origin,
            "Referer": self.referer,
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
        })

        return {"url": url, "method": method, "body": body, "headers": headers}

    # ---- helpers ----
    def _build_url(self, endpoint: str) -> str:
        if endpoint.startswith("http"):
            return endpoint
        prefix = f"/{self.api_version.strip('/')}" if self.api_version else ""
        return f"{self.base_url.rstrip('/')}{prefix}/{endpoint.lstrip('/')}"

    def _headers(self, instruction: Optional[str] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Origin": self.origin,
            "Referer": self.referer,
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.connected_address:
            headers["vr-connected-address"] = self.connected_address
        if instruction:
            headers["vr-instruction"] = instruction
        return headers

    def _to_str(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            value = value.normalize()
            text = format(value, "f")
            return text.rstrip("0").rstrip(".") or "0"
        return str(value)

    def _normalize_instrument(self, instrument: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if instrument:
            return instrument
        return self.default_instrument

    def _format_instrument_symbol(self, instrument: Any) -> str:
        """Format instrument dict into a human-readable symbol."""
        if isinstance(instrument, dict):
            underlying = instrument.get("underlying")
            settle = instrument.get("settlement_asset")
            itype = instrument.get("instrument_type") or ""
            if underlying and settle:
                suffix = "_PERP" if "perp" in itype else ""
                return f"{underlying}_{settle}{suffix}"
        return str(instrument or "")

    # ---- core HTTP ----
    def make_request(
        self,
        method: str,
        endpoint: str,
        api_key=None,
        secret_key=None,
        instruction=None,
        params=None,
        data=None,
        retry_count: int = 3,
    ) -> Dict[str, Any]:
        if instruction and not self.cookie:
            raise AuthenticationError("Variational cookie not set for private request to " + endpoint)
        url = self._build_url(endpoint)
        headers = self._headers(instruction)

        for attempt in range(1, retry_count + 1):
            try:
                resp = self.session.request(
                    method.upper(),
                    url,
                    params=params,
                    json=data if data is not None else None,
                    headers=headers,
                    timeout=self.timeout,
                )
                status = resp.status_code
                if status >= 400:
                    text = resp.text
                    logger.warning("Variational request failed (%s %s): %s", status, url, text[:200])
                    if attempt < retry_count:
                        time.sleep(self.retry_sleep)
                        continue
                    return {"error": text or f"HTTP {status}", "status_code": status}
                try:
                    return resp.json()
                except (ValueError, TypeError, KeyError):
                    return {"raw": resp.text}
            except (OSError, ValueError, TypeError) as exc:  # noqa
                logger.error("Variational request error: %s", exc)
                if attempt >= retry_count:
                    return {"error": str(exc)}
                time.sleep(self.retry_sleep)
        return {"error": "unreachable"}

    # ---- RFQ helpers ----
    def request_indicative_quote(
        self,
        qty: Any,
        *,
        instrument: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> ApiResponse:
        payload: Dict[str, Any] = {
            "instrument": self._normalize_instrument(instrument),
            "qty": self._to_str(qty),
        }
        if self.counterparty:
            payload["counterparty"] = self.counterparty
        if extra:
            payload.update(extra)

        resp = self.make_request("POST", "/quotes/indicative", data=payload)

        if isinstance(resp, dict) and resp.get("error"):
            return ApiResponse(success=False, error_message=resp.get("error"), data=resp)
        try:
            quote_id, bid, ask = parse_indicative_quote(resp)
        except ValueError as exc:
            return ApiResponse(success=False, error_message=str(exc), data=resp)

        mid = (bid + ask) / 2

        return ApiResponse(
            success=True,
            data={
                "quote_id": str(quote_id),
                "bid": bid,
                "ask": ask,
                "price": mid,
                "raw": resp,
                "payload": payload,
            },
        )

    def place_market_order(
        self,
        side: str,
        qty: Any,
        *,
        max_slippage: float = 0.05,
        instrument: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
        quote_id: Optional[str] = None,
        price_hint: Optional[Any] = None,
    ) -> ApiResponse:
        quote_resp = None
        if not quote_id:
            quote_resp = self.request_indicative_quote(qty, instrument=instrument, extra=extra)
            if not quote_resp.success:
                return quote_resp
            quote_id = quote_resp.data.get("quote_id") if quote_resp.data else None

        if not quote_id:
            return ApiResponse(success=False, error_message="quote_id missing", data={"quote_id": None})

        payload: Dict[str, Any] = {
            "quote_id": quote_id,
            "side": side.lower(),
            "max_slippage": max_slippage,
        }
        if self.counterparty:
            payload["counterparty"] = self.counterparty
        if extra:
            payload.update(extra)

        resp = self.make_request("POST", "/orders/new/market", data=payload)
        if isinstance(resp, dict) and resp.get("error"):
            return ApiResponse(success=False, error_message=resp.get("error"), data=resp)

        order_id = (
            resp.get("rfq_id")
            or resp.get("order_id")
            or resp.get("id")
            or quote_id
        )
        return ApiResponse(
            success=True,
            data={
                "id": str(order_id) if order_id else None,
                "order_id": str(order_id) if order_id else None,
                "side": side.lower(),
                "amount": self._to_str(qty),
                "price": self._to_str(price_hint) if price_hint is not None else (quote_resp.data.get("price") if quote_resp else None),
                "raw": resp,
            },
        )

    def place_limit_order(
        self,
        side: str,
        qty: Any,
        price: Any,
        *,
        order_type: str = "limit",
        max_slippage: Optional[float] = None,
        trigger_price: Optional[Any] = None,
        instrument: Optional[Dict[str, Any]] = None,
        is_auto_resize: bool = False,
        use_mark_price: Optional[bool] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> ApiResponse:
        payload: Dict[str, Any] = {
            "order_type": (order_type or "limit").lower(),
            "limit_price": self._to_str(price),
            "side": side.lower(),
            "instrument": self._normalize_instrument(instrument),
            "qty": self._to_str(qty),
            "is_auto_resize": is_auto_resize,
        }
        if self.counterparty:
            payload["counterparty"] = self.counterparty
        if trigger_price is not None:
            payload["trigger_price"] = self._to_str(trigger_price)
        if use_mark_price is not None:
            payload["use_mark_price"] = use_mark_price
        # limit order endpoint may ignore this; keep for API-compat with market params
        if max_slippage is not None:
            payload.setdefault("max_slippage", max_slippage)
        if extra:
            payload.update(extra)

        resp = self.make_request("POST", "/orders/new/limit", data=payload)
        if isinstance(resp, dict) and resp.get("error"):
            return ApiResponse(success=False, error_message=resp.get("error"), data=resp)

        order_id = resp.get("rfq_id") or resp.get("order_id") or resp.get("id")
        return ApiResponse(
            success=True,
            data={
                "id": str(order_id) if order_id else None,
                "order_id": str(order_id) if order_id else None,
                "side": side.lower(),
                "amount": self._to_str(qty),
                "price": self._to_str(price),
                "raw": resp,
            },
        )

    # ---- Standardized thin wrappers ----
    def create_order(self, symbol: str, type: str, side: str, amount: Any, price: Optional[Any] = None, params=None):
        """Alias compatible with strategy wrappers; symbol is ignored because Omni uses instrument tuples."""
        params = params or {}
        if type.lower() == "market":
            resp = self.place_market_order(side, amount, **params)
        elif type.lower() == "limit":
            resp = self.place_limit_order(side, amount, price, **params)
        else:
            raise ValueError(f"Unsupported order type for Variational: {type}")

        if isinstance(resp, ApiResponse):
            if resp.success:
                return resp.data
            raise RuntimeError(resp.error_message or "order failed")
        return resp

    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> ApiResponse:
        payload = {"rfq_id": order_id}
        resp = self.make_request("POST", "/orders/cancel", data=payload)
        if isinstance(resp, dict) and resp.get("error"):
            return ApiResponse(success=False, error_message=resp.get("error"), data=resp)
        return ApiResponse(success=True, data=resp)

    def cancel_all_orders(self, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None):
        """Cancel all open orders, optionally filtered by symbol.

        Fetches open orders via fetch_open_orders() and cancels each one individually.

        Args:
            symbol: Optional symbol filter (currently unused by Variational API)
            params: Optional extra parameters (reserved for future use)

        Returns:
            List of ApiResponse results from each cancel_order() call
        """
        from .base.errors import ExchangeError, NetworkError, ExchangeNotAvailable

        open_orders = self.fetch_open_orders(symbol=symbol)
        if isinstance(open_orders, dict) and open_orders.get("error"):
            logger.error("cancel_all_orders: failed to fetch open orders: %s", open_orders.get("error"))
            return []

        if not isinstance(open_orders, list):
            open_orders = open_orders.get("orders", []) if isinstance(open_orders, dict) else []

        results = []
        for order in open_orders:
            if not isinstance(order, dict):
                continue
            order_id = order.get("rfq_id") or order.get("order_id") or order.get("id")
            if order_id is None:
                continue
            try:
                results.append(self.cancel_order(str(order_id), symbol=symbol))
            except (NetworkError, ExchangeNotAvailable) as exc:
                logger.warning("cancel_order(%s) transient error: %s", order_id, exc)
                continue
            except ExchangeError as exc:
                logger.error("cancel_order(%s) failed: %s", order_id, exc)
                continue
        return results

    def fetch_open_orders(self, symbol: Optional[str] = None) -> Any:
        return self.make_request("GET", "/orders/v2")

    def fetch_positions(self, symbol: Optional[str] = None) -> ApiResponse:
        resp = self.make_request("GET", "/positions")
        if isinstance(resp, dict) and resp.get("error"):
            return ApiResponse(success=False, error_message=resp.get("error"), data=resp)

        positions = []
        if isinstance(resp, list):
            raw_positions = resp
        else:
            raw_positions = resp.get("positions") if isinstance(resp, dict) else []

        for item in raw_positions or []:
            info = item.get("position_info") if isinstance(item, dict) else None
            data = info or item
            qty_raw = None
            if isinstance(data, dict):
                qty_raw = data.get("position_size") or data.get("qty")
            try:
                qty = Decimal(str(qty_raw)) if qty_raw is not None else Decimal("0")
            except (InvalidOperation, TypeError, ValueError):
                qty = Decimal("0")

            side = ""
            if isinstance(data, dict):
                side = str(data.get("side") or "").upper()
            if not side:
                side = "LONG" if qty > 0 else "SHORT" if qty < 0 else "FLAT"

            instrument = data.get("instrument") if isinstance(data, dict) else None
            symbol_fmt = self._format_instrument_symbol(instrument)

            mark_price = None
            entry_price = None
            try:
                mp_raw = data.get("mark_price") or data.get("price")
                mark_price = Decimal(str(mp_raw)) if mp_raw is not None else None
            except (InvalidOperation, TypeError, ValueError):
                mark_price = None
            try:
                ep_raw = data.get("avg_entry_price") or data.get("entry_price")
                entry_price = Decimal(str(ep_raw)) if ep_raw is not None else None
            except (InvalidOperation, TypeError, ValueError):
                entry_price = None

            positions.append(
                PositionInfo(
                    symbol=symbol_fmt,
                    side=side,
                    size=abs(qty),
                    entry_price=entry_price,
                    mark_price=mark_price,
                    unrealized_pnl=None,
                    margin=None,
                )
            )
        return ApiResponse(success=True, data=positions or raw_positions)

    def fetch_position_size(self, symbol: str) -> Optional[float]:
        resp = self.fetch_positions(symbol)
        if isinstance(resp, ApiResponse):
            if not resp.success:
                return None
            positions = resp.data
        else:
            positions = resp
        if isinstance(positions, dict):
            positions = positions.get("positions") or positions.get("data") or []
        if not isinstance(positions, list):
            return None
        for pos in positions:
            if isinstance(pos, PositionInfo):
                pos_symbol = pos.symbol
                side = (pos.side or "").upper()
                size_raw = pos.size
            elif isinstance(pos, dict):
                pos_symbol = pos.get("symbol")
                side = str(pos.get("side") or "").upper()
                size_raw = pos.get("size")
            else:
                continue
            if pos_symbol != symbol:
                continue
            try:
                size_val = float(size_raw or 0)
            except (TypeError, ValueError):
                size_val = 0.0
            if side == "SHORT":
                return -abs(size_val)
            if side == "LONG":
                return abs(size_val)
            return 0.0
        return 0.0

    def fetch_trades(self, symbol: Optional[str] = None, limit: int = 50) -> Any:
        return self.make_request("GET", "/transfers", params={"limit": limit})

    def fetch_ticker(self, symbol: Optional[str] = None) -> Any:
        quote = self.request_indicative_quote(qty="1")
        if quote.success:
            return {"last": quote.data.get("price"), "quote_id": quote.data.get("quote_id")}
        return {"error": quote.error_message}

    def fetch_markets(self) -> Any:
        return self.make_request("GET", "/instruments")

    def fetch_l1_orderbook(
        self,
        symbol: Optional[str] = None,
        qty: Decimal = Decimal("0.05"),
        instrument: Optional[Dict[str, Any]] = None,
    ) -> ApiResponse:
        """Fetch Variational L1 quote (single RFQ)

        Variational uses RFQ mode, requiring an active quote request to obtain bid/ask

        Args:
            symbol: Ignored (Variational uses instrument)
            qty: Quote quantity (base)
            instrument: Contract specification
        Returns:
            ApiResponse with data: L1OrderbookInfo
        """
        instrument = self._normalize_instrument(instrument)

        qty_str = self._to_str(qty)
        quote = self.request_indicative_quote(qty_str, instrument=instrument)
        if not quote.success:
            return ApiResponse(
                success=False,
                error_message=f"Failed to fetch quote: {quote.error_message}",
            )

        raw = (quote.data or {}).get("raw") or {}
        bid_price = (quote.data or {}).get("bid")
        ask_price = (quote.data or {}).get("ask")
        if bid_price is None or ask_price is None:
            return ApiResponse(
                success=False,
                error_message="Quote missing bid/ask",
            )
        if not isinstance(bid_price, Decimal):
            bid_price = Decimal(str(bid_price))
        if not isinstance(ask_price, Decimal):
            ask_price = Decimal(str(ask_price))
        qty_raw = raw.get("qty") or qty_str
        qty_decimal = Decimal(str(qty_raw))
        
        mid_price = (bid_price + ask_price) / 2
        spread = ask_price - bid_price
        spread_bps = (spread / mid_price * 10000) if mid_price > 0 else Decimal(0)
        
        # Build symbol
        underlying = instrument.get("underlying", "ETH")
        settlement = instrument.get("settlement_asset", "USDC")
        symbol_str = f"{underlying}/{settlement}"
        
        l1_info = L1OrderbookInfo(
            symbol=symbol_str,
            exchange="variational",
            timestamp=int(time.time() * 1000),
            bid=bid_price,
            ask=ask_price,
            bid_volume=qty_decimal,
            ask_volume=qty_decimal,
            mid=mid_price,
            spread=spread,
            spread_bps=spread_bps,
            mark_price=Decimal(str(raw.get("mark_price"))) if raw.get("mark_price") is not None else None,
            index_price=Decimal(str(raw.get("index_price"))) if raw.get("index_price") is not None else None,
            raw={
                "quote": raw,
                "quote_id": raw.get("quote_id") or (quote.data or {}).get("quote_id"),
                "qty": qty_str,
            }
        )
        
        return ApiResponse(success=True, data=l1_info)

    def parse_error(self, response: Any) -> None:
        """
        Parse Variational-specific error responses

        Called to handle exchange-specific errors in a consistent way.
        Note: Variational uses custom make_request() instead of _request(),
        but we provide this method for architecture consistency.

        Args:
            response: Parsed response from the API (dict or ApiResponse)

        Raises:
            AuthenticationError: For authentication errors
            ExchangeError: For other errors

        Example error responses:
            {"error": "Unauthorized", "status_code": 401}
            {"error": "Invalid request", "status_code": 400}
        """
        from .base.errors import ExchangeError
        
        if response is None:
            return

        # Handle dict responses from make_request()
        if isinstance(response, dict):
            error = response.get("error")
            status_code = response.get("status_code")

            if error is None:
                return  # No error

            feedback = f"{self.id} {error}"

            # Map status codes to exceptions
            if status_code == 401 or status_code == 403:
                raise AuthenticationError(feedback)
            else:
                raise ExchangeError(feedback)

        # Handle ApiResponse dataclass
        if hasattr(response, 'success') and not response.success:
            error_msg = getattr(response, 'error_message', 'Unknown error')
            error_code = getattr(response, 'error_code', None)
            feedback = f"{self.id} {error_code}: {error_msg}" if error_code else f"{self.id} {error_msg}"
            raise ExchangeError(feedback)


# Alias for compatibility
Variational = VariationalClient
variational = VariationalClient
