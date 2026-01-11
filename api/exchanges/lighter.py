"""Lighter exchange client with ccxt-style interface."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..base import (
    Balance,
    Exchange,
    ExchangeError,
    InvalidOrder,
    Market,
    Order,
    OrderBook,
    Ticker,
)
from ..lighter_client import LighterClient
from logger import setup_logger

logger = setup_logger("api.lighter")


class Lighter(Exchange):
    """ccxt-style adapter around the legacy LighterClient."""

    id = "lighter"
    name = "Lighter"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.client = LighterClient(config or {})

    def fetch_markets(self, params: Optional[Dict] = None) -> List[Market]:
        raw = self.client.get_markets()
        if isinstance(raw, dict) and raw.get("error"):
            raise ExchangeError(raw["error"])

        markets: List[Market] = []
        if isinstance(raw, list):
            for item in raw:
                try:
                    market = self._parse_market(item)
                    if market:
                        markets.append(market)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("無法解析市場信息: %s (%s)", item, exc)
        return markets

    def fetch_ticker(self, symbol: str, params: Optional[Dict] = None) -> Ticker:
        raw = self.client.get_ticker(symbol)
        if isinstance(raw, dict) and raw.get("error"):
            raise ExchangeError(raw["error"])

        return Ticker(
            symbol=symbol,
            bid=self._to_float(raw.get("bid_price") or raw.get("bidPrice")),
            ask=self._to_float(raw.get("ask_price") or raw.get("askPrice")),
            last=self._to_float(raw.get("lastPrice") or raw.get("price") or raw.get("last_trade_price")),
            baseVolume=self._to_float(raw.get("baseVolume")),
            quoteVolume=self._to_float(raw.get("quoteVolume")),
            info=raw if isinstance(raw, dict) else {},
        )

    def fetch_order_book(
        self, symbol: str, limit: Optional[int] = None, params: Optional[Dict] = None
    ) -> OrderBook:
        raw = self.client.get_order_book(symbol, limit=limit or 50)
        if isinstance(raw, dict) and raw.get("error"):
            raise ExchangeError(raw["error"])

        return OrderBook(
            symbol=symbol,
            bids=raw.get("bids", []) if isinstance(raw, dict) else [],
            asks=raw.get("asks", []) if isinstance(raw, dict) else [],
            timestamp=raw.get("timestamp") if isinstance(raw, dict) else None,
            info=raw if isinstance(raw, dict) else {},
        )

    def fetch_balance(self, params: Optional[Dict] = None) -> Balance:
        raw = self.client.get_balance()
        if isinstance(raw, dict) and raw.get("error"):
            raise ExchangeError(raw["error"])

        free: Dict[str, float] = {}
        used: Dict[str, float] = {}
        total: Dict[str, float] = {}

        balances = raw.get("balances") if isinstance(raw, dict) else raw
        if isinstance(balances, dict):
            for asset, entry in balances.items():
                if not isinstance(entry, dict):
                    continue
                available = self._to_float(entry.get("available"), 0.0)
                locked = self._to_float(entry.get("locked"), 0.0)
                free[asset] = available or 0.0
                used[asset] = locked or 0.0
                total[asset] = (available or 0.0) + (locked or 0.0)

        return Balance(free=free, used=used, total=total, info=raw if isinstance(raw, dict) else {})

    def create_order(
        self,
        symbol: str,
        type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict] = None,
    ) -> Order:
        payload: Dict[str, Any] = {
            "symbol": symbol,
            "side": "Bid" if side.lower() == "buy" else "Ask",
            "orderType": "LIMIT" if type.lower() == "limit" else "MARKET",
            "quantity": amount,
        }
        if price is not None:
            payload["price"] = price
        if params:
            payload.update(params)

        result = self.client.execute_order(payload)
        if isinstance(result, dict) and result.get("error"):
            raise InvalidOrder(result["error"])
        return self._parse_order(result)

    def cancel_order(self, id: str, symbol: Optional[str] = None, params: Optional[Dict] = None) -> Dict:
        symbol_arg = symbol or params.get("symbol") if params else symbol
        result = self.client.cancel_order(id, symbol_arg or "")
        if isinstance(result, dict) and result.get("error"):
            raise ExchangeError(result["error"])
        return result if isinstance(result, dict) else {"info": result}

    def fetch_open_orders(
        self,
        symbol: Optional[str] = None,
        since: Optional[int] = None,
        limit: Optional[int] = None,
        params: Optional[Dict] = None,
    ) -> List[Order]:
        raw = self.client.get_open_orders(symbol)
        if isinstance(raw, dict) and raw.get("error"):
            raise ExchangeError(raw["error"])

        orders: List[Order] = []
        payload = raw.get("orders") if isinstance(raw, dict) else raw
        if isinstance(payload, list):
            for item in payload:
                try:
                    orders.append(self._parse_order(item))
                except Exception as exc:  # noqa: BLE001
                    logger.debug("無法解析訂單: %s (%s)", item, exc)
        return orders

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _parse_market(self, item: Dict[str, Any]) -> Optional[Market]:
        base = item.get("base_asset") or item.get("baseAsset")
        quote = item.get("quote_asset") or item.get("quoteAsset")
        symbol = item.get("symbol")
        if not base or not quote or not symbol:
            return None

        tick_size = item.get("tick_size")
        min_order_size = item.get("min_order_size")
        precision = {}
        limits: Dict[str, Dict[str, Optional[float]]] = {}
        if tick_size is not None:
            precision["price"] = self._to_float(tick_size)
            limits.setdefault("price", {})["min"] = self._to_float(tick_size)
        if min_order_size is not None:
            precision["amount"] = self._to_float(min_order_size)
            limits.setdefault("amount", {})["min"] = self._to_float(min_order_size)

        return Market(
            id=str(item.get("market_id", symbol)),
            symbol=symbol.replace("_", "/") if "/" not in symbol else symbol,
            base=base,
            quote=quote,
            type="swap",
            spot=False,
            swap=True,
            contract=True,
            linear=True,
            precision=precision,
            limits=limits,
            info=item,
        )

    def _parse_order(self, raw: Any) -> Order:
        if not isinstance(raw, dict):
            raise ExchangeError("無法解析訂單結果")

        order_id = raw.get("orderId") or raw.get("id") or raw.get("clientOrderId") or raw.get("clientId") or ""
        return Order(
            id=str(order_id),
            clientOrderId=str(raw.get("clientOrderId")) if raw.get("clientOrderId") else None,
            symbol=raw.get("symbol"),
            price=self._to_float(raw.get("price")),
            amount=self._to_float(raw.get("quantity") or raw.get("size")),
            filled=self._to_float(raw.get("filled")),
            remaining=self._to_float(raw.get("remaining")),
            side=raw.get("side"),
            type=raw.get("orderType") or raw.get("type"),
            status=raw.get("status"),
            info=raw,
        )

    @staticmethod
    def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
