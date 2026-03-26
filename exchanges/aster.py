# -*- coding: utf-8 -*-

"""
Aster Exchange Implementation

Safe Data Access Pattern
- Always use safe_* methods for dictionary access (never direct access)
- safe_string(dict, 'key', default=None) - returns string or None
- safe_integer(dict, 'key') - converts to int safely
- safe_number(dict, 'key') - converts to float safely
- safe_string_2(dict, 'key1', 'key2') - tries key1, then key2
- Graceful handling of missing/null data with built-in type conversion
"""

import hashlib
from typing import Any, Dict, List, Optional

from .base.exchange import Exchange
from .endpoints.aster import AsterEndpoints
from .base.errors import (
    ArgumentsRequired,
    AuthenticationError,
    BadRequest,
    BadResponse,
    BadSymbol,
    ExchangeError,
    InsufficientFunds,
    InvalidNonce,
    InvalidOrder,
    NetworkError,
    OperationFailed,
    OrderNotFound,
    RateLimitExceeded,
    RequestTimeout,
)
from .base.precise import Precise
from .base.decimal_to_precision import TICK_SIZE


class aster(Exchange):
    endpoints = AsterEndpoints()
    def describe(self) -> Dict[str, Any]:
        return self.deep_extend(
            super(aster, self).describe(),
            {
                "id": "aster",
                "name": "Aster Futures",
                "countries": ["SG"],
                "rateLimit": 333,  # 3 req/s = 333ms
                "hostname": "asterdex.com",
                "certified": False,
                "pro": True,  # WebSocket support via api/ws/aster.py
                "version": "v1",
                "dex": True,  # Aster is a DEX
                "has": {
                    "CORS": None,
                    "spot": False,
                    "margin": False,
                    "swap": True,
                    "future": False,
                    "option": False,
                    "addMargin": False,
                    "cancelAllOrders": False,
                    "cancelOrder": True,
                    "createOrder": True,
                    "fetchBalance": True,
                    "fetchFundingRate": True,
                    "fetchFundingRateHistory": False,
                    "fetchLeverage": "emulated",
                    "fetchMarkets": True,
                    "fetchMyTrades": True,
                    "fetchOHLCV": True,
                    "fetchOpenOrders": True,
                    "fetchOrder": True,
                    "fetchOrderBook": True,
                    "fetchOrders": False,
                    "fetchPositions": True,
                    "fetchTicker": True,
                    "fetchTickers": True,
                    "fetchTrades": True,
                    "setLeverage": True,
                    "setMarginMode": False,
                    "transfer": False,
                },
                "timeframes": {
                    "1m": "1m",
                    "3m": "3m",
                    "5m": "5m",
                    "15m": "15m",
                    "30m": "30m",
                    "1h": "1h",
                    "2h": "2h",
                    "4h": "4h",
                    "6h": "6h",
                    "8h": "8h",
                    "12h": "12h",
                    "1d": "1d",
                },
                "urls": {
                    "logo": "https://github.com/user-attachments/assets/4982201b-73cd-4d7a-8907-e69e239e9609",
                    "www": "https://www.asterdex.com/en",
                    "api": {
                        "fapiPublic": "https://fapi.asterdex.com",
                        "fapiPrivate": "https://fapi.asterdex.com",
                        "sapiPublic": "https://sapi.asterdex.com",
                        "sapiPrivate": "https://sapi.asterdex.com",
                    },
                    "doc": "https://github.com/asterdex/api-docs",
                    "fees": "https://docs.asterdex.com/product/asterex-simple/fees-and-slippage",
                    "referral": {
                        "url": "https://www.asterdex.com/en/referral/aA1c2B",
                        "discount": 0.1,
                    },
                },
                "fees": {
                    "trading": {
                        "tierBased": True,
                        "percentage": True,
                        "maker": 0.0001,  # 0.01%
                        "taker": 0.00035,  # 0.035%
                    },
                },
                "precisionMode": TICK_SIZE,
                "api": {
                    "public": {
                        "get": [
                            "fapi/v1/ping",
                            "fapi/v1/time",
                            "fapi/v1/exchangeInfo",
                            "fapi/v1/depth",
                            "fapi/v1/trades",
                            "fapi/v1/klines",
                            "fapi/v1/ticker/24hr",
                            "fapi/v1/ticker/price",
                            "fapi/v1/premiumIndex",
                            "fapi/v1/fundingRate",
                        ],
                    },
                    "private": {
                        "get": [
                            "fapi/v1/order",
                            "fapi/v1/openOrders",
                            "fapi/v1/allOrders",
                            "fapi/v2/balance",
                            "fapi/v2/positionRisk",
                            "fapi/v1/userTrades",
                        ],
                        "post": [
                            "fapi/v1/order",
                            "fapi/v1/leverage",
                        ],
                        "delete": [
                            "fapi/v1/order",
                            "fapi/v1/allOpenOrders",
                        ],
                    },
                },
                "options": {
                    "recvWindow": 10 * 1000,  # 10 sec default
                    "defaultTimeInForce": "GTC",  # Good Till Cancel
                    "defaultType": "swap",  # Default market type
                    "accountsByType": {
                        "spot": "SPOT",
                        "future": "FUTURE",
                        "linear": "FUTURE",
                        "swap": "FUTURE",
                    },
                    "networks": {
                        "ERC20": "ETH",
                        "BEP20": "BSC",
                        "ARB": "Arbitrum",
                    },
                    "networksToChainId": {
                        "ETH": 1,
                        "BSC": 56,
                        "Arbitrum": 42161,
                    },
                },
                "exceptions": {
                    "exact": {
                        # 10xx - General Server or Network issues
                        "-1000": OperationFailed,  # UNKNOWN
                        "-1001": NetworkError,  # DISCONNECTED
                        "-1002": AuthenticationError,  # UNAUTHORIZED
                        "-1003": RateLimitExceeded,  # TOO_MANY_REQUESTS
                        "-1006": BadResponse,  # UNEXPECTED_RESP
                        "-1007": RequestTimeout,  # TIMEOUT
                        "-1015": RateLimitExceeded,  # TOO_MANY_ORDERS
                        "-1021": InvalidNonce,  # INVALID_TIMESTAMP
                        "-1022": AuthenticationError,  # INVALID_SIGNATURE
                        # 11xx - Request issues
                        "-1100": BadRequest,  # ILLEGAL_CHARS
                        "-1102": ArgumentsRequired,  # MANDATORY_PARAM_EMPTY_OR_MALFORMED
                        "-1121": BadSymbol,  # BAD_SYMBOL
                        # 20xx - Processing Issues
                        "-2010": InvalidOrder,  # NEW_ORDER_REJECTED
                        "-2011": OrderNotFound,  # CANCEL_REJECTED
                        "-2013": OrderNotFound,  # NO_SUCH_ORDER
                        "-2014": AuthenticationError,  # BAD_API_KEY_FMT
                        "-2015": AuthenticationError,  # REJECTED_MBX_KEY
                        "-2018": InsufficientFunds,  # BALANCE_NOT_SUFFICIENT
                        "-2019": InsufficientFunds,  # MARGIN_NOT_SUFFICIENT
                        # 40xx - Filters and validation
                        "-4000": InvalidOrder,  # INVALID_ORDER_STATUS
                        "-4001": InvalidOrder,  # PRICE_LESS_THAN_ZERO
                        "-4004": InvalidOrder,  # QTY_LESS_THAN_MIN_QTY
                        "-4013": InvalidOrder,  # PRICE_LESS_THAN_MIN_PRICE
                    },
                    "broad": {
                        # Pattern matching for error messages
                        "has no position": InvalidOrder,
                        "does not exist": BadSymbol,
                        "Invalid symbol": BadSymbol,
                    },
                },
            },
        )

    def nonce(self) -> int:
        return self.milliseconds()

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
        # Map 'public' -> 'fapiPublic' and 'private' -> 'fapiPrivate'
        api_key = "fapiPublic" if api == "public" else "fapiPrivate"
        base_url = self.urls["api"][api_key]
        url = base_url + "/" + path
        query = None
        headers = headers or {}

        if api == "public":
            if params:
                query = self.urlencode(params)
                url += "?" + query
        else:
            self.check_required_credentials()
            timestamp = self.milliseconds()
            recv_window = self.safe_integer(self.options, "recvWindow", 5000)
            signed_params = {"timestamp": timestamp}
            if recv_window is not None:
                signed_params["recvWindow"] = recv_window
            signed_params = self.extend(signed_params, params)
            query = self.urlencode(signed_params)
            signature = self.hmac(self.encode(query), self.encode(self.secret), hashlib.sha256)
            url += "?" + query + "&signature=" + signature
            headers["X-MBX-APIKEY"] = self.apiKey

        return {"url": url, "method": method, "body": body, "headers": headers}

    def fetch_markets(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        response = self._request(self.endpoints.publicGetFapiV1ExchangeInfo, params or {})
        symbols = self.safe_list(response, "symbols", [])
        result = []
        for market in symbols:
            market_id = self.safe_string(market, "symbol")
            base_id = self.safe_string(market, "baseAsset")
            quote_id = self.safe_string(market, "quoteAsset")
            base = self.safe_currency_code(base_id)
            quote = self.safe_currency_code(quote_id)
            symbol = market_id
            if base and quote:
                symbol = base + "/" + quote
            status = self.safe_string(market, "status")
            filters = self.index_by(self.safe_list(market, "filters", []), "filterType")
            price_filter = self.safe_dict(filters, "PRICE_FILTER", {})
            lot_size = self.safe_dict(filters, "LOT_SIZE", {})
            min_price = self.safe_number(price_filter, "minPrice")
            max_price = self.safe_number(price_filter, "maxPrice")
            tick_size = self.safe_number(price_filter, "tickSize")
            min_qty = self.safe_number(lot_size, "minQty")
            max_qty = self.safe_number(lot_size, "maxQty")
            step_size = self.safe_number(lot_size, "stepSize")
            precision = {
                "price": self.safe_number(market, "pricePrecision"),
                "amount": self.safe_number(market, "quantityPrecision"),
            }
            result.append(
                {
                    "id": market_id,
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
                    "active": status == "TRADING",
                    "contract": True,
                    "linear": True,
                    "inverse": False,
                    "contractSize": 1,
                    "precision": precision,
                    "limits": {
                        "price": {"min": min_price, "max": max_price},
                        "amount": {"min": min_qty, "max": max_qty},
                        "cost": {"min": None, "max": None},
                    },
                    "info": market,
                    "filters": filters,
                    "stepSize": step_size,
                    "tickSize": tick_size,
                }
            )
        return result

    def parse_ticker(self, ticker: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        market_id = self.safe_string(ticker, "symbol")
        symbol = self.safe_symbol(market_id, market)
        timestamp = self.safe_integer(ticker, "closeTime") or self.safe_integer(ticker, "time")
        last = self.safe_string_2(ticker, "lastPrice", "price")
        open_price = self.safe_string(ticker, "openPrice")

        # Add bid/ask prices
        bid = self.safe_string(ticker, "bidPrice")
        ask = self.safe_string(ticker, "askPrice")

        # Calculate VWAP if possible
        base_volume = self.safe_string(ticker, "volume")
        quote_volume = self.safe_string(ticker, "quoteVolume")
        vwap = None
        if quote_volume is not None and base_volume is not None:
            vwap = Precise.string_div(quote_volume, base_volume)

        return self.safe_ticker(
            {
                "symbol": symbol,
                "timestamp": timestamp,
                "datetime": self.iso8601(timestamp),
                "high": self.safe_string(ticker, "highPrice"),
                "low": self.safe_string(ticker, "lowPrice"),
                "bid": bid,
                "bidVolume": self.safe_string(ticker, "bidQty"),
                "ask": ask,
                "askVolume": self.safe_string(ticker, "askQty"),
                "vwap": vwap,
                "open": open_price,
                "close": last,
                "last": last,
                "previousClose": None,
                "change": self.safe_string(ticker, "priceChange"),
                "percentage": self.safe_string(ticker, "priceChangePercent"),
                "average": None,
                "baseVolume": base_volume,
                "quoteVolume": quote_volume,
                "info": ticker,
            },
            market,
        )

    def fetch_ticker(self, symbol: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.load_markets()
        market = self.market(symbol)
        request = {"symbol": market["id"]}
        response = self._request(self.endpoints.publicGetFapiV1Ticker24hr, self.extend(request, params or {}))
        return self.parse_ticker(response, market)

    def fetch_tickers(
        self, symbols: Optional[List[str]] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.load_markets()
        response = self._request(self.endpoints.publicGetFapiV1Ticker24hr, params or {})
        result: Dict[str, Any] = {}
        for ticker in response:
            market_id = self.safe_string(ticker, "symbol")
            market = self.safe_market(market_id, None, None)
            parsed = self.parse_ticker(ticker, market)
            result[parsed["symbol"]] = parsed
        return self.filter_by_array_tickers(result, "symbol", symbols)

    def fetch_order_book(
        self, symbol: str, limit: Optional[int] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.load_markets()
        market = self.market(symbol)
        request = {"symbol": market["id"]}
        if limit is not None:
            request["limit"] = limit
        response = self._request(self.endpoints.publicGetFapiV1Depth, self.extend(request, params or {}))
        timestamp = self.safe_integer(response, "T")
        orderbook = self.parse_order_book(response, market["symbol"], timestamp)
        return orderbook

    def parse_trade(self, trade: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        id = self.safe_string_2(trade, "id", "t")
        order_id = self.safe_string(trade, "orderId")
        market_id = self.safe_string(trade, "symbol")
        symbol = self.safe_symbol(market_id, market)
        timestamp = self.safe_integer_2(trade, "time", "T")
        price = self.safe_string_2(trade, "price", "p")
        amount = self.safe_string_2(trade, "qty", "q")
        cost = self.safe_string(trade, "quoteQty")
        side = None
        if "buyer" in trade:
            side = "buy" if trade.get("buyer") else "sell"
        taker_or_maker = "maker" if trade.get("maker") else "taker" if "maker" in trade else None
        fee_cost = self.safe_string(trade, "commission")
        fee_currency = self.safe_currency_code(self.safe_string(trade, "commissionAsset"))
        fee = None
        if fee_cost is not None:
            fee = {"cost": self.parse_number(fee_cost), "currency": fee_currency}
        return {
            "info": trade,
            "id": id,
            "order": order_id,
            "timestamp": timestamp,
            "datetime": self.iso8601(timestamp),
            "symbol": symbol,
            "type": None,
            "side": side,
            "takerOrMaker": taker_or_maker,
            "price": self.parse_number(price),
            "amount": self.parse_number(amount),
            "cost": self.parse_number(cost),
            "fee": fee,
        }

    def fetch_trades(
        self, symbol: str, since: Optional[int] = None, limit: Optional[int] = None, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        self.load_markets()
        market = self.market(symbol)
        request = {"symbol": market["id"]}
        if limit is not None:
            request["limit"] = limit
        response = self._request(self.endpoints.publicGetFapiV1Trades, self.extend(request, params or {}))
        return self.parse_trades(response, market, since, limit)

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
        request = {"symbol": market["id"], "interval": self.timeframes[timeframe]}
        if limit is not None:
            request["limit"] = limit
        if since is not None:
            request["startTime"] = since
        response = self._request(self.endpoints.publicGetFapiV1Klines, self.extend(request, params or {}))
        return self.parse_ohlcvs(response, market, timeframe, since, limit)

    def parse_ohlcv(self, ohlcv: List[Any], market: Optional[Dict[str, Any]] = None) -> List[Any]:
        return [
            self.safe_integer(ohlcv, 0),
            self.safe_number(ohlcv, 1),
            self.safe_number(ohlcv, 2),
            self.safe_number(ohlcv, 3),
            self.safe_number(ohlcv, 4),
            self.safe_number(ohlcv, 5),
        ]

    def fetch_balance(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = self._request(self.endpoints.privateGetFapiV2Balance, params or {})
        result: Dict[str, Any] = {"info": response}
        for balance in response:
            code = self.safe_currency_code(self.safe_string(balance, "asset"))
            account = {
                "free": self.safe_number(balance, "availableBalance"),
                "used": None,
                "total": self.safe_number(balance, "balance"),
            }
            result[code] = account
        return self.safe_balance(result)

    def fetch_positions(self, symbols: Optional[List[str]] = None, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        response = self._request(self.endpoints.privateGetFapiV2PositionRisk, params or {})
        results = []
        for position in response:
            parsed = self.parse_position(position)
            results.append(parsed)
        return results if symbols is None else self.filter_by_array_positions(results, "symbol", symbols, False)

    def parse_position(self, position: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        market_id = self.safe_string(position, "symbol")
        symbol = self.safe_symbol(market_id, market)
        contracts = self.safe_number(position, "positionAmt")
        entry_price = self.safe_number(position, "entryPrice")
        side = None
        if contracts is not None:
            side = "long" if contracts > 0 else "short" if contracts < 0 else None
            contracts = abs(contracts)
        leverage = self.safe_integer(position, "leverage")
        unrealized = self.safe_number(position, "unRealizedProfit")
        liquidation_price = self.safe_number(position, "liquidationPrice")
        initial_margin = self.safe_number(position, "initialMargin")
        return {
            "info": position,
            "id": None,
            "symbol": symbol,
            "contracts": contracts,
            "contractSize": 1,
            "entryPrice": entry_price,
            "markPrice": self.safe_number(position, "markPrice"),
            "notional": self.safe_number(position, "notional"),
            "leverage": leverage,
            "unrealizedPnl": unrealized,
            "liquidationPrice": liquidation_price,
            "collateral": self.safe_number(position, "isolatedMargin"),
            "marginMode": "cross" if self.safe_string(position, "marginType") == "cross" else "isolated",
            "initialMargin": initial_margin,
            "maintenanceMargin": self.safe_number(position, "maintMargin"),
            "side": side,
            "percentage": None,
            "timestamp": None,
            "datetime": None,
        }

    def parse_order_status(self, status: str) -> Optional[str]:
        statuses = {
            "NEW": "open",
            "PARTIALLY_FILLED": "open",
            "FILLED": "closed",
            "CANCELED": "canceled",
            "EXPIRED": "expired",
            "REJECTED": "rejected",
        }
        return self.safe_string(statuses, status, status)

    def parse_order(self, order: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        id = self.safe_string_2(order, "orderId", "i")
        client_order_id = self.safe_string(order, "clientOrderId")
        market_id = self.safe_string(order, "symbol")
        symbol = self.safe_symbol(market_id, market)
        timestamp = self.safe_integer(order, "time")
        status = self.parse_order_status(self.safe_string(order, "status"))
        last_trade_timestamp = self.safe_integer(order, "updateTime")
        type = self.safe_string_lower(order, "type")
        side = self.safe_string_lower(order, "side")
        price = self.safe_string(order, "price")
        amount = self.safe_string(order, "origQty")
        filled = self.safe_string(order, "executedQty")
        average = self.safe_string(order, "avgPrice")
        reduce_only = self.safe_bool(order, "reduceOnly")
        time_in_force = self.safe_string(order, "timeInForce")
        stop_price = self.safe_string(order, "stopPrice")
        cost = None
        if average is not None and filled is not None:
            cost = Precise.string_mul(average, filled)
        return self.safe_order(
            {
                "info": order,
                "id": id,
                "clientOrderId": client_order_id,
                "timestamp": timestamp,
                "datetime": self.iso8601(timestamp),
                "lastTradeTimestamp": last_trade_timestamp,
                "symbol": symbol,
                "type": type,
                "timeInForce": time_in_force,
                "postOnly": None,
                "reduceOnly": reduce_only,
                "side": side,
                "price": price,
                "stopPrice": stop_price,
                "amount": amount,
                "cost": cost,
                "average": average,
                "filled": filled,
                "remaining": None,
                "status": status,
                "fee": None,
                "trades": None,
            },
            market,
        )

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
        self.load_markets()
        market = self.market(symbol)
        request: Dict[str, Any] = {
            "symbol": market["id"],
            "side": side.upper(),
            "type": type.upper(),
        }
        if type.lower() != "market":
            request["price"] = self.price_to_precision(symbol, price)
            # For limit orders, timeInForce is mandatory on Aster
            time_in_force = self.safe_string(params, "timeInForce", "GTC")
            request["timeInForce"] = time_in_force
            params = self.omit(params, "timeInForce")
        if amount is not None:
            request["quantity"] = self.amount_to_precision(symbol, amount)
        client_order_id = self.safe_string(params, "clientOrderId")
        if client_order_id:
            request["newClientOrderId"] = client_order_id
            params = self.omit(params, "clientOrderId")
        reduce_only = self.safe_value(params, "reduceOnly")
        if reduce_only is not None:
            request["reduceOnly"] = reduce_only
            params = self.omit(params, "reduceOnly")
        response = self._request(self.endpoints.privatePostFapiV1Order, self.extend(request, params))
        return self.parse_order(response, market)

    def cancel_order(
        self, id: str, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        params = params or {}
        if symbol is None:
            raise ArgumentsRequired(self.id + " cancel_order() requires a symbol argument")
        self.load_markets()
        market = self.market(symbol)
        request: Dict[str, Any] = {"symbol": market["id"], "orderId": id}
        client_order_id = self.safe_string(params, "clientOrderId")
        if client_order_id is not None:
            request["origClientOrderId"] = client_order_id
            params = self.omit(params, "clientOrderId")
        response = self._request(self.endpoints.privateDeleteFapiV1Order, self.extend(request, params))
        return self.parse_order(response, market)

    def fetch_order(self, id: str, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        if symbol is None:
            raise ArgumentsRequired(self.id + " fetch_order() requires a symbol argument")
        self.load_markets()
        market = self.market(symbol)
        request = {"symbol": market["id"], "orderId": id}
        response = self._request(self.endpoints.privateGetFapiV1Order, self.extend(request, params))
        return self.parse_order(response, market)

    def fetch_open_orders(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        params = params or {}
        self.load_markets()
        request: Dict[str, Any] = {}
        market = None
        if symbol is not None:
            market = self.market(symbol)
            request["symbol"] = market["id"]
        response = self._request(self.endpoints.privateGetFapiV1OpenOrders, self.extend(request, params))
        return self.parse_orders(response, market, since, limit)

    def fetch_my_trades(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        params = params or {}
        self.load_markets()
        request: Dict[str, Any] = {}
        market = None
        if symbol is not None:
            market = self.market(symbol)
            request["symbol"] = market["id"]
        if limit is not None:
            request["limit"] = limit
        response = self._request(self.endpoints.privateGetFapiV1UserTrades, self.extend(request, params))
        return self.parse_trades(response, market, since, limit)

    def set_leverage(
        self, leverage: int, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Set leverage for a symbol on Aster exchange.

        Args:
            leverage: Leverage multiplier (e.g., 5 for 5x)
            symbol: Trading pair symbol (e.g., 'XAU/USDT')
            params: Additional parameters

        Returns:
            Response from the exchange
        """
        if symbol is None:
            raise ArgumentsRequired(self.id + " set_leverage() requires a symbol argument")
        params = params or {}
        self.load_markets()
        market = self.market(symbol)
        request = {
            "symbol": market["id"],
            "leverage": int(leverage),
        }
        response = self._request(self.endpoints.privatePostFapiV1Leverage, self.extend(request, params))
        return response

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
        Parse Aster-specific error responses

        Called automatically by _request() to handle exchange-specific errors.
        This provides the second layer of error handling after HTTP errors.

        Args:
            response: Parsed JSON response from the API

        Raises:
            ExchangeError: For unrecognized errors
            InvalidOrder: For invalid order errors
            InsufficientFunds: For insufficient balance errors
            AuthenticationError: For authentication errors
            RateLimitExceeded: For rate limit errors
            InvalidNonce: For nonce errors
            OrderNotFound: For order not found errors
            ... (other dext exceptions based on error code)

        Example error responses:
            {"code": "-1000", "msg": "Unknown error"}
            {"code": "-1021", "msg": "Invalid timestamp"}
            {"code": "-2010", "msg": "Insufficient balance"}
        """
        if response is None or isinstance(response, str):
            return  # No error or not a valid response

        # Extract error information (Aster uses 'code' and 'msg'/'message')
        code = self.safe_string(response, "code")
        message = self.safe_string(response, "msg") or self.safe_string(response, "message")

        if code is None and message is None:
            return  # No error in response

        # Build error feedback message
        feedback = f"{self.id} {self.json(response)}"

        # Try exact code matching
        self.throw_exactly_matched_exception(self.exceptions["exact"], code, feedback)

        # Try broad pattern matching on message
        if "broad" in self.exceptions:
            self.throw_broadly_matched_exception(self.exceptions["broad"], message, feedback)

        # If no match found, raise generic ExchangeError
        raise ExchangeError(feedback)


# Uppercase export for ergonomics
Aster = aster
