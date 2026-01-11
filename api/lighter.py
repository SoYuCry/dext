# -*- coding: utf-8 -*-

from __future__ import annotations

import itertools
import math
import time
import os
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import requests

from .base.exchange import Exchange
from .base.errors import (
    ArgumentsRequired,
    BadSymbol,
    ExchangeError,
    InvalidOrder,
    OrderNotFound,
)
from .proxy_utils import get_proxy_config
from .lighter_signer import SimpleSignerClient, SimpleSignerError
from logger import setup_logger

logger = setup_logger("api.lighter")


def _compact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in (data or {}).items() if v is not None}


class lighter(Exchange):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.base_url = (
            config.get("base_url")
            or os.getenv("LIGHTER_BASE_URL")
            or "https://mainnet.zklighter.elliot.ai"
        ).rstrip("/")
        self.verify_ssl = bool(config.get("verify_ssl", True))
        self.timeout = float(config.get("timeout", 10.0) or 10.0)
        super().__init__(config)
        self.session.verify = self.verify_ssl
        self.session.headers.update(
            {
                "User-Agent": "dext-lighter/1.0",
                "Accept": "application/json",
            }
        )

        proxies = get_proxy_config()
        if proxies:
            self.session.proxies.update(proxies)

        overrides = config.get("symbol_overrides") or {}
        self._raw_overrides: Dict[str, Dict[str, Any]] = overrides
        self._market_cache: Dict[str, Dict[str, Any]] = {}
        self._market_id_map: Dict[int, Dict[str, Any]] = {}

        self.account_index: Optional[int] = self._as_int(
            config.get("account_index")
            or config.get("accountIndex")
            or config.get("account_id")
            or config.get("accountId")
        )
        self.api_key_index: int = self._as_int(config.get("api_key_index") or config.get("apiKeyIndex") or 0, default=0)
        self.private_key: Optional[str] = (
            config.get("api_private_key")
            or config.get("private_key")
            or config.get("api_key")
        )
        self.signer_dir: Optional[str] = config.get("signer_lib_dir")
        self.chain_id: Optional[int] = self._as_int(config.get("chain_id"))
        self.auth_token_ttl: int = max(self._as_int(config.get("auth_token_ttl"), default=600) or 600, 120)

        self._signer: Optional[SimpleSignerClient] = None
        self._auth_token: Optional[str] = None
        self._auth_expiry: float = 0.0
        self._client_order_counter = itertools.count(int(time.time() * 1000) % 1_000_000_000)

    def describe(self) -> Dict[str, Any]:
        return self.deep_extend(
            super(lighter, self).describe(),
            {
                "id": "lighter",
                "name": "Lighter",
                "countries": ["SG"],
                "rateLimit": 50,
                "pro": False,
                "has": {
                    "spot": False,
                    "swap": True,
                    "fetchMarkets": True,
                    "fetchTicker": True,
                    "fetchOrderBook": True,
                    "fetchBalance": True,
                    "fetchPositions": True,
                    "fetchOpenOrders": True,
                    "createOrder": True,
                    "cancelOrder": True,
                },
                "urls": {
                    "api": {
                        "public": self.base_url,
                        "private": self.base_url,
                    },
                    "www": "https://lighter.trade",
                },
                "options": {},
            },
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _as_int(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _scale_to_int(self, value: Any, decimals: int) -> Optional[int]:
        decimal_value = self._safe_decimal(value)
        if decimal_value is None:
            return None
        factor = Decimal(10) ** int(decimals)
        return int((decimal_value * factor).to_integral_value())

    def _normalize_symbol_key(self, symbol: str) -> str:
        return symbol.replace("-", "/").upper()

    def _infer_tick_size(self, decimals: Optional[int]) -> str:
        if decimals is None or decimals <= 0:
            return "1"
        return "0." + "0" * (decimals - 1) + "1"

    def _build_market_entry(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        symbol = item.get("symbol")
        if not symbol:
            return None
        key = self._normalize_symbol_key(symbol)
        override = self._raw_overrides.get(symbol) or self._raw_overrides.get(key) or {}

        base_asset = override.get("base_asset") or item.get("base_asset") or symbol
        quote_asset = override.get("quote_asset") or item.get("quote_asset") or "USDC"
        market_type = override.get("market_type") or item.get("market_type") or "PERP"
        status = override.get("status") or item.get("status") or "TRADING"

        base_precision = (
            override.get("base_precision")
            if override.get("base_precision") is not None
            else item.get("size_decimals") or item.get("supported_size_decimals") or 3
        )
        quote_precision = (
            override.get("quote_precision")
            if override.get("quote_precision") is not None
            else item.get("price_decimals") or item.get("supported_price_decimals") or 3
        )

        min_order_size = item.get("min_order_size") or item.get("min_base_amount") or item.get("minQuantity") or "0"
        tick_size = item.get("tick_size") or item.get("tickSize") or item.get("priceIncrement")
        if tick_size is None:
            tick_size = self._infer_tick_size(int(quote_precision))

        market_id = item.get("market_id") or item.get("marketId")
        last_price = item.get("last_price") or item.get("lastPrice")

        return {
            "symbol": symbol,
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "market_type": market_type,
            "status": status,
            "min_order_size": min_order_size,
            "tick_size": str(tick_size),
            "base_precision": base_precision,
            "quote_precision": quote_precision,
            "market_id": market_id,
            "last_price": self.safe_number({"v": last_price}, "v"),
        }

    def _fetch_markets_raw(self) -> List[Dict[str, Any]]:
        payload = self._http_get("/api/v1/orderBookDetails")
        if isinstance(payload, dict) and payload.get("error"):
            logger.error("Failed to fetch Lighter markets: %s", payload["error"])
            return []
        details = payload.get("order_book_details") if isinstance(payload, dict) else None
        if not isinstance(details, list):
            return []
        return [entry for entry in details if isinstance(entry, dict)]

    def _ensure_market_cache(self) -> None:
        if self._market_cache:
            return
        items = self._fetch_markets_raw()
        if not items:
            return
        for item in items:
            entry = self._build_market_entry(item)
            if not entry:
                continue
            key = self._normalize_symbol_key(entry["symbol"])
            self._market_cache[key] = entry
            try:
                market_id_int = int(entry.get("market_id")) if entry.get("market_id") is not None else None
            except (TypeError, ValueError):
                market_id_int = None
            if market_id_int is not None:
                self._market_id_map[market_id_int] = entry

    def _lookup_market(self, symbol: str) -> Optional[Dict[str, Any]]:
        self._ensure_market_cache()
        if not symbol:
            return None
        key = self._normalize_symbol_key(symbol)
        return self._market_cache.get(key)

    def _lookup_market_by_id(self, market_id: Any) -> Optional[Dict[str, Any]]:
        self._ensure_market_cache()
        try:
            mid = int(market_id)
        except (TypeError, ValueError):
            return None
        return self._market_id_map.get(mid)

    def _convert_levels(self, levels: Optional[List[Dict[str, Any]]]) -> List[List[float]]:
        result: List[List[float]] = []
        if not levels:
            return result
        for level in levels:
            if not isinstance(level, dict):
                continue
            price = self.safe_number(level, "price")
            amount = (
                self.safe_number(level, "remaining_base_amount")
                or self.safe_number(level, "initial_base_amount")
                or self.safe_number(level, "size")
                or self.safe_number(level, "quantity")
            )
            if price is None:
                continue
            result.append([price, amount or 0.0])
        return result

    def _resolve_position_symbol(self, payload: Dict[str, Any]) -> Optional[str]:
        market_id = payload.get("market_id")
        symbol = payload.get("symbol")
        market_entry = self._lookup_market_by_id(market_id) if market_id is not None else None
        if market_entry:
            return market_entry.get("symbol") or symbol
        return symbol

    def _convert_position(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        symbol = self._resolve_position_symbol(payload)
        size_value = self.safe_number(payload, "position")
        sign_flag = payload.get("sign")
        if size_value is None:
            size_value = 0
        if sign_flag is not None:
            try:
                if int(sign_flag) < 0:
                    size_value = -abs(size_value)
            except (TypeError, ValueError):
                pass
        size_abs = abs(size_value)
        side = "long" if size_value > 0 else "short" if size_value < 0 else None
        entry_price = self.safe_number(payload, "entry_price")
        mark_price = self.safe_number(payload, "mark_price")
        unrealized = self.safe_number(payload, "unrealized_pnl")
        leverage = self.safe_number(payload, "leverage")
        liquidation_price = self.safe_number(payload, "liquidation_price")
        return {
            "info": payload,
            "symbol": symbol,
            "contracts": size_abs,
            "side": side,
            "entryPrice": entry_price,
            "markPrice": mark_price,
            "unrealizedPnl": unrealized,
            "leverage": leverage,
            "liquidationPrice": liquidation_price,
            "marginMode": None,
        }

    def _next_client_order_index(self) -> int:
        return next(self._client_order_counter)

    # -------------------------------------------------------------------------
    # HTTP / signer helpers
    # -------------------------------------------------------------------------
    def _http_get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=_compact_dict(params or {}), headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            return {"error": str(exc)}
        if response.status_code >= 400:
            return {"error": f"HTTP {response.status_code}: {response.text or response.reason}"}
        if not response.text:
            return {}
        try:
            return response.json()
        except Exception:
            return {"error": "Failed to decode JSON response", "raw": response.text}

    def _ensure_signer_client(self) -> Optional[SimpleSignerClient]:
        if self._signer is not None:
            return self._signer
        if not self.private_key or self.account_index is None:
            return None
        try:
            signer = SimpleSignerClient(
                base_url=self.base_url,
                private_key=self.private_key,
                account_index=int(self.account_index),
                api_key_index=self.api_key_index,
                session=self.session,
                timeout=self.timeout,
                verify_ssl=self.verify_ssl,
                signer_dir=self.signer_dir,
                chain_id=self.chain_id,
            )
        except SimpleSignerError as exc:
            logger.error("Failed to initialise Lighter signer: %s", exc)
            return None
        mismatch = signer.check_client()
        if mismatch:
            logger.error("Signer key verification failed: %s", mismatch)
            return None
        self._signer = signer
        self._auth_token = None
        self._auth_expiry = 0.0
        return signer

    def _get_auth_token(self) -> Optional[str]:
        signer = self._ensure_signer_client()
        if not signer:
            return None
        now = time.time()
        if self._auth_token and now < self._auth_expiry - 5:
            return self._auth_token
        deadline = int(now + self.auth_token_ttl)
        token, error = signer.create_auth_token_with_expiry(deadline)
        if error or not token:
            self._auth_token = None
            return None
        self._auth_token = token
        self._auth_expiry = deadline
        return token

    def _fetch_account_details(self) -> Dict[str, Any]:
        if self.account_index is None:
            return {"error": "Account index is not configured"}
        payload = self._http_get("/api/v1/account", params={"by": "index", "value": str(self.account_index)})
        if isinstance(payload, dict) and "error" in payload:
            return payload
        if isinstance(payload, dict):
            accounts = payload.get("accounts")
            if isinstance(accounts, list) and accounts:
                primary = accounts[0]
                if isinstance(primary, dict):
                    return primary
        return payload

    # -------------------------------------------------------------------------
    # CCXT methods
    # -------------------------------------------------------------------------
    def fetch_markets(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        self._market_cache.clear()
        self._market_id_map.clear()
        self._ensure_market_cache()
        result: List[Dict[str, Any]] = []
        for entry in self._market_cache.values():
            market_id = entry.get("market_id")
            base = entry.get("base_asset")
            quote = entry.get("quote_asset")
            symbol = f"{base}/{quote}"
            price_decimals = self._as_int(entry.get("quote_precision"), default=3) or 3
            amount_decimals = self._as_int(entry.get("base_precision"), default=3) or 3
            tick_size = self.safe_number(entry, "tick_size")
            min_amount = self.safe_number(entry, "min_order_size")
            result.append(
                {
                    "id": str(market_id),
                    "symbol": symbol,
                    "base": base,
                    "quote": quote,
                    "settle": quote,
                    "type": "swap",
                    "spot": False,
                    "margin": False,
                    "swap": True,
                    "future": False,
                    "option": False,
                    "active": (entry.get("status") or "").upper() == "TRADING",
                    "contract": True,
                    "linear": True,
                    "inverse": False,
                    "contractSize": 1,
                    "precision": {
                        "price": 10 ** (-price_decimals),
                        "amount": 10 ** (-amount_decimals),
                    },
                    "limits": {
                        "amount": {"min": min_amount, "max": None},
                        "price": {"min": tick_size, "max": None},
                        "cost": {"min": 10, "max": None},  # enforced in create_order
                    },
                    "info": entry,
                }
            )
        return result

    def fetch_ticker(self, symbol: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.load_markets()
        market = self.market(symbol)
        orderbook = self.fetch_order_book(symbol, 50)
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        best_bid = bids[0][0] if bids else None
        best_ask = asks[0][0] if asks else None
        last = market["info"].get("last_price") if market and market.get("info") else None
        return self.safe_ticker(
            {
                "symbol": market["symbol"],
                "bid": best_bid,
                "ask": best_ask,
                "last": last,
                "info": {"orderbook": orderbook},
            },
            market,
        )

    def fetch_order_book(
        self, symbol: str, limit: Optional[int] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.load_markets()
        market = self.market(symbol)
        market_id = market["id"]
        req_limit = max(1, min(limit or 50, 100))
        response = self._http_get(
            "/api/v1/orderBookOrders",
            params={"market_id": market_id, "limit": req_limit},
        )
        if isinstance(response, dict) and response.get("error"):
            raise ExchangeError(response["error"])
        bids = self._convert_levels(response.get("bids") if isinstance(response, dict) else None)
        asks = self._convert_levels(response.get("asks") if isinstance(response, dict) else None)
        return self.parse_order_book(
            {"bids": bids, "asks": asks},
            market["symbol"],
            None,
            "bids",
            "asks",
            0,
            1,
        )

    def fetch_balance(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        account = self._fetch_account_details()
        if isinstance(account, dict) and account.get("error"):
            raise ExchangeError(account["error"])
        available = self.safe_number(account, "available_balance") or 0.0
        collateral = self.safe_number(account, "collateral") or 0.0
        locked = max(collateral - available, 0.0)
        total = available + locked
        result = {
            "info": account,
            "USDC": {"free": available, "used": locked, "total": total},
        }
        return self.safe_balance(result)

    def fetch_positions(self, symbols: Optional[List[str]] = None, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        account = self._fetch_account_details()
        if isinstance(account, dict) and account.get("error"):
            raise ExchangeError(account["error"])
        positions = account.get("positions", []) if isinstance(account, dict) else []
        results: List[Dict[str, Any]] = []
        for position in positions:
            if not isinstance(position, dict):
                continue
            parsed = self._convert_position(position)
            if symbols is None or parsed["symbol"] in symbols:
                results.append(parsed)
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
        self.load_markets()
        market = self.market(symbol)
        market_info = market.get("info") or {}
        market_id = market.get("id")
        if market_id is None:
            raise BadSymbol(f"{self.id} missing market id for {symbol}")

        signer = self._ensure_signer_client()
        if not signer:
            raise ExchangeError("Signer client is not configured")

        base_precision = int(market_info.get("base_precision", 3))
        quote_precision = int(market_info.get("quote_precision", 3))
        min_order_size = float(market_info.get("min_order_size") or 0)

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

        is_ask = side.upper() in ("ASK", "SELL", "SELL_SHORT")

        scaled_price = self._scale_to_int(price, quote_precision) if price is not None else None
        scaled_quantity = self._scale_to_int(amount, base_precision)
        if scaled_quantity is None:
            raise InvalidOrder("Invalid quantity")

        if scaled_price is None:
            if order_type == SimpleSignerClient.ORDER_TYPE_MARKET:
                book = self.fetch_order_book(symbol, 1)
                reference_price = None
                bids = book.get("bids") or []
                asks = book.get("asks") or []
                if is_ask and bids:
                    reference_price = float(bids[0][0]) * 0.999
                elif not is_ask and asks:
                    reference_price = float(asks[0][0]) * 1.001
                reference_price = reference_price or market_info.get("last_price")
                if reference_price is None:
                    raise InvalidOrder("Market price unavailable for market order")
                scaled_price = self._scale_to_int(reference_price, quote_precision)
            else:
                raise InvalidOrder("Price is required for limit orders")

        quantity_float = float(amount)
        price_float = float(price) if price is not None else None
        if price_float is None and scaled_price is not None:
            price_float = float(scaled_price) / (10 ** quote_precision)
        effective_price = price_float or 0.0
        min_quote_value = 10.0
        required_base = math.ceil((min_quote_value / effective_price) * (10 ** base_precision)) / (10 ** base_precision) if effective_price else 0
        effective_min_quantity = max(min_order_size, required_base)
        if quantity_float < effective_min_quantity:
            raise InvalidOrder(f"Quantity {quantity_float} below minimum {effective_min_quantity}")

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
            }
            time_in_force = tif_map.get(time_in_force_raw, SimpleSignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME)
        if order_type == SimpleSignerClient.ORDER_TYPE_MARKET:
            time_in_force = SimpleSignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL

        reduce_only = bool(params.get("reduceOnly") or params.get("reduce_only"))
        trigger_price_raw = params.get("triggerPrice") or params.get("trigger_price")
        scaled_trigger_price = (
            self._scale_to_int(trigger_price_raw, quote_precision) if trigger_price_raw is not None else SimpleSignerClient.NIL_TRIGGER_PRICE
        )
        expiry_raw = params.get("orderExpiry") or params.get("order_expiry")
        default_expiry = (
            SimpleSignerClient.DEFAULT_IOC_EXPIRY
            if order_type == SimpleSignerClient.ORDER_TYPE_MARKET
            else SimpleSignerClient.DEFAULT_28_DAY_ORDER_EXPIRY
        )
        order_expiry = self._as_int(expiry_raw, default=default_expiry)

        client_order_index = self._as_int(
            params.get("clientOrderIndex")
            or params.get("clientOrderId")
            or params.get("client_order_id")
        )
        if client_order_index is None:
            client_order_index = self._next_client_order_index()

        tx_payload, tx_response, error = signer.create_order(
            market_index=int(market_id),
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
            message = tx_response.get("message") if isinstance(tx_response, dict) else "unknown error"
            raise InvalidOrder(f"Order rejected: {message}")

        return {
            "id": str(client_order_index),
            "clientOrderId": client_order_index,
            "symbol": market["symbol"],
            "side": "sell" if is_ask else "buy",
            "type": type,
            "price": price,
            "amount": amount,
            "info": {
                "txHash": tx_response.get("tx_hash") if isinstance(tx_response, dict) else None,
                "payload": tx_payload,
            },
            "status": "open",
        }

    def cancel_order(self, id: str, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        if symbol is None:
            raise ArgumentsRequired(self.id + " cancel_order() requires a symbol argument")
        self.load_markets()
        market = self.market(symbol)
        market_id = market.get("id")
        signer = self._ensure_signer_client()
        if not signer:
            raise ExchangeError("Signer client is not configured")
        order_index = self._as_int(id)
        if order_index is None:
            raise InvalidOrder("Invalid order id")
        tx_payload, tx_response, error = signer.cancel_order(
            market_index=int(market_id),
            order_index=order_index,
        )
        if error:
            raise OrderNotFound(error)
        if not tx_response or tx_response.get("code") != 200:
            message = tx_response.get("message") if isinstance(tx_response, dict) else "unknown error"
            raise OrderNotFound(f"Cancel rejected: {message}")
        return {
            "id": id,
            "symbol": market["symbol"],
            "info": {
                "txHash": tx_response.get("tx_hash") if isinstance(tx_response, dict) else None,
                "payload": tx_payload,
            },
            "status": "canceled",
        }

    def fetch_open_orders(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        params = params or {}
        if symbol is None:
            raise ArgumentsRequired(self.id + " fetch_open_orders() requires a symbol argument")
        self.load_markets()
        market = self.market(symbol)
        market_id = market.get("id")
        if self.account_index is None:
            raise ExchangeError("Account index is not configured")
        auth = self._get_auth_token()
        if auth is None:
            raise ExchangeError("Unable to generate auth token")
        payload = self._http_get(
            "/api/v1/accountActiveOrders",
            params={"account_index": int(self.account_index), "market_id": int(market_id), "auth": auth},
            headers={"authorization": auth},
        )
        if isinstance(payload, dict) and payload.get("error"):
            raise ExchangeError(payload["error"])
        orders = payload.get("orders") if isinstance(payload, dict) else []
        results: List[Dict[str, Any]] = []
        for order in orders or []:
            if not isinstance(order, dict):
                continue
            parsed = self.parse_order(order, market)
            results.append(parsed)
        return results

    def parse_order(self, order: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        market_id = order.get("market_id")
        symbol = market["symbol"] if market else self.safe_symbol(market_id, market)
        order_id = order.get("order_id") or order.get("orderIndex") or order.get("client_order_index") or order.get("id")
        side = "sell" if order.get("is_ask") else "buy"
        price = self.safe_number(order, "price")
        amount = self.safe_number(order, "original_quantity")
        remaining = self.safe_number(order, "remaining_quantity") or self.safe_number(order, "remainingQuantity")
        filled = None
        if amount is not None and remaining is not None:
            filled = amount - remaining
        status = order.get("status") or order.get("order_status")
        return self.safe_order(
            {
                "id": str(order_id) if order_id is not None else None,
                "clientOrderId": order.get("client_order_index"),
                "timestamp": None,
                "datetime": None,
                "symbol": symbol,
                "type": None,
                "side": side,
                "price": price,
                "amount": amount,
                "filled": filled,
                "remaining": remaining,
                "status": status,
                "info": order,
            },
            market,
        )


# Uppercase alias
Lighter = lighter
