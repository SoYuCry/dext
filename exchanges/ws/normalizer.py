"""WebSocket data normalizers.

Convert exchange-specific WS payloads into unified dataclasses.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from exchanges.logger import setup_logger

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

logger = setup_logger("ws.normalizer")

NormalizedOrders = Union[OrderUpdate, List[OrderUpdate], None]


class Normalizer(ABC):
    """Base normalizer for exchange WS events."""

    def __init__(self, exchange_name: str) -> None:
        self.exchange_name = (exchange_name or "").lower()

    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def to_decimal(value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (TypeError, ValueError, ArithmeticError):
            return None

    @abstractmethod
    def normalize_symbol(self, raw_symbol: str, *, market_index: Optional[int] = None) -> str:
        """Return canonical symbol (e.g., ETH/USDC)."""

    @abstractmethod
    def normalize_order_status(self, raw_status: str) -> OrderStatus:
        """Return canonical order status."""

    @abstractmethod
    def normalize_bbo(self, raw_event: Dict[str, Any]) -> Optional[BBOUpdate]:
        """Normalize best-bid-offer events."""

    @abstractmethod
    def normalize_order(self, raw_event: Dict[str, Any]) -> NormalizedOrders:
        """Normalize order updates / fills."""


class LighterNormalizer(Normalizer):
    """Lighter WS normalizer."""

    def __init__(self, market_index_to_symbol: Optional[Dict[int, str]] = None) -> None:
        super().__init__("lighter")
        self.market_index_to_symbol = market_index_to_symbol or {}

    def normalize_symbol(self, raw_symbol: str, *, market_index: Optional[int] = None) -> str:
        if market_index is not None:
            mapped = self.market_index_to_symbol.get(int(market_index))
            if mapped:
                return mapped
        symbol = raw_symbol or ""
        if symbol.startswith("MARKET_"):
            try:
                market_id = int(symbol.split("_", 1)[1])
            except (ValueError, IndexError):
                market_id = None
            if market_id is not None:
                mapped = self.market_index_to_symbol.get(market_id)
                if mapped:
                    return mapped
        if "_" in symbol and "/" not in symbol:
            return symbol.replace("_", "/")
        return symbol or "UNKNOWN"

    def normalize_order_status(self, raw_status: str) -> OrderStatus:
        status = (raw_status or "").lower()
        mapping = {
            "open": OrderStatus.OPEN,
            "new": OrderStatus.OPEN,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "partial": OrderStatus.PARTIALLY_FILLED,
            "filled": OrderStatus.FILLED,
            "cancelled": OrderStatus.CANCELLED,
            "canceled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
            "expired": OrderStatus.EXPIRED,
        }
        return mapping.get(status, OrderStatus.OPEN)

    def normalize_bbo(self, raw_event: Dict[str, Any]) -> Optional[BBOUpdate]:
        bids = raw_event.get("bids") or []
        asks = raw_event.get("asks") or []

        best_bid = raw_event.get("best_bid")
        best_ask = raw_event.get("best_ask")
        if best_bid is None and bids:
            try:
                best_bid = bids[0][0]
            except (IndexError, TypeError, KeyError):
                best_bid = None
        if best_ask is None and asks:
            try:
                best_ask = asks[0][0]
            except (IndexError, TypeError, KeyError):
                best_ask = None

        if best_bid is None or best_ask is None:
            return None

        bid_size = raw_event.get("best_bid_size")
        ask_size = raw_event.get("best_ask_size")
        if bid_size is None and bids:
            try:
                bid_size = bids[0][1]
            except (IndexError, TypeError, KeyError):
                bid_size = 0
        if ask_size is None and asks:
            try:
                ask_size = asks[0][1]
            except (IndexError, TypeError, KeyError):
                ask_size = 0

        market_index = raw_event.get("market_index")
        symbol_raw = raw_event.get("symbol") or ""
        symbol = self.normalize_symbol(symbol_raw, market_index=market_index)

        ts_local = int(raw_event.get("ts_local") or self.now_ms())
        ts_exchange = int(raw_event.get("ts_exchange") or ts_local)
        last_price = raw_event.get("last_price")

        return BBOUpdate(
            exchange=self.exchange_name,
            symbol=symbol,
            data=BBOData(
                bid=self.to_decimal(best_bid) or Decimal(0),
                ask=self.to_decimal(best_ask) or Decimal(0),
                bid_size=self.to_decimal(bid_size) or Decimal(0),
                ask_size=self.to_decimal(ask_size) or Decimal(0),
                last_price=self.to_decimal(last_price),
            ),
            metadata=EventMetadata(
                ts_exchange=ts_exchange,
                ts_local=ts_local,
                event_type=EventType.BBO_UPDATE,
            ),
            raw=raw_event.get("raw"),
        )

    def _derive_fill_fields(self, order: Dict[str, Any]) -> Dict[str, Any]:
        base = order.get("filled_base_amount")
        quote = order.get("filled_quote_amount")
        if base is None or quote is None:
            return {}
        try:
            filled_amount = Decimal(str(base))
            if filled_amount == 0:
                return {}
            fill_price = Decimal(str(quote)) / filled_amount
        except (TypeError, ValueError, ArithmeticError):
            return {}
        return {
            "fill_price": fill_price,
            "filled_amount": filled_amount,
        }

    def normalize_order(self, raw_event: Dict[str, Any]) -> NormalizedOrders:
        orders = raw_event.get("orders") or []
        if not isinstance(orders, list) or not orders:
            return None

        updates: List[OrderUpdate] = []
        market_index = raw_event.get("market_index")
        symbol_raw = raw_event.get("symbol") or ""
        symbol = self.normalize_symbol(symbol_raw, market_index=market_index)
        ts_local = int(raw_event.get("ts_local") or self.now_ms())
        ts_exchange = int(raw_event.get("ts_exchange") or ts_local)

        for order in orders:
            if not isinstance(order, dict):
                continue
            order_id = order.get("order_index") or order.get("client_order_index")
            if order_id is None:
                continue
            client_order_id = order.get("client_order_index")
            status = self.normalize_order_status(order.get("status", "open"))

            is_ask = bool(order.get("is_ask"))
            side = OrderSide.SELL if is_ask else OrderSide.BUY

            amount = self.to_decimal(order.get("initial_base_amount"))
            if amount is None:
                amount = self.to_decimal(order.get("amount")) or Decimal(0)
            filled = self.to_decimal(order.get("filled_base_amount")) or Decimal(0)
            remaining = self.to_decimal(order.get("remaining_base_amount"))
            if remaining is None:
                remaining = max(Decimal(0), (amount or Decimal(0)) - filled)

            fill_price = self.to_decimal(order.get("fill_price"))
            filled_amount = self.to_decimal(order.get("filled_amount"))
            if fill_price is None or filled_amount is None:
                derived = self._derive_fill_fields(order)
                fill_price = fill_price or derived.get("fill_price")
                filled_amount = filled_amount or derived.get("filled_amount")

            event_type = EventType.ORDER_UPDATE
            if status == OrderStatus.FILLED or filled_amount:
                event_type = EventType.FILL_UPDATE

            updates.append(
                OrderUpdate(
                    exchange=self.exchange_name,
                    symbol=symbol,
                    data=OrderData(
                        order_id=str(order_id),
                        client_order_id=str(client_order_id) if client_order_id is not None else None,
                        status=status,
                        side=side,
                        price=self.to_decimal(order.get("price")),
                        amount=amount or Decimal(0),
                        filled=filled,
                        remaining=remaining,
                        fill_price=fill_price,
                        filled_amount=filled_amount,
                    ),
                    metadata=EventMetadata(
                        ts_exchange=ts_exchange,
                        ts_local=ts_local,
                        event_type=event_type,
                    ),
                    raw=raw_event.get("raw") or order,
                )
            )

        return updates or None


class BackpackNormalizer(Normalizer):
    """Backpack WS normalizer."""

    def __init__(self) -> None:
        super().__init__("backpack")

    def normalize_symbol(self, raw_symbol: str, *, market_index: Optional[int] = None) -> str:
        symbol = raw_symbol or ""
        if "_" in symbol and "/" not in symbol:
            return symbol.replace("_", "/")
        return symbol or "UNKNOWN"

    def normalize_order_status(self, raw_status: str) -> OrderStatus:
        status = (raw_status or "").lower()
        mapping = {
            "new": OrderStatus.OPEN,
            "open": OrderStatus.OPEN,
            "partiallyfilled": OrderStatus.PARTIALLY_FILLED,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "filled": OrderStatus.FILLED,
            "cancelled": OrderStatus.CANCELLED,
            "canceled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
            "expired": OrderStatus.EXPIRED,
        }
        return mapping.get(status, OrderStatus.OPEN)

    def normalize_bbo(self, raw_event: Dict[str, Any]) -> Optional[BBOUpdate]:
        bids = raw_event.get("bids") or []
        asks = raw_event.get("asks") or []
        if not bids or not asks:
            return None
        try:
            best_bid = bids[0][0]
            best_ask = asks[0][0]
        except (IndexError, TypeError, KeyError):
            return None
        bid_size = bids[0][1] if len(bids[0]) > 1 else 0
        ask_size = asks[0][1] if len(asks[0]) > 1 else 0

        raw_data = raw_event.get("raw") or {}
        last_price = raw_data.get("c") or raw_data.get("lastPrice")

        symbol = self.normalize_symbol(raw_event.get("symbol", ""))
        ts_local = int(raw_event.get("ts_local") or self.now_ms())
        ts_exchange = int(raw_event.get("ts_exchange") or ts_local)

        return BBOUpdate(
            exchange=self.exchange_name,
            symbol=symbol,
            data=BBOData(
                bid=self.to_decimal(best_bid) or Decimal(0),
                ask=self.to_decimal(best_ask) or Decimal(0),
                bid_size=self.to_decimal(bid_size) or Decimal(0),
                ask_size=self.to_decimal(ask_size) or Decimal(0),
                last_price=self.to_decimal(last_price),
            ),
            metadata=EventMetadata(
                ts_exchange=ts_exchange,
                ts_local=ts_local,
                event_type=EventType.BBO_UPDATE,
            ),
            raw=raw_data,
        )

    def normalize_order(self, raw_event: Dict[str, Any]) -> NormalizedOrders:
        order_id = raw_event.get("order_id") or raw_event.get("trade_id")
        if not order_id:
            return None

        status = self.normalize_order_status(raw_event.get("status", "new"))
        side_raw = str(raw_event.get("side", "")).lower()
        side = OrderSide.BUY if side_raw == "buy" else OrderSide.SELL

        amount = self.to_decimal(raw_event.get("orig_qty")) or Decimal(0)
        filled = self.to_decimal(raw_event.get("filled_qty")) or Decimal(0)
        remaining = max(Decimal(0), amount - filled)

        event_type = EventType.ORDER_UPDATE
        if raw_event.get("event_type") == "FILL_UPDATE":
            event_type = EventType.FILL_UPDATE

        fill_price = self.to_decimal(raw_event.get("last_price"))
        filled_amount = self.to_decimal(raw_event.get("last_qty"))

        symbol = self.normalize_symbol(raw_event.get("symbol", ""))
        ts_local = int(raw_event.get("ts_local") or self.now_ms())
        ts_exchange = int(raw_event.get("ts_exchange") or ts_local)

        return OrderUpdate(
            exchange=self.exchange_name,
            symbol=symbol,
            data=OrderData(
                order_id=str(order_id),
                client_order_id=raw_event.get("client_order_id"),
                status=status,
                side=side,
                price=self.to_decimal(raw_event.get("price")),
                amount=amount,
                filled=filled,
                remaining=remaining,
                fill_price=fill_price,
                filled_amount=filled_amount,
            ),
            metadata=EventMetadata(
                ts_exchange=ts_exchange,
                ts_local=ts_local,
                event_type=event_type,
            ),
            raw=raw_event.get("raw"),
        )


class BinanceNormalizer(Normalizer):
    """Binance WS normalizer."""

    _QUOTE_ASSETS = (
        "USDT",
        "USDC",
        "BUSD",
        "FDUSD",
        "TUSD",
        "USDP",
        "USD",
        "BTC",
        "ETH",
        "BNB",
        "EUR",
        "GBP",
        "TRY",
        "BRL",
        "AUD",
        "CAD",
        "JPY",
        "KRW",
        "RUB",
        "IDR",
        "NGN",
        "ZAR",
        "UAH",
        "DAI",
        "PAX",
        "PAXG",
    )

    def __init__(self) -> None:
        super().__init__("binance")

    def normalize_symbol(self, raw_symbol: str, *, market_index: Optional[int] = None) -> str:
        symbol = (raw_symbol or "").upper()
        if "/" in symbol:
            return symbol
        if "_" in symbol:
            return symbol.replace("_", "/")
        for quote in self._QUOTE_ASSETS:
            if symbol.endswith(quote) and len(symbol) > len(quote):
                base = symbol[: -len(quote)]
                return f"{base}/{quote}"
        return symbol or "UNKNOWN"

    def normalize_order_status(self, raw_status: str) -> OrderStatus:
        status = (raw_status or "").upper()
        mapping = {
            "NEW": OrderStatus.OPEN,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "CANCELLED": OrderStatus.CANCELLED,
            "PENDING_CANCEL": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED,
        }
        return mapping.get(status, OrderStatus.OPEN)

    def normalize_bbo(self, raw_event: Dict[str, Any]) -> Optional[BBOUpdate]:
        bids = raw_event.get("bids") or []
        asks = raw_event.get("asks") or []
        if not bids or not asks:
            return None
        try:
            best_bid = bids[0][0]
            best_ask = asks[0][0]
        except (IndexError, TypeError, KeyError):
            return None
        bid_size = bids[0][1] if len(bids[0]) > 1 else 0
        ask_size = asks[0][1] if len(asks[0]) > 1 else 0

        raw_data = raw_event.get("raw") or {}
        last_price = raw_data.get("c") or raw_data.get("lastPrice")

        symbol = self.normalize_symbol(raw_event.get("symbol", ""))
        ts_local = int(raw_event.get("ts_local") or self.now_ms())
        ts_exchange = int(raw_event.get("ts_exchange") or ts_local)

        return BBOUpdate(
            exchange=self.exchange_name,
            symbol=symbol,
            data=BBOData(
                bid=self.to_decimal(best_bid) or Decimal(0),
                ask=self.to_decimal(best_ask) or Decimal(0),
                bid_size=self.to_decimal(bid_size) or Decimal(0),
                ask_size=self.to_decimal(ask_size) or Decimal(0),
                last_price=self.to_decimal(last_price),
            ),
            metadata=EventMetadata(
                ts_exchange=ts_exchange,
                ts_local=ts_local,
                event_type=EventType.BBO_UPDATE,
            ),
            raw=raw_data,
        )

    def normalize_order(self, raw_event: Dict[str, Any]) -> NormalizedOrders:
        order_id = raw_event.get("order_id") or raw_event.get("trade_id")
        if not order_id:
            return None

        status = self.normalize_order_status(raw_event.get("status", "NEW"))
        side_raw = str(raw_event.get("side", "")).lower()
        side = OrderSide.BUY if side_raw == "buy" else OrderSide.SELL

        amount = self.to_decimal(raw_event.get("orig_qty")) or Decimal(0)
        filled = self.to_decimal(raw_event.get("filled_qty")) or Decimal(0)
        remaining = max(Decimal(0), amount - filled)

        last_qty = self.to_decimal(raw_event.get("last_qty"))
        fill_price = self.to_decimal(raw_event.get("last_price"))
        filled_amount = last_qty if last_qty is not None else None

        event_type = EventType.ORDER_UPDATE
        if last_qty is not None and last_qty > 0:
            event_type = EventType.FILL_UPDATE

        symbol = self.normalize_symbol(raw_event.get("symbol", ""))
        ts_local = int(raw_event.get("ts_local") or self.now_ms())
        ts_exchange = int(raw_event.get("ts_exchange") or ts_local)

        return OrderUpdate(
            exchange=self.exchange_name,
            symbol=symbol,
            data=OrderData(
                order_id=str(order_id),
                client_order_id=raw_event.get("client_order_id"),
                status=status,
                side=side,
                price=self.to_decimal(raw_event.get("price")),
                amount=amount,
                filled=filled,
                remaining=remaining,
                fill_price=fill_price,
                filled_amount=filled_amount,
            ),
            metadata=EventMetadata(
                ts_exchange=ts_exchange,
                ts_local=ts_local,
                event_type=event_type,
            ),
            raw=raw_event.get("raw"),
        )


class AsterNormalizer(Normalizer):
    """Aster (Binance-style futures DEX) WS normalizer."""

    _QUOTE_ASSETS = ("USDT", "USDC", "BUSD")

    def __init__(self) -> None:
        super().__init__("aster")

    def normalize_symbol(self, raw_symbol: str, *, market_index: Optional[int] = None) -> str:
        symbol = (raw_symbol or "").upper()
        if "/" in symbol:
            return symbol
        if "_" in symbol:
            return symbol.replace("_", "/")
        for quote in self._QUOTE_ASSETS:
            if symbol.endswith(quote) and len(symbol) > len(quote):
                base = symbol[: -len(quote)]
                return f"{base}/{quote}"
        return symbol or "UNKNOWN"

    def normalize_order_status(self, raw_status: str) -> OrderStatus:
        status = (raw_status or "").upper()
        mapping = {
            "NEW": OrderStatus.OPEN,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "CANCELLED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED,
        }
        return mapping.get(status, OrderStatus.OPEN)

    def normalize_bbo(self, raw_event: Dict[str, Any]) -> Optional[BBOUpdate]:
        bids = raw_event.get("bids") or []
        asks = raw_event.get("asks") or []
        if not bids or not asks:
            return None
        try:
            best_bid = bids[0][0]
            best_ask = asks[0][0]
        except (IndexError, TypeError):
            return None
        bid_size = bids[0][1] if len(bids[0]) > 1 else 0
        ask_size = asks[0][1] if len(asks[0]) > 1 else 0

        raw_data = raw_event.get("raw") or {}
        last_price = raw_data.get("c") or raw_data.get("lastPrice")

        symbol = self.normalize_symbol(raw_event.get("symbol", ""))
        ts_local = int(raw_event.get("ts_local") or self.now_ms())
        ts_exchange = int(raw_event.get("ts_exchange") or ts_local)

        return BBOUpdate(
            exchange=self.exchange_name,
            symbol=symbol,
            data=BBOData(
                bid=self.to_decimal(best_bid) or Decimal(0),
                ask=self.to_decimal(best_ask) or Decimal(0),
                bid_size=self.to_decimal(bid_size) or Decimal(0),
                ask_size=self.to_decimal(ask_size) or Decimal(0),
                last_price=self.to_decimal(last_price),
            ),
            metadata=EventMetadata(
                ts_exchange=ts_exchange,
                ts_local=ts_local,
                event_type=EventType.BBO_UPDATE,
            ),
            raw=raw_data,
        )

    def normalize_order(self, raw_event: Dict[str, Any]) -> NormalizedOrders:
        order_id = raw_event.get("order_id") or raw_event.get("trade_id")
        if not order_id:
            return None

        status = self.normalize_order_status(raw_event.get("status", "NEW"))
        side_raw = str(raw_event.get("side", "")).lower()
        side = OrderSide.BUY if side_raw == "buy" else OrderSide.SELL

        amount = self.to_decimal(raw_event.get("orig_qty")) or Decimal(0)
        filled = self.to_decimal(raw_event.get("filled_qty")) or Decimal(0)
        remaining = max(Decimal(0), amount - filled)

        last_qty = self.to_decimal(raw_event.get("last_qty"))
        fill_price = self.to_decimal(raw_event.get("last_price"))
        filled_amount = last_qty if last_qty is not None else None

        event_type = EventType.ORDER_UPDATE
        if last_qty is not None and last_qty > 0:
            event_type = EventType.FILL_UPDATE

        symbol = self.normalize_symbol(raw_event.get("symbol", ""))
        ts_local = int(raw_event.get("ts_local") or self.now_ms())
        ts_exchange = int(raw_event.get("ts_exchange") or ts_local)

        return OrderUpdate(
            exchange=self.exchange_name,
            symbol=symbol,
            data=OrderData(
                order_id=str(order_id),
                client_order_id=raw_event.get("client_order_id"),
                status=status,
                side=side,
                price=self.to_decimal(raw_event.get("price")),
                amount=amount,
                filled=filled,
                remaining=remaining,
                fill_price=fill_price,
                filled_amount=filled_amount,
            ),
            metadata=EventMetadata(
                ts_exchange=ts_exchange,
                ts_local=ts_local,
                event_type=event_type,
            ),
            raw=raw_event.get("raw"),
        )


class VariationalNormalizer(Normalizer):
    """Variational (Omni) RFQ normalizer."""

    def __init__(self) -> None:
        super().__init__("variational")

    def normalize_symbol(self, raw_symbol: str, *, market_index: Optional[int] = None) -> str:
        symbol = raw_symbol or ""
        symbol = symbol.replace("_PERP", "")
        if "_" in symbol and "/" not in symbol:
            return symbol.replace("_", "/")
        return symbol or "UNKNOWN"

    def normalize_order_status(self, raw_status: str) -> OrderStatus:
        status = (raw_status or "").lower()
        mapping = {
            "pending": OrderStatus.OPEN,
            "filled": OrderStatus.FILLED,
            "cancelled": OrderStatus.CANCELLED,
            "canceled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
        }
        return mapping.get(status, OrderStatus.OPEN)

    def normalize_bbo(self, raw_event: Dict[str, Any]) -> Optional[BBOUpdate]:
        bid = raw_event.get("bid")
        ask = raw_event.get("ask")
        if bid is None or ask is None:
            return None

        instrument = raw_event.get("instrument") or {}
        symbol = None
        if isinstance(instrument, dict):
            underlying = instrument.get("underlying")
            settlement = instrument.get("settlement_asset")
            if underlying and settlement:
                symbol = f"{underlying}/{settlement}"
        if not symbol:
            symbol = self.normalize_symbol(raw_event.get("symbol", ""))

        ts_local = int(raw_event.get("ts_local") or self.now_ms())
        latency_ms = raw_event.get("latency_ms") or 0
        try:
            latency_ms = int(latency_ms)
        except (TypeError, ValueError):
            latency_ms = 0
        ts_exchange = int(raw_event.get("ts_exchange") or (ts_local - latency_ms))

        return BBOUpdate(
            exchange=self.exchange_name,
            symbol=symbol,
            data=BBOData(
                bid=self.to_decimal(bid) or Decimal(0),
                ask=self.to_decimal(ask) or Decimal(0),
                bid_size=Decimal(0),
                ask_size=Decimal(0),
                last_price=self.to_decimal(raw_event.get("last_price")),
            ),
            metadata=EventMetadata(
                ts_exchange=ts_exchange,
                ts_local=ts_local,
                event_type=EventType.BBO_UPDATE,
            ),
            raw=raw_event.get("raw"),
        )

    def normalize_order(self, raw_event: Dict[str, Any]) -> NormalizedOrders:
        transfer_id = raw_event.get("transfer_id") or raw_event.get("trade_id")
        if not transfer_id:
            return None

        side_raw = str(raw_event.get("side", "")).lower()
        side = OrderSide.BUY if side_raw == "buy" else OrderSide.SELL

        price = self.to_decimal(raw_event.get("price"))
        qty = self.to_decimal(raw_event.get("qty")) or Decimal(0)

        symbol = self.normalize_symbol(raw_event.get("symbol", ""))
        ts_local = int(raw_event.get("ts_local") or self.now_ms())
        ts_exchange = int(raw_event.get("ts_exchange") or ts_local)

        return OrderUpdate(
            exchange=self.exchange_name,
            symbol=symbol,
            data=OrderData(
                order_id=str(transfer_id),
                client_order_id=None,
                status=OrderStatus.FILLED,
                side=side,
                price=price,
                amount=qty,
                filled=qty,
                remaining=Decimal(0),
                fill_price=price,
                filled_amount=qty,
            ),
            metadata=EventMetadata(
                ts_exchange=ts_exchange,
                ts_local=ts_local,
                event_type=EventType.FILL_UPDATE,
            ),
            raw=raw_event.get("raw"),
        )
