# -*- coding: utf-8 -*-

"""
Binance Spot Exchange Implementation

Safe Data Access Pattern
- Always use safe_* methods for dictionary access (never direct access)
- safe_string(dict, 'key', default=None) - returns string or None
- safe_integer(dict, 'key') - converts to int safely
- safe_number(dict, 'key') - converts to float safely
- safe_string_2(dict, 'key1', 'key2') - tries key1, then key2
- Graceful handling of missing/null data with built-in type conversion
"""

import hashlib
import logging
from typing import Any, Dict, List, Optional

from .base.exchange import Exchange
from .endpoints.binance import BinanceEndpoints
from .base.errors import (
    ArgumentsRequired,
    AuthenticationError,
    BadRequest,
    BadResponse,
    BadSymbol,
    ExchangeError,
    ExchangeNotAvailable,
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

logger = logging.getLogger(__name__)


class binance(Exchange):
    endpoints = BinanceEndpoints()

    def describe(self) -> Dict[str, Any]:
        return self.deep_extend(
            super(binance, self).describe(),
            {
                "id": "binance",
                "name": "Binance Spot",
                "countries": [],
                "rateLimit": 100,  # conservative default (ms)
                "version": "v3",
                "certified": False,
                "pro": True,  # WebSocket support via exchanges/ws/binance.py
                "has": {
                    "CORS": None,
                    "spot": True,
                    "margin": False,
                    "swap": False,
                    "future": False,
                    "option": False,
                    "cancelAllOrders": True,
                    "cancelOrder": True,
                    "createOrder": True,
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
                    "1w": "1w",
                    "1M": "1M",
                },
                "urls": {
                    "logo": "https://www.binance.com/favicon.ico",
                    "www": "https://www.binance.com",
                    "api": {
                        "public": "https://api.binance.com",
                        "private": "https://api.binance.com",
                    },
                    "doc": "https://binance-docs.github.io/apidocs/spot/en/",
                },
                "fees": {
                    "trading": {
                        "tierBased": True,
                        "percentage": True,
                        "maker": 0.001,  # default 0.1%
                        "taker": 0.001,
                    },
                },
                "precisionMode": TICK_SIZE,
                "api": {
                    "public": {
                        "get": [
                            "api/v3/ping",
                            "api/v3/time",
                            "api/v3/exchangeInfo",
                            "api/v3/depth",
                            "api/v3/trades",
                            "api/v3/aggTrades",
                            "api/v3/klines",
                            "api/v3/avgPrice",
                            "api/v3/ticker/24hr",
                            "api/v3/ticker/price",
                            "api/v3/ticker/bookTicker",
                        ],
                    },
                    "private": {
                        "get": [
                            "api/v3/account",
                            "api/v3/myTrades",
                            "api/v3/order",
                            "api/v3/openOrders",
                            "api/v3/allOrders",
                        ],
                        "post": [
                            "api/v3/order",
                            "api/v3/order/test",
                        ],
                        "delete": [
                            "api/v3/order",
                            "api/v3/openOrders",
                        ],
                    },
                },
                "options": {
                    "recvWindow": 5000,
                    "defaultTimeInForce": "GTC",
                },
                "exceptions": {
                    "exact": {
                        "-1000": OperationFailed,
                        "-1001": NetworkError,
                        "-1002": AuthenticationError,
                        "-1003": RateLimitExceeded,
                        "-1006": BadResponse,
                        "-1007": RequestTimeout,
                        "-1015": RateLimitExceeded,
                        "-1021": InvalidNonce,
                        "-1022": AuthenticationError,
                        "-1100": BadRequest,
                        "-1102": ArgumentsRequired,
                        "-1121": BadSymbol,
                        "-2010": InvalidOrder,
                        "-2011": OrderNotFound,
                        "-2013": OrderNotFound,
                        "-2014": AuthenticationError,
                        "-2015": AuthenticationError,
                        "-2018": InsufficientFunds,
                        "-2019": InsufficientFunds,
                        "-4000": InvalidOrder,
                        "-4001": InvalidOrder,
                        "-4004": InvalidOrder,
                        "-4013": InvalidOrder,
                    },
                    "broad": {
                        "invalid symbol": BadSymbol,
                        "insufficient": InsufficientFunds,
                        "unknown order": OrderNotFound,
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
        api_key = "public" if api == "public" else "private"
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
        response = self._request(self.endpoints.publicGetApiV3ExchangeInfo, params or {})
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
                "price": self.safe_integer(market, "quotePrecision"),
                "amount": self.safe_integer(market, "baseAssetPrecision"),
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
                    "type": "spot",
                    "spot": True,
                    "margin": False,
                    "swap": False,
                    "future": False,
                    "option": False,
                    "active": status == "TRADING",
                    "contract": False,
                    "linear": None,
                    "inverse": None,
                    "contractSize": None,
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
        timestamp = self.safe_integer_2(ticker, "closeTime", "time")
        last = self.safe_string_2(ticker, "lastPrice", "price")
        open_price = self.safe_string(ticker, "openPrice")

        bid = self.safe_string(ticker, "bidPrice")
        ask = self.safe_string(ticker, "askPrice")

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
                "previousClose": self.safe_string(ticker, "prevClosePrice"),
                "change": self.safe_string(ticker, "priceChange"),
                "percentage": self.safe_string(ticker, "priceChangePercent"),
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
        response = self._request(self.endpoints.publicGetApiV3Ticker24hr, self.extend(request, params or {}))
        return self.parse_ticker(response, market)

    def fetch_tickers(
        self, symbols: Optional[List[str]] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.load_markets()
        response = self._request(self.endpoints.publicGetApiV3Ticker24hr, params or {})
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
        response = self._request(self.endpoints.publicGetApiV3Depth, self.extend(request, params or {}))
        timestamp = self.safe_integer(response, "T")
        orderbook = self.parse_order_book(response, market["symbol"], timestamp)
        return orderbook

    def parse_trade(self, trade: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        trade_id = self.safe_string_2(trade, "id", "t")
        order_id = self.safe_string(trade, "orderId")
        market_id = self.safe_string(trade, "symbol")
        symbol = self.safe_symbol(market_id, market)
        timestamp = self.safe_integer_2(trade, "time", "T")
        price = self.safe_string_2(trade, "price", "p")
        amount = self.safe_string_2(trade, "qty", "q")
        cost = self.safe_string(trade, "quoteQty")
        side = None
        if "isBuyer" in trade:
            side = "buy" if trade.get("isBuyer") else "sell"
        taker_or_maker = "maker" if trade.get("isMaker") else "taker" if "isMaker" in trade else None
        fee_cost = self.safe_string(trade, "commission")
        fee_currency = self.safe_currency_code(self.safe_string(trade, "commissionAsset"))
        fee = None
        if fee_cost is not None:
            fee = {"cost": self.parse_number(fee_cost), "currency": fee_currency}
        return {
            "info": trade,
            "id": trade_id,
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
        response = self._request(self.endpoints.publicGetApiV3Trades, self.extend(request, params or {}))
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
        response = self._request(self.endpoints.publicGetApiV3Klines, self.extend(request, params or {}))
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
        response = self._request(self.endpoints.privateGetApiV3Account, params or {})
        result: Dict[str, Any] = {"info": response}
        balances = self.safe_list(response, "balances", [])
        for balance in balances:
            code = self.safe_currency_code(self.safe_string(balance, "asset"))
            free = self.safe_number(balance, "free")
            used = self.safe_number(balance, "locked")
            total = None
            if free is not None or used is not None:
                total = (free or 0) + (used or 0)
            account = {
                "free": free,
                "used": used,
                "total": total,
            }
            result[code] = account
        return self.safe_balance(result)

    def fetch_positions(
        self, symbols: Optional[List[str]] = None, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch positions derived from spot balances.

        For spot exchanges, each non-zero balance is treated as a position.
        Uses the account endpoint (api/v3/account) to retrieve balances.

        Args:
            symbols: Optional list of symbols to filter (e.g. ['BTC']).
                     For spot, the symbol is the asset code itself.
            params: Extra parameters for the request.

        Returns:
            List of position dicts in standardized format.
        """
        response = self._request(self.endpoints.privateGetApiV3Account, params or {})
        balances = self.safe_list(response, "balances", [])

        result = []
        for balance in balances:
            free = self.safe_string(balance, "free")
            locked = self.safe_string(balance, "locked")
            total_str = Precise.string_add(free or "0", locked or "0")
            if total_str is None or total_str == "0" or total_str == "0.0" or total_str == "0.00000000":
                continue
            parsed = self.parse_position(balance)
            result.append(parsed)

        if symbols is not None:
            return self.filter_by_array_positions(result, "symbol", symbols, False)
        return result

    def parse_position(self, balance: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Parse a spot balance entry into a standardized position dict.

        Args:
            balance: Raw balance entry from Binance account response.
            market: Optional market dictionary (unused for spot).

        Returns:
            Position dictionary matching the format used by lighter.py.
        """
        asset = self.safe_string(balance, "asset")
        symbol = self.safe_currency_code(asset)
        free = self.safe_string(balance, "free")
        locked = self.safe_string(balance, "locked")
        total_str = Precise.string_add(free or "0", locked or "0")
        contracts = self.parse_number(total_str)

        side = None
        if contracts is not None and contracts > 0:
            side = "long"

        return {
            "info": balance,
            "id": None,
            "symbol": symbol,
            "contracts": contracts,
            "contractSize": 1,
            "entryPrice": None,
            "markPrice": None,
            "notional": None,
            "leverage": None,
            "unrealizedPnl": None,
            "liquidationPrice": None,
            "collateral": None,
            "marginMode": None,
            "initialMargin": None,
            "maintenanceMargin": None,
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
            "CANCELLED": "canceled",
            "PENDING_CANCEL": "canceled",
            "REJECTED": "rejected",
            "EXPIRED": "expired",
        }
        return self.safe_string(statuses, status, status)

    def parse_order(self, order: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        order_id = self.safe_string(order, "orderId")
        client_order_id = self.safe_string(order, "clientOrderId")
        market_id = self.safe_string(order, "symbol")
        symbol = self.safe_symbol(market_id, market)
        timestamp = self.safe_integer_2(order, "time", "transactTime")
        status = self.parse_order_status(self.safe_string(order, "status"))
        last_trade_timestamp = self.safe_integer(order, "updateTime")
        order_type = self.safe_string_lower(order, "type")
        side = self.safe_string_lower(order, "side")
        price = self.safe_string(order, "price")
        amount = self.safe_string(order, "origQty")
        filled = self.safe_string(order, "executedQty")
        quote_cost = self.safe_string(order, "cummulativeQuoteQty")
        average = None
        if quote_cost is not None and filled is not None and filled not in ("0", "0.0", "0.00", "0.00000000"):
            try:
                average = Precise.string_div(quote_cost, filled)
            except (ValueError, ZeroDivisionError, ArithmeticError):
                average = None
        time_in_force = self.safe_string(order, "timeInForce")
        stop_price = self.safe_string(order, "stopPrice")
        cost = quote_cost
        return self.safe_order(
            {
                "info": order,
                "id": order_id,
                "clientOrderId": client_order_id,
                "timestamp": timestamp,
                "datetime": self.iso8601(timestamp),
                "lastTradeTimestamp": last_trade_timestamp,
                "symbol": symbol,
                "type": order_type,
                "timeInForce": time_in_force,
                "postOnly": None,
                "reduceOnly": None,
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
            time_in_force = self.safe_string(params, "timeInForce", self.options.get("defaultTimeInForce", "GTC"))
            request["timeInForce"] = time_in_force
            params = self.omit(params, "timeInForce")
        if amount is not None:
            request["quantity"] = self.amount_to_precision(symbol, amount)
        client_order_id = self.safe_string(params, "clientOrderId")
        if client_order_id:
            request["newClientOrderId"] = client_order_id
            params = self.omit(params, "clientOrderId")
        response = self._request(self.endpoints.privatePostApiV3Order, self.extend(request, params))
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
        response = self._request(self.endpoints.privateDeleteApiV3Order, self.extend(request, params))
        return self.parse_order(response, market)

    def cancel_all_orders(self, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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

    def fetch_order(self, id: str, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        if symbol is None:
            raise ArgumentsRequired(self.id + " fetch_order() requires a symbol argument")
        self.load_markets()
        market = self.market(symbol)
        request = {"symbol": market["id"], "orderId": id}
        response = self._request(self.endpoints.privateGetApiV3Order, self.extend(request, params))
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
        response = self._request(self.endpoints.privateGetApiV3OpenOrders, self.extend(request, params))
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
        response = self._request(self.endpoints.privateGetApiV3MyTrades, self.extend(request, params))
        return self.parse_trades(response, market, since, limit)

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
        if response is None:
            return
        self.parse_error(response)

    def parse_error(self, response: Any) -> None:
        if response is None:
            return
        code = self.safe_string(response, "code")
        msg = self.safe_string(response, "msg")
        if code is None:
            return
        exceptions = self.exceptions.get("exact", {})
        error_class = exceptions.get(str(code))
        if error_class is None:
            error_class = ExchangeError
        message = self.id + " " + self.json(response)
        raise error_class(message)
