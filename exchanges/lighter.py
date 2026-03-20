# -*- coding: utf-8 -*-

"""
Lighter Exchange Implementation

Lighter is a decentralized trading platform with verifiable order matching.
This implementation uses the official Lighter Python SDK.

Official SDK: https://github.com/elliottech/lighter-python
API Docs: https://apidocs.lighter.xyz
"""

import itertools
import time
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Dict, List, Optional

from .base.exchange import Exchange
from .endpoints.lighter import LighterEndpoints
from .base.errors import (
    ArgumentsRequired,
    AuthenticationError,
    BadRequest,
    ExchangeError,
    ExchangeNotAvailable,
    InsufficientFunds,
    InvalidOrder,
    NetworkError,
    OrderNotFound,
)
from .base.precise import Precise
from .base.decimal_to_precision import TICK_SIZE
from .auth.lighter import SimpleSignerClient


class lighter(Exchange):
    endpoints = LighterEndpoints()
    def describe(self) -> Dict[str, Any]:
        return self.deep_extend(
            super(lighter, self).describe(),
            {
                "id": "lighter",
                "name": "Lighter",
                "countries": ["SG"],
                "rateLimit": 500,  # Conservative rate limit
                "hostname": "lighter.xyz",
                "certified": False,
                "pro": True,  # WebSocket support via api/ws/lighter.py
                "version": "v1",
                "dex": True,  # Lighter is a DEX
                "has": {
                    "CORS": None,
                    "spot": False,
                    "margin": False,
                    "swap": True,
                    "future": False,
                    "option": False,
                    "cancelOrder": True,
                    "cancelAllOrders": True,
                    "createOrder": True,
                    "createOrders": True,
                    "fetchBalance": True,
                    "fetchMarkets": True,
                    "fetchMyTrades": True,
                    "fetchOHLCV": True,
                    "fetchOpenOrders": True,
                    "fetchOrder": True,
                    "fetchOrderBook": True,
                    "fetchPositions": True,
                    "fetchTicker": True,
                    "fetchTickers": True,
                    "fetchTrades": True,
                },
                "timeframes": {
                    "1m": "1m",
                    "5m": "5m",
                    "15m": "15m",
                    "1h": "1h",
                    "4h": "4h",
                    "1d": "1d",
                },
                "urls": {
                    "logo": "https://lighter.xyz/favicon.ico",
                    "www": "https://lighter.xyz",
                    "api": {
                        "public": "https://mainnet.zklighter.elliot.ai",
                        "private": "https://mainnet.zklighter.elliot.ai",
                    },
                    "doc": [
                        "https://docs.lighter.xyz",
                        "https://apidocs.lighter.xyz",
                        "https://github.com/elliottech/lighter-python",
                    ],
                    "fees": "https://docs.lighter.xyz/about-lighter/fees",
                },
                "fees": {
                    "trading": {
                        "tierBased": True,
                        "percentage": True,
                        "maker": 0.0002,  # 0.02%
                        "taker": 0.0005,  # 0.05%
                    },
                },
                "precisionMode": TICK_SIZE,
                "api": {
                    "public": {
                        "get": [
                            "status",
                            "orderbooks",
                            "orderbooks/{market_id}",
                            "orderbooks/{market_id}/details",
                            "markets",
                            "markets/{market_id}",
                            "trades",
                            "trades/{market_id}",
                            "candles",
                            "funding-rates",
                        ],
                    },
                    "private": {
                        "get": [
                            "accounts",
                            "accounts/{account_index}",
                            "orders",
                            "orders/active",
                            "orders/history",
                            "fills",
                            "positions",
                        ],
                        "post": [
                            "orders",
                            "orders/cancel",
                            "orders/cancel-all",
                        ],
                    },
                },
                "options": {
                    "defaultType": "swap",
                    "accountIndex": 0,  # Default account index
                    "apiKeyIndex": 0,  # Default API key index
                    "authTokenTTL": 600,
                    "signerDir": None,
                    "chainId": None,
                },
                "exceptions": {
                    "exact": {
                        "INVALID_SIGNATURE": AuthenticationError,
                        "INVALID_API_KEY": AuthenticationError,
                        "INSUFFICIENT_BALANCE": InsufficientFunds,
                        "ORDER_NOT_FOUND": OrderNotFound,
                        "INVALID_ORDER": InvalidOrder,
                        "MARKET_NOT_FOUND": BadRequest,
                    },
                    "broad": {
                        "insufficient": InsufficientFunds,
                        "not found": OrderNotFound,
                        "invalid": InvalidOrder,
                        "unauthorized": AuthenticationError,
                    },
                },
            },
        )

    def after_construct(self):
        super().after_construct()
        self._signer: Optional[SimpleSignerClient] = None
        self._auth_token: Optional[str] = None
        self._auth_expiry: float = 0.0
        self._client_order_counter = itertools.count(int(time.time() * 1000) % 1_000_000_000)

    # ---- helpers ---------------------------------------------------------
    def _resolve_private_key(self) -> Optional[str]:
        return (
            getattr(self, "privateKey", None)
            or getattr(self, "private_key", None)
            or getattr(self, "secret", None)
            or getattr(self, "apiKey", None)
        )

    def _get_account_index(self, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        params = params or {}
        value = (
            params.get("account_index")
            or params.get("accountIndex")
            or self.options.get("accountIndex")
        )
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _get_api_key_index(self, params: Optional[Dict[str, Any]] = None) -> int:
        params = params or {}
        value = params.get("api_key_index") or params.get("apiKeyIndex") or self.options.get("apiKeyIndex", 0)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _ensure_signer_client(self) -> SimpleSignerClient:
        if self._signer is not None:
            return self._signer

        private_key = self._resolve_private_key()
        account_index = self._get_account_index()
        if not private_key or account_index is None:
            raise AuthenticationError(f"{self.id} requires private_key and account_index for signing")

        signer_dir = self.options.get("signerDir")
        chain_id = self.options.get("chainId")
        signer = SimpleSignerClient(
            base_url=self.urls["api"]["private"],
            private_key=private_key,
            account_index=account_index,
            api_key_index=self._get_api_key_index(),
            session=self.session,
            verify_ssl=self.verify,
            signer_dir=signer_dir,
            chain_id=chain_id,
        )
        mismatch = signer.check_client()
        if mismatch:
            raise AuthenticationError(f"{self.id} signer verification failed: {mismatch}")
        self._signer = signer
        return signer

    def _get_auth_token(self) -> str:
        now = time.time()
        if self._auth_token and now < self._auth_expiry - 5:
            return self._auth_token

        signer = self._ensure_signer_client()
        ttl = int(self.options.get("authTokenTTL") or 600)
        ttl = max(ttl, 120)
        deadline = int(now + ttl)
        token, err = signer.create_auth_token_with_expiry(deadline)
        if err or not token:
            raise AuthenticationError(f"{self.id} failed to create auth token: {err or 'unknown error'}")
        self._auth_token = token
        self._auth_expiry = float(deadline)
        return token

    def _as_int(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _as_bool(self, value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if value in (None, "", "NaN"):
            return None
        if isinstance(value, (int, float, Decimal)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("true", "1", "yes", "y", "t"):
                return True
            if lowered in ("false", "0", "no", "n", "f"):
                return False
        return None

    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def _scale_to_int(self, value: Any, precision: int) -> Optional[int]:
        decimal_value = self._safe_decimal(value)
        if decimal_value is None:
            return None
        factor = Decimal(10) ** int(precision or 0)
        return int((decimal_value * factor).to_integral_value(rounding=ROUND_DOWN))

    def _next_client_order_index(self) -> int:
        return next(self._client_order_counter)

    # ---- Exchange hooks ----------------------------------------------------
    def sign(
        self,
        path: str,
        api: Any = "public",
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        body: Any = None,
    ) -> Dict[str, Any]:
        params = params or {}
        base_url = self.urls["api"]["public" if api == "public" else "private"]
        url = base_url + "/" + path
        headers = headers or {}

        if api != "public":
            auth = self._get_auth_token()
            headers["authorization"] = auth
            params = self.extend({"auth": auth}, params)

        if method in ("GET", "DELETE"):
            if params:
                url += "?" + self.urlencode(params)
        else:
            if params:
                body = self.json(params)
                headers["Content-Type"] = "application/json"

        return {"url": url, "method": method, "body": body, "headers": headers}

    def fetch_markets(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch all available markets from Lighter."""
        response = self._request(self.endpoints.publicGetOrderbooks, params or {})
        details = self.safe_list(response, "order_book_details", [])
        if not details:
            details = self.safe_list(response, "spot_order_book_details", [])
        result = []

        for market in details:
            symbol_raw = self.safe_string(market, "symbol")
            if not symbol_raw:
                continue
            base_id = self.safe_string(market, "base_asset")
            quote_id = self.safe_string(market, "quote_asset")
            if not base_id or not quote_id:
                parts = symbol_raw.replace("/", "_").split("_")
                if len(parts) >= 2:
                    base_id = base_id or parts[0]
                    quote_id = quote_id or parts[1]

            base = self.safe_currency_code(base_id)
            quote = self.safe_currency_code(quote_id)
            symbol = f"{base}/{quote}" if base and quote else symbol_raw.replace("_", "/")

            market_id = self.safe_integer(market, "market_id")
            size_decimals = self.safe_integer(market, "supported_size_decimals", 3)
            price_decimals = self.safe_integer(market, "supported_price_decimals", 3)

            step_size = 1 / (10 ** size_decimals) if size_decimals is not None else None
            tick_size = 1 / (10 ** price_decimals) if price_decimals is not None else None

            status = self.safe_string(market, "status") or "TRADING"

            result.append({
                "id": str(market_id) if market_id is not None else symbol_raw,
                "symbol": symbol,
                "base": base,
                "quote": quote,
                "settle": quote,
                "baseId": base_id,
                "quoteId": quote_id,
                "type": "swap",
                "spot": False,
                "margin": False,
                "swap": True,
                "future": False,
                "option": False,
                "active": status.upper() in ("TRADING", "OPEN"),
                "contract": True,
                "linear": True,
                "inverse": False,
                "contractSize": 1,
                "precision": {
                    "price": price_decimals,
                    "amount": size_decimals,
                },
                "limits": {
                    "price": {"min": tick_size, "max": None},
                    "amount": {"min": step_size, "max": None},
                    "cost": {"min": None, "max": None},
                },
                "info": market,
                "stepSize": step_size,
                "tickSize": tick_size,
            })

        return result

    def fetch_ticker(self, symbol: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch ticker data for a symbol."""
        self.load_markets()
        market = self.market(symbol)
        market_id = market["id"]

        response = self._request(self.endpoints.publicGetOrderbooksMarketIdDetails, params or {})
        details = self.safe_list(response, "order_book_details", [])
        if not details:
            details = self.safe_list(response, "spot_order_book_details", [])
        target = None
        for entry in details:
            try:
                if int(entry.get("market_id")) == int(market_id):
                    target = entry
                    break
            except (TypeError, ValueError):
                continue
        target = target or {}

        return self.parse_ticker(target, market)

    def parse_ticker(self, ticker: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Parse ticker data into standardized format
        
        Args:
            ticker: Raw ticker data from exchange
            market: Market dictionary
            
        Returns:
            Parsed ticker in standardized format
        """
        symbol = self.safe_symbol(None, market)
        timestamp = self.milliseconds()
        
        # Lighter provides best bid/ask
        bid = (
            self.safe_string(ticker, "best_bid")
            or self.safe_string(ticker, "bestBid")
            or self.safe_string(ticker, "bidPrice")
        )
        ask = (
            self.safe_string(ticker, "best_ask")
            or self.safe_string(ticker, "bestAsk")
            or self.safe_string(ticker, "askPrice")
        )
        
        # Calculate mid price
        last = None
        if bid and ask:
            last = Precise.string_div(
                Precise.string_add(bid, ask),
                "2"
            )
        
        return self.safe_ticker({
            "symbol": symbol,
            "timestamp": timestamp,
            "datetime": self.iso8601(timestamp),
            "high": None,
            "low": None,
            "bid": bid,
            "bidVolume": None,
            "ask": ask,
            "askVolume": None,
            "vwap": None,
            "open": None,
            "close": last,
            "last": last,
            "previousClose": None,
            "change": None,
            "percentage": None,
            "average": None,
            "baseVolume": None,
            "quoteVolume": None,
            "info": ticker,
        }, market)

    def fetch_tickers(
        self, symbols: Optional[List[str]] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.load_markets()
        response = self._request(self.endpoints.publicGetOrderbooks, params or {})
        details = self.safe_list(response, "order_book_details", [])
        if not details:
            details = self.safe_list(response, "spot_order_book_details", [])
        result: Dict[str, Any] = {}
        for entry in details:
            market_id = self.safe_string(entry, "market_id")
            market = self.safe_market(market_id, None, None)
            parsed = self.parse_ticker(entry, market)
            if parsed["symbol"] is not None:
                result[parsed["symbol"]] = parsed
        return self.filter_by_array_tickers(result, "symbol", symbols)

    def fetch_order_book(
        self, symbol: str, limit: Optional[int] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.load_markets()
        market = self.market(symbol)
        market_id = market["id"]

        request = {"market_id": market_id}
        if limit is not None:
            request["limit"] = max(1, min(int(limit), 100))
        response = self._request(self.endpoints.publicGetOrderbooksMarketId, self.extend(request, params or {}))

        bids = self.safe_list(response, "bids", [])
        asks = self.safe_list(response, "asks", [])
        timestamp = self.milliseconds()
        return self.parse_order_book(
            {"bids": bids, "asks": asks},
            symbol,
            timestamp,
            "bids",
            "asks",
        )

    def _fetch_account_details(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        account_index = self._get_account_index(params)
        if account_index is None:
            raise ArgumentsRequired(f"{self.id} requires account_index")
        request = {
            "by": "index",
            "value": account_index,
            "api_key_index": self._get_api_key_index(params),
        }
        response = self._request(self.endpoints.privateGetAccountsAccountIndex, self.extend(request, params))
        account = self.safe_dict(response, "account")
        if not account:
            accounts = self.safe_list(response, "accounts", [])
            if accounts:
                account = self.safe_dict(accounts, 0, {})
        return {"account": account, "raw": response}

    def fetch_balance(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch account balance."""
        payload = self._fetch_account_details(params)
        account = payload.get("account") or {}
        result: Dict[str, Any] = {"info": payload.get("raw")}

        available = self.safe_number(account, "available_balance")
        collateral = self.safe_number(account, "collateral")
        if collateral is None:
            collateral = self.safe_number(account, "total_asset_value")
        if available is None:
            available = self.safe_number(account, "availableBalance")

        locked = None
        if available is not None and collateral is not None:
            locked = max(collateral - available, 0)
        total = collateral if collateral is not None else available

        for asset in ("USDC", "USD", "USDT"):
            result[asset] = {
                "free": available,
                "used": locked,
                "total": total,
            }

        return self.safe_balance(result)

    def fetch_positions(
        self, symbols: Optional[List[str]] = None, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        payload = self._fetch_account_details(params)
        account = payload.get("account") or {}
        positions = self.safe_list(account, "positions", [])

        result = []
        for position in positions:
            parsed = self.parse_position(position)
            result.append(parsed)

        return result if symbols is None else self.filter_by_array_positions(result, "symbol", symbols, False)

    def parse_position(self, position: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Parse position data into standardized format
        
        Args:
            position: Raw position data
            market: Market dictionary
            
        Returns:
            Parsed position dictionary
        """
        market_id = self.safe_string(position, "market_id")
        symbol = self.safe_symbol(market_id, market)
        
        position_amt = self.safe_string(position, "position")
        contracts = self.parse_number(position_amt)
        
        side = None
        if contracts is not None:
            side = "long" if contracts > 0 else "short" if contracts < 0 else None
            contracts = abs(contracts)
        
        return {
            "info": position,
            "id": None,
            "symbol": symbol,
            "contracts": contracts,
            "contractSize": 1,
            "entryPrice": self.safe_number(position, "avg_price"),
            "markPrice": None,
            "notional": None,
            "leverage": None,
            "unrealizedPnl": self.safe_number(position, "unrealized_pnl"),
            "liquidationPrice": None,
            "collateral": None,
            "marginMode": "cross",
            "initialMargin": None,
            "maintenanceMargin": None,
            "side": side,
            "percentage": None,
            "timestamp": None,
            "datetime": None,
        }

    def fetch_open_orders(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        params = params or {}
        account_index = self._get_account_index(params)
        if account_index is None:
            raise ArgumentsRequired(f"{self.id} fetch_open_orders() requires account_index")

        request: Dict[str, Any] = {"account_index": account_index}
        market = None
        if symbol is not None:
            self.load_markets()
            market = self.market(symbol)
            request["market_id"] = market["id"]

        response = self._request(self.endpoints.privateGetOrdersActive, self.extend(request, params))
        orders = self.safe_list(response, "orders", [])
        return self.parse_orders(orders, market, since, limit)

    def fetch_order(
        self, id: str, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if symbol is None:
            raise ArgumentsRequired(self.id + " fetch_order() requires a symbol argument")
        orders = self.fetch_open_orders(symbol=symbol, params=params)
        for order in orders:
            if str(order.get("id")) == str(id) or str(order.get("clientOrderId")) == str(id):
                return order
        raise OrderNotFound(f"{self.id} order {id} not found")

    def fetch_trades(
        self, symbol: str, since: Optional[int] = None, limit: Optional[int] = None, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        self.load_markets()
        market = self.market(symbol)
        request = {"market_id": market["id"]}
        if limit is not None:
            request["limit"] = max(1, min(int(limit), 100))
        response = self._request(self.endpoints.publicGetTrades, self.extend(request, params or {}))
        trades = self.safe_list(response, "trades", response if isinstance(response, list) else [])
        return self.parse_trades(trades, market, since, limit)

    def fetch_my_trades(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        params = params or {}
        account_index = self._get_account_index(params)
        if account_index is None:
            raise ArgumentsRequired(f"{self.id} fetch_my_trades() requires account_index")

        request: Dict[str, Any] = {
            "sort_by": "timestamp",
            "sort_dir": "desc",
            "limit": max(1, min(int(limit or 100), 100)),
            "account_index": account_index,
        }
        market = None
        if symbol is not None:
            self.load_markets()
            market = self.market(symbol)
            request["market_id"] = market["id"]

        response = self._request(self.endpoints.privateGetFills, self.extend(request, params))
        trades = self.safe_list(response, "trades", [])
        return self.parse_trades(trades, market, since, limit)

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[int] = None,
        limit: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[List[Any]]:
        self.load_markets()
        market = self.market(symbol)
        resolution = self.timeframes.get(timeframe, timeframe)

        limit = max(1, int(limit or 100))
        now_sec = int(time.time())
        if since is not None:
            start_sec = int(since / 1000)
            end_sec = start_sec + (limit * self.parse_timeframe(timeframe))
        else:
            end_sec = now_sec
            start_sec = end_sec - (limit * self.parse_timeframe(timeframe))

        request = {
            "market_id": market["id"],
            "resolution": resolution,
            "start_timestamp": start_sec,
            "end_timestamp": end_sec,
            "count_back": limit,
        }
        response = self._request(self.endpoints.publicGetCandles, self.extend(request, params or {}))
        candles = self.safe_list(response, "candlesticks", [])
        return self.parse_ohlcvs(candles, market, timeframe, since, limit)

    def parse_ohlcv(self, ohlcv: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> List[Any]:
        ts = self.safe_integer(ohlcv, "timestamp")
        if ts is not None:
            ts *= 1000
        return [
            ts,
            self.safe_number(ohlcv, "open"),
            self.safe_number(ohlcv, "high"),
            self.safe_number(ohlcv, "low"),
            self.safe_number(ohlcv, "close"),
            self.safe_number(ohlcv, "volume0"),
        ]

    def create_orders(self, orders: List[Dict[str, Any]], params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        params = params or {}
        signer = self._ensure_signer_client()
        self.load_markets()

        processed_orders: List[Dict[str, Any]] = []
        for order in orders:
            symbol = order.get("symbol")
            if not symbol:
                continue
            market = self.market(symbol)
            base_precision = int(market.get("precision", {}).get("amount") or 3)
            quote_precision = int(market.get("precision", {}).get("price") or 3)

            order_type_raw = (order.get("type") or "limit").upper()
            order_type_map = {
                "LIMIT": SimpleSignerClient.ORDER_TYPE_LIMIT,
                "MARKET": SimpleSignerClient.ORDER_TYPE_MARKET,
                "STOP": SimpleSignerClient.ORDER_TYPE_STOP_LOSS,
                "STOP_LIMIT": SimpleSignerClient.ORDER_TYPE_STOP_LOSS_LIMIT,
                "TAKE_PROFIT": SimpleSignerClient.ORDER_TYPE_TAKE_PROFIT,
                "TAKE_PROFIT_LIMIT": SimpleSignerClient.ORDER_TYPE_TAKE_PROFIT_LIMIT,
            }
            order_type = order_type_map.get(order_type_raw, SimpleSignerClient.ORDER_TYPE_LIMIT)

            side_raw = str(order.get("side", "")).upper()
            is_ask = side_raw in ("ASK", "SELL", "SELL_SHORT")

            price_value = order.get("price")
            quantity_value = order.get("amount") or order.get("quantity") or order.get("size")
            if quantity_value is None:
                continue

            scaled_price = self._scale_to_int(price_value, quote_precision)
            scaled_quantity = self._scale_to_int(quantity_value, base_precision)
            if scaled_price is None and order_type == SimpleSignerClient.ORDER_TYPE_MARKET:
                book = self.fetch_order_book(symbol, limit=1)
                reference_price = None
                bids = book.get("bids") or []
                asks = book.get("asks") or []
                if is_ask and bids:
                    reference_price = float(bids[0][0]) * 0.999
                elif not is_ask and asks:
                    reference_price = float(asks[0][0]) * 1.001
                if reference_price is not None:
                    scaled_price = self._scale_to_int(reference_price, quote_precision)
            if scaled_price is None or scaled_quantity is None:
                continue

            time_in_force_raw = (order.get("timeInForce") or order.get("time_in_force") or "GTC").upper()
            post_only = bool(order.get("postOnly") or order.get("post_only"))
            if post_only:
                time_in_force = SimpleSignerClient.ORDER_TIME_IN_FORCE_POST_ONLY
            else:
                tif_map = {
                    "GTC": SimpleSignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                    "IOC": SimpleSignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
                    "FOK": SimpleSignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
                    "PO": SimpleSignerClient.ORDER_TIME_IN_FORCE_POST_ONLY,
                    "POST_ONLY": SimpleSignerClient.ORDER_TIME_IN_FORCE_POST_ONLY,
                }
                time_in_force = tif_map.get(time_in_force_raw, SimpleSignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME)
            if order_type == SimpleSignerClient.ORDER_TYPE_MARKET:
                time_in_force = SimpleSignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL

            reduce_only = bool(order.get("reduceOnly") or order.get("reduce_only"))
            trigger_raw = order.get("triggerPrice") or order.get("trigger_price")
            if trigger_raw is None:
                scaled_trigger_price = SimpleSignerClient.NIL_TRIGGER_PRICE
            else:
                scaled_trigger_price = self._scale_to_int(trigger_raw, quote_precision)
                if scaled_trigger_price is None:
                    continue

            expiry_raw = order.get("orderExpiry") or order.get("order_expiry")
            default_expiry = (
                SimpleSignerClient.DEFAULT_IOC_EXPIRY
                if order_type == SimpleSignerClient.ORDER_TYPE_MARKET
                else SimpleSignerClient.DEFAULT_28_DAY_ORDER_EXPIRY
            )
            order_expiry = self._as_int(expiry_raw, default=default_expiry)

            client_order_raw = (
                order.get("clientOrderIndex")
                or order.get("clientOrderId")
                or order.get("client_order_id")
            )
            client_order_index = self._as_int(client_order_raw) or self._next_client_order_index()

            processed_orders.append({
                "market_index": int(market["id"]),
                "client_order_index": int(client_order_index),
                "base_amount": int(scaled_quantity),
                "price": int(scaled_price),
                "is_ask": is_ask,
                "order_type": order_type,
                "time_in_force": time_in_force,
                "reduce_only": reduce_only,
                "trigger_price": int(scaled_trigger_price),
                "order_expiry": int(order_expiry),
                "symbol": symbol,
            })

        if not processed_orders:
            return []

        tx_payloads, tx_response, error = signer.create_order_batch(processed_orders)
        if error:
            raise InvalidOrder(error)
        if not tx_response or tx_response.get("code") != 200:
            message = tx_response.get("message") if tx_response else "unknown error"
            raise InvalidOrder(f"Batch orders rejected: {message}")

        results: List[Dict[str, Any]] = []
        for payload, processed in zip(tx_payloads, processed_orders):
            client_order_index = processed.get("client_order_index")
            results.append({
                "id": str(client_order_index),
                "clientOrderId": str(client_order_index),
                "symbol": processed.get("symbol"),
                "status": "open",
                "info": {"payload": payload, "tx": tx_response},
            })
        return results

    def create_order(
        self,
        symbol: str,
        type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params = params or {}
        signer = self._ensure_signer_client()
        self.load_markets()
        market = self.market(symbol)

        base_precision = int(market.get("precision", {}).get("amount") or 3)
        quote_precision = int(market.get("precision", {}).get("price") or 3)

        order_type_raw = (type or "limit").upper()
        order_type_map = {
            "LIMIT": SimpleSignerClient.ORDER_TYPE_LIMIT,
            "MARKET": SimpleSignerClient.ORDER_TYPE_MARKET,
            "STOP": SimpleSignerClient.ORDER_TYPE_STOP_LOSS,
            "STOP_LIMIT": SimpleSignerClient.ORDER_TYPE_STOP_LOSS_LIMIT,
            "TAKE_PROFIT": SimpleSignerClient.ORDER_TYPE_TAKE_PROFIT,
            "TAKE_PROFIT_LIMIT": SimpleSignerClient.ORDER_TYPE_TAKE_PROFIT_LIMIT,
        }
        order_type = order_type_map.get(order_type_raw, SimpleSignerClient.ORDER_TYPE_LIMIT)

        is_ask = side.lower() in ("sell", "ask", "sell_short", "short")
        price_value = price

        scaled_price = self._scale_to_int(price_value, quote_precision)
        scaled_quantity = self._scale_to_int(amount, base_precision)
        if scaled_price is None and order_type == SimpleSignerClient.ORDER_TYPE_MARKET:
            book = self.fetch_order_book(symbol, limit=1)
            reference_price = None
            bids = book.get("bids") or []
            asks = book.get("asks") or []
            if is_ask and bids:
                reference_price = float(bids[0][0]) * 0.999
            elif not is_ask and asks:
                reference_price = float(asks[0][0]) * 1.001
            if reference_price is not None:
                price_value = reference_price
                scaled_price = self._scale_to_int(reference_price, quote_precision)

        if scaled_price is None or scaled_quantity is None:
            raise InvalidOrder(f"{self.id} invalid price/amount for order")

        time_in_force_raw = (params.get("timeInForce") or params.get("time_in_force") or "GTC").upper()
        post_only = bool(params.get("postOnly") or params.get("post_only"))
        if post_only:
            time_in_force = SimpleSignerClient.ORDER_TIME_IN_FORCE_POST_ONLY
        else:
            tif_map = {
                "GTC": SimpleSignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                "IOC": SimpleSignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
                "FOK": SimpleSignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
                "PO": SimpleSignerClient.ORDER_TIME_IN_FORCE_POST_ONLY,
                "POST_ONLY": SimpleSignerClient.ORDER_TIME_IN_FORCE_POST_ONLY,
            }
            time_in_force = tif_map.get(time_in_force_raw, SimpleSignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME)
        if order_type == SimpleSignerClient.ORDER_TYPE_MARKET:
            time_in_force = SimpleSignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL

        reduce_only = bool(params.get("reduceOnly") or params.get("reduce_only"))

        trigger_raw = params.get("triggerPrice") or params.get("trigger_price")
        if trigger_raw is None:
            scaled_trigger_price = SimpleSignerClient.NIL_TRIGGER_PRICE
        else:
            scaled_trigger_price = self._scale_to_int(trigger_raw, quote_precision)
            if scaled_trigger_price is None:
                raise InvalidOrder(f"{self.id} invalid trigger price")

        expiry_raw = params.get("orderExpiry") or params.get("order_expiry")
        default_expiry = (
            SimpleSignerClient.DEFAULT_IOC_EXPIRY
            if order_type == SimpleSignerClient.ORDER_TYPE_MARKET
            else SimpleSignerClient.DEFAULT_28_DAY_ORDER_EXPIRY
        )
        order_expiry = self._as_int(expiry_raw, default=default_expiry)

        client_order_raw = params.get("clientOrderIndex") or params.get("clientOrderId") or params.get("client_order_id")
        client_order_index = self._as_int(client_order_raw) or self._next_client_order_index()

        tx_payload, tx_response, error = signer.create_order(
            market_index=int(market["id"]),
            client_order_index=int(client_order_index),
            base_amount=int(scaled_quantity),
            price=int(scaled_price),
            is_ask=is_ask,
            order_type=order_type,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            trigger_price=int(scaled_trigger_price),
            order_expiry=int(order_expiry),
        )

        if error:
            raise InvalidOrder(error)
        if not tx_response or tx_response.get("code") != 200:
            message = tx_response.get("message") if tx_response else "unknown error"
            raise InvalidOrder(f"Create order failed: {message}")

        return self.safe_order(
            {
                "id": str(client_order_index),
                "clientOrderId": str(client_order_index),
                "symbol": symbol,
                "type": type,
                "side": side,
                "price": price_value,
                "amount": amount,
                "status": "open",
                "info": {"payload": tx_payload, "tx": tx_response},
            },
            market,
        )

    def cancel_all_orders(self, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None):
        if symbol is None:
            raise ArgumentsRequired(self.id + " cancel_all_orders() requires a symbol argument")
        open_orders = self.fetch_open_orders(symbol=symbol, params=params)
        results = []
        for order in open_orders:
            order_id = order.get("id") or order.get("clientOrderId")
            if order_id is None:
                continue
            try:
                results.append(self.cancel_order(str(order_id), symbol=symbol, params=params))
            except (NetworkError, ExchangeNotAvailable) as exc:
                logger.warning("cancel_order(%s) transient error: %s", order_id, exc)
                continue
            except ExchangeError as exc:
                logger.error("cancel_order(%s) failed: %s", order_id, exc)
                continue
        return results

    def cancel_order(
        self, id: str, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if symbol is None:
            raise ArgumentsRequired(self.id + " cancel_order() requires a symbol argument")
        params = params or {}
        signer = self._ensure_signer_client()
        self.load_markets()
        market = self.market(symbol)

        order_index = self._as_int(id)
        if order_index is None:
            open_orders = self.fetch_open_orders(symbol=symbol, params=params)
            for order in open_orders:
                if str(order.get("id")) == str(id):
                    order_index = self._as_int(order.get("clientOrderId") or order.get("id"))
                    break

        if order_index is None:
            raise OrderNotFound(f"{self.id} cancel_order() unable to resolve order index for {id}")

        tx_payload, tx_response, error = signer.cancel_order(
            market_index=int(market["id"]),
            order_index=int(order_index),
        )

        if error:
            raise InvalidOrder(error)
        if not tx_response or tx_response.get("code") != 200:
            message = tx_response.get("message") if tx_response else "unknown error"
            raise InvalidOrder(f"Cancel order failed: {message}")

        return self.safe_order(
            {
                "id": str(order_index),
                "symbol": symbol,
                "status": "canceled",
                "info": {"payload": tx_payload, "tx": tx_response},
            },
            market,
        )

    def parse_order(self, order: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalized = self._normalize_order_record(order, self.safe_symbol(self.safe_string(order, "market_id"), market))
        symbol = normalized.get("symbol")
        status = self.parse_order_status(normalized.get("status"))
        amount = normalized.get("origQty")
        filled = normalized.get("executedQty")
        remaining = normalized.get("quantity")

        return self.safe_order(
            {
                "info": order,
                "id": normalized.get("id"),
                "clientOrderId": normalized.get("clientOrderId"),
                "timestamp": normalized.get("timestamp"),
                "datetime": self.iso8601(normalized.get("timestamp")) if normalized.get("timestamp") else None,
                "lastTradeTimestamp": None,
                "symbol": symbol,
                "type": (normalized.get("type") or "limit").lower() if normalized.get("type") else None,
                "timeInForce": normalized.get("timeInForce"),
                "postOnly": None,
                "reduceOnly": normalized.get("reduceOnly"),
                "side": "sell" if str(normalized.get("side")).lower() in ("ask", "sell") else "buy",
                "price": normalized.get("price"),
                "stopPrice": normalized.get("triggerPrice"),
                "amount": amount,
                "cost": None,
                "average": None,
                "filled": filled,
                "remaining": remaining,
                "status": status,
                "fee": None,
                "trades": None,
            },
            market,
        )

    def parse_order_status(self, status: Optional[str]) -> Optional[str]:
        if status is None:
            return None
        mapping = {
            "open": "open",
            "new": "open",
            "partially_filled": "open",
            "partial": "open",
            "filled": "closed",
            "cancelled": "canceled",
            "canceled": "canceled",
            "rejected": "rejected",
            "expired": "expired",
        }
        return mapping.get(str(status).lower(), str(status).lower())

    def _normalize_order_record(self, payload: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        order_index = (
            payload.get("order_index")
            if payload.get("order_index") is not None
            else payload.get("orderIndex")
            if payload.get("orderIndex") is not None
            else payload.get("i")
        )
        client_order_index = (
            payload.get("client_order_index")
            if payload.get("client_order_index") is not None
            else payload.get("clientOrderIndex")
            if payload.get("clientOrderIndex") is not None
            else payload.get("u")
        )
        order_id = payload.get("order_id") or payload.get("orderId") or payload.get("id") or order_index
        client_order_id = payload.get("client_order_id") or payload.get("clientOrderId") or client_order_index

        price = self.safe_number(payload, "price")
        if price is None:
            price = self.safe_number(payload, "p")
        if price is None:
            price = self.safe_number(payload, "base_price")

        remaining = self.safe_number(payload, "remaining_base_amount")
        if remaining is None:
            remaining = self.safe_number(payload, "rs")
        initial = self.safe_number(payload, "initial_base_amount")
        if initial is None:
            initial = self.safe_number(payload, "is")
        filled_raw = self.safe_number(payload, "filled_base_amount")
        if filled_raw is None:
            filled_raw = self.safe_number(payload, "fb")

        if remaining is None and initial is not None:
            remaining = max(initial - (filled_raw or 0.0), 0.0)
        if initial is None:
            initial = remaining

        filled_amount = None
        if initial is not None and remaining is not None:
            filled_amount = max(initial - remaining, 0.0)

        trigger_price = self.safe_number(payload, "trigger_price")
        if trigger_price is None:
            trigger_price = self.safe_number(payload, "tp")

        is_ask_raw = payload.get("is_ask")
        if is_ask_raw is None:
            is_ask_raw = payload.get("ia")
        side_raw = payload.get("side")
        is_ask = self._as_bool(is_ask_raw)
        if is_ask is None and side_raw is not None:
            side_upper = str(side_raw).strip().upper()
            if side_upper in ("ASK", "SELL", "SELL_SHORT", "SHORT"):
                is_ask = True
            elif side_upper in ("BID", "BUY", "BUY_LONG", "LONG"):
                is_ask = False
        side = "Ask" if is_ask is True else "Bid" if is_ask is False else side_raw

        status = payload.get("status") if payload.get("status") is not None else payload.get("st")
        order_type = payload.get("type") if payload.get("type") is not None else payload.get("ot")
        time_in_force = payload.get("time_in_force") if payload.get("time_in_force") is not None else payload.get("f")
        reduce_only_raw = payload.get("reduce_only")
        if reduce_only_raw is None:
            reduce_only_raw = payload.get("ro")
        reduce_only = self._as_bool(reduce_only_raw)
        order_expiry = payload.get("order_expiry") if payload.get("order_expiry") is not None else payload.get("e")
        timestamp = payload.get("timestamp") if payload.get("timestamp") is not None else payload.get("t")
        tx_hash = payload.get("tx_hash") if payload.get("tx_hash") is not None else payload.get("txHash")

        return {
            "id": str(order_id) if order_id is not None else None,
            "orderId": str(order_id) if order_id is not None else None,
            "orderIndex": order_index,
            "order_index": order_index,
            "clientOrderId": str(client_order_id) if client_order_id is not None else None,
            "clientOrderIndex": client_order_index,
            "client_order_index": client_order_index,
            "symbol": symbol,
            "price": price,
            "quantity": remaining,
            "remainingQuantity": remaining,
            "origQty": initial,
            "executedQty": filled_amount,
            "status": status,
            "side": side,
            "type": order_type,
            "timeInForce": time_in_force,
            "reduceOnly": reduce_only,
            "triggerPrice": trigger_price,
            "orderExpiry": order_expiry,
            "timestamp": timestamp,
            "txHash": tx_hash,
        }

    def _normalize_trade_record(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        trade_id = trade.get("trade_id") or trade.get("tradeId") or trade.get("id")
        size = self.safe_number(trade, "size")
        price = self.safe_number(trade, "price")
        usd_amount = self.safe_number(trade, "usd_amount")

        ask_account = self._as_int(trade.get("ask_account_id") or trade.get("askAccountId"))
        bid_account = self._as_int(trade.get("bid_account_id") or trade.get("bidAccountId"))

        maker_is_ask_raw = (
            trade.get("is_maker_ask")
            if trade.get("is_maker_ask") is not None
            else trade.get("maker_is_ask")
            if trade.get("maker_is_ask") is not None
            else trade.get("makerIsAsk")
            if trade.get("makerIsAsk") is not None
            else trade.get("maker_side_is_ask")
        )
        maker_is_ask = self._as_bool(maker_is_ask_raw)

        maker_account: Optional[int] = None
        taker_account: Optional[int] = None
        if maker_is_ask is True:
            maker_account = ask_account
            taker_account = bid_account
        elif maker_is_ask is False:
            maker_account = bid_account
            taker_account = ask_account

        account_index = self._get_account_index()
        is_maker: Optional[bool] = None
        if account_index is not None:
            if maker_account is not None and maker_account == int(account_index):
                is_maker = True
            elif taker_account is not None and taker_account == int(account_index):
                is_maker = False

        side: Optional[str] = None
        if is_maker is True:
            side = "Ask" if maker_is_ask is True else "Bid"
        elif is_maker is False:
            side = "Bid" if maker_is_ask is True else "Ask"

        if side is None and account_index is not None:
            if ask_account is not None and ask_account == int(account_index):
                side = "Ask"
            elif bid_account is not None and bid_account == int(account_index):
                side = "Bid"

        if side is None:
            side = "Bid"

        if side == "Bid":
            order_identifier = trade.get("bid_id") or trade.get("order_id")
        elif side == "Ask":
            order_identifier = trade.get("ask_id") or trade.get("order_id")
        else:
            order_identifier = trade.get("order_id") or trade.get("orderId")

        timestamp = trade.get("timestamp") or trade.get("time")

        return {
            "trade_id": str(trade_id) if trade_id is not None else None,
            "order_id": str(order_identifier) if order_identifier is not None else None,
            "market_id": trade.get("market_id"),
            "side": side,
            "size": size,
            "quantity": size,
            "price": price,
            "usd_amount": usd_amount,
            "fee": None,
            "fee_asset": None,
            "is_maker": is_maker,
            "timestamp": timestamp,
            "tx_hash": trade.get("tx_hash"),
        }

    def parse_trade(self, trade: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalized = self._normalize_trade_record(trade)
        market_id = normalized.get("market_id")
        symbol = self.safe_symbol(market_id, market)
        timestamp = self._as_int(normalized.get("timestamp"))
        side = normalized.get("side")
        side = "buy" if str(side).lower() in ("bid", "buy") else "sell"

        return {
            "info": trade,
            "id": normalized.get("trade_id"),
            "order": normalized.get("order_id"),
            "timestamp": timestamp * 1000 if timestamp else None,
            "datetime": self.iso8601(timestamp * 1000) if timestamp else None,
            "symbol": symbol,
            "type": None,
            "side": side,
            "takerOrMaker": "maker" if normalized.get("is_maker") else "taker" if normalized.get("is_maker") is not None else None,
            "price": normalized.get("price"),
            "amount": normalized.get("size"),
            "cost": None,
            "fee": None,
        }

    def handle_errors(
        self,
        statusCode: int,
        statusText: str,
        url: str,
        method: str,
        responseHeaders: Dict[str, Any],
        responseBody: str,
        response: Any,
        requestHeaders: Dict[str, Any],
        requestBody: Any,
    ) -> None:
        """
        Legacy error handler (called by base class fetch())

        This method is kept for backward compatibility.
        The actual error parsing logic has been moved to parse_error().
        """
        if response is None:
            return

        # Delegate to the new parse_error method
        self.parse_error(response)

    def parse_error(self, response: Any) -> None:
        """
        Parse Lighter-specific error responses

        Called automatically by _request() to handle exchange-specific errors.
        This provides the second layer of error handling after HTTP errors.

        Args:
            response: Parsed JSON response from the API

        Raises:
            ExchangeError: For unrecognized errors
            InvalidOrder: For invalid order errors
            InsufficientFunds: For insufficient balance errors
            AuthenticationError: For authentication/signature errors
            OrderNotFound: For order not found errors
            ... (other dext exceptions based on error code)

        Example error responses:
            {"error": "INVALID_SIGNATURE", "message": "Invalid signature"}
            {"error": "INSUFFICIENT_BALANCE", "message": "Not enough balance"}
            {"error": "ORDER_NOT_FOUND", "message": "Order does not exist"}
        """
        if response is None or isinstance(response, str):
            return  # No error or not a valid response

        # Extract error information
        error = self.safe_string(response, "error")
        message = self.safe_string(response, "message")

        if error is None and message is None:
            return  # No error in response

        # Build error feedback message
        feedback = f"{self.id} {self.json(response)}"

        # Try exact match first (error code)
        if error:
            self.throw_exactly_matched_exception(self.exceptions["exact"], error, feedback)

        # Try broad match with message
        if message and "broad" in self.exceptions:
            self.throw_broadly_matched_exception(self.exceptions["broad"], message, feedback)

        # If no match found, raise generic ExchangeError
        raise ExchangeError(feedback)


# Uppercase export for ergonomics
Lighter = lighter
