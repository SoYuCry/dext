"""Tests for WebSocket normalizers.

Covers all five normalizers: Lighter, Backpack, Binance, Aster, Variational.
Each normalizer is tested for normalize_symbol, normalize_order_status,
normalize_bbo, and normalize_order.
"""

import pytest
from decimal import Decimal

from exchanges.ws.normalizer import (
    LighterNormalizer,
    BackpackNormalizer,
    BinanceNormalizer,
    AsterNormalizer,
    VariationalNormalizer,
)
from exchanges.ws.types import (
    BBOUpdate,
    OrderUpdate,
    OrderStatus,
    OrderSide,
    EventType,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def lighter():
    return LighterNormalizer(market_index_to_symbol={0: "ETH/USDC", 1: "BTC/USDC"})

@pytest.fixture
def lighter_no_map():
    return LighterNormalizer()

@pytest.fixture
def backpack():
    return BackpackNormalizer()

@pytest.fixture
def binance():
    return BinanceNormalizer()

@pytest.fixture
def aster():
    return AsterNormalizer()

@pytest.fixture
def variational():
    return VariationalNormalizer()


# ============================================================
# LighterNormalizer
# ============================================================

class TestLighterNormalizeSymbol:
    def test_market_index_mapping(self, lighter):
        assert lighter.normalize_symbol("", market_index=0) == "ETH/USDC"
        assert lighter.normalize_symbol("", market_index=1) == "BTC/USDC"

    def test_market_index_string_cast(self, lighter):
        """market_index is cast to int internally."""
        assert lighter.normalize_symbol("", market_index="0") == "ETH/USDC"

    def test_market_index_unknown(self, lighter):
        assert lighter.normalize_symbol("FOO", market_index=99) == "FOO"

    def test_market_prefix(self, lighter):
        assert lighter.normalize_symbol("MARKET_0") == "ETH/USDC"
        assert lighter.normalize_symbol("MARKET_1") == "BTC/USDC"

    def test_market_prefix_unknown_id(self, lighter):
        # Falls through to underscore-to-slash conversion
        assert lighter.normalize_symbol("MARKET_99") == "MARKET/99"

    def test_market_prefix_invalid(self, lighter):
        # non-numeric after MARKET_ falls through to underscore-to-slash
        result = lighter.normalize_symbol("MARKET_abc")
        assert result == "MARKET/abc"

    def test_underscore_to_slash(self, lighter):
        assert lighter.normalize_symbol("SOL_USDC") == "SOL/USDC"

    def test_already_normalized(self, lighter):
        assert lighter.normalize_symbol("ETH/USDC") == "ETH/USDC"

    def test_empty_string(self, lighter):
        assert lighter.normalize_symbol("") == "UNKNOWN"

    def test_none_like(self, lighter_no_map):
        assert lighter_no_map.normalize_symbol("") == "UNKNOWN"

    def test_plain_symbol(self, lighter_no_map):
        assert lighter_no_map.normalize_symbol("ETHUSDC") == "ETHUSDC"


class TestLighterNormalizeOrderStatus:
    @pytest.mark.parametrize("raw,expected", [
        ("open", OrderStatus.OPEN),
        ("new", OrderStatus.OPEN),
        ("OPEN", OrderStatus.OPEN),
        ("NEW", OrderStatus.OPEN),
        ("partially_filled", OrderStatus.PARTIALLY_FILLED),
        ("partial", OrderStatus.PARTIALLY_FILLED),
        ("filled", OrderStatus.FILLED),
        ("FILLED", OrderStatus.FILLED),
        ("cancelled", OrderStatus.CANCELLED),
        ("canceled", OrderStatus.CANCELLED),
        ("rejected", OrderStatus.REJECTED),
        ("expired", OrderStatus.EXPIRED),
    ])
    def test_known_statuses(self, lighter, raw, expected):
        assert lighter.normalize_order_status(raw) == expected

    def test_unknown_defaults_to_open(self, lighter):
        assert lighter.normalize_order_status("something_random") == OrderStatus.OPEN

    def test_empty_defaults_to_open(self, lighter):
        assert lighter.normalize_order_status("") == OrderStatus.OPEN


class TestLighterNormalizeBbo:
    def test_valid_bbo_with_best_fields(self, lighter):
        raw = {
            "best_bid": "1800.50",
            "best_ask": "1801.00",
            "best_bid_size": "2.5",
            "best_ask_size": "3.0",
            "market_index": 0,
            "ts_local": 1700000000000,
            "ts_exchange": 1699999999900,
        }
        result = lighter.normalize_bbo(raw)
        assert result is not None
        assert isinstance(result, BBOUpdate)
        assert result.exchange == "lighter"
        assert result.symbol == "ETH/USDC"
        assert result.data.bid == Decimal("1800.50")
        assert result.data.ask == Decimal("1801.00")
        assert result.data.bid_size == Decimal("2.5")
        assert result.data.ask_size == Decimal("3.0")
        assert result.metadata.event_type == EventType.BBO_UPDATE
        assert result.metadata.ts_exchange == 1699999999900
        assert result.metadata.ts_local == 1700000000000

    def test_valid_bbo_from_bids_asks_arrays(self, lighter):
        raw = {
            "bids": [["1800", "10"]],
            "asks": [["1801", "5"]],
            "market_index": 0,
            "ts_local": 1700000000000,
        }
        result = lighter.normalize_bbo(raw)
        assert result is not None
        assert result.data.bid == Decimal("1800")
        assert result.data.ask == Decimal("1801")
        assert result.data.bid_size == Decimal("10")
        assert result.data.ask_size == Decimal("5")

    def test_missing_bid_returns_none(self, lighter):
        raw = {"best_ask": "1801", "asks": [["1801", "5"]]}
        assert lighter.normalize_bbo(raw) is None

    def test_missing_ask_returns_none(self, lighter):
        raw = {"best_bid": "1800", "bids": [["1800", "10"]]}
        assert lighter.normalize_bbo(raw) is None

    def test_empty_event_returns_none(self, lighter):
        assert lighter.normalize_bbo({}) is None

    def test_last_price_included(self, lighter):
        raw = {
            "best_bid": "1800",
            "best_ask": "1801",
            "last_price": "1800.75",
            "market_index": 0,
            "ts_local": 1700000000000,
        }
        result = lighter.normalize_bbo(raw)
        assert result.data.last_price == Decimal("1800.75")

    def test_last_price_absent(self, lighter):
        raw = {
            "best_bid": "1800",
            "best_ask": "1801",
            "market_index": 0,
            "ts_local": 1700000000000,
        }
        result = lighter.normalize_bbo(raw)
        assert result.data.last_price is None


class TestLighterDeriveFillFields:
    def test_derives_fill_price(self, lighter):
        order = {"filled_base_amount": "10", "filled_quote_amount": "18005"}
        result = lighter._derive_fill_fields(order)
        assert result["fill_price"] == Decimal("18005") / Decimal("10")
        assert result["filled_amount"] == Decimal("10")

    def test_zero_base_returns_empty(self, lighter):
        order = {"filled_base_amount": "0", "filled_quote_amount": "0"}
        assert lighter._derive_fill_fields(order) == {}

    def test_missing_base_returns_empty(self, lighter):
        order = {"filled_quote_amount": "100"}
        assert lighter._derive_fill_fields(order) == {}

    def test_missing_quote_returns_empty(self, lighter):
        order = {"filled_base_amount": "10"}
        assert lighter._derive_fill_fields(order) == {}


class TestLighterNormalizeOrder:
    def test_valid_order(self, lighter):
        raw = {
            "orders": [{
                "order_index": "123",
                "client_order_index": "c456",
                "status": "open",
                "is_ask": False,
                "price": "1800",
                "initial_base_amount": "5",
                "filled_base_amount": "0",
                "remaining_base_amount": "5",
            }],
            "market_index": 0,
            "ts_local": 1700000000000,
            "ts_exchange": 1699999999900,
        }
        result = lighter.normalize_order(raw)
        assert isinstance(result, list)
        assert len(result) == 1
        order = result[0]
        assert isinstance(order, OrderUpdate)
        assert order.exchange == "lighter"
        assert order.symbol == "ETH/USDC"
        assert order.data.order_id == "123"
        assert order.data.client_order_id == "c456"
        assert order.data.status == OrderStatus.OPEN
        assert order.data.side == OrderSide.BUY
        assert order.data.price == Decimal("1800")
        assert order.data.amount == Decimal("5")
        assert order.data.filled == Decimal("0")
        assert order.data.remaining == Decimal("5")
        assert order.metadata.event_type == EventType.ORDER_UPDATE

    def test_sell_side(self, lighter):
        raw = {
            "orders": [{"order_index": "1", "is_ask": True, "status": "open",
                         "initial_base_amount": "1", "filled_base_amount": "0"}],
            "market_index": 0,
            "ts_local": 1700000000000,
        }
        result = lighter.normalize_order(raw)
        assert result[0].data.side == OrderSide.SELL

    def test_filled_order_triggers_fill_event(self, lighter):
        raw = {
            "orders": [{
                "order_index": "10",
                "status": "filled",
                "is_ask": False,
                "initial_base_amount": "5",
                "filled_base_amount": "5",
                "filled_quote_amount": "9000",
                "remaining_base_amount": "0",
            }],
            "market_index": 0,
            "ts_local": 1700000000000,
        }
        result = lighter.normalize_order(raw)
        assert result[0].metadata.event_type == EventType.FILL_UPDATE
        assert result[0].data.status == OrderStatus.FILLED
        assert result[0].data.fill_price == Decimal("9000") / Decimal("5")
        assert result[0].data.filled_amount == Decimal("5")

    def test_missing_order_id_skipped(self, lighter):
        raw = {
            "orders": [{"status": "open", "is_ask": False}],
            "market_index": 0,
            "ts_local": 1700000000000,
        }
        result = lighter.normalize_order(raw)
        assert result is None

    def test_no_orders_returns_none(self, lighter):
        assert lighter.normalize_order({}) is None
        assert lighter.normalize_order({"orders": []}) is None

    def test_multiple_orders(self, lighter):
        raw = {
            "orders": [
                {"order_index": "1", "status": "open", "is_ask": False,
                 "initial_base_amount": "1", "filled_base_amount": "0"},
                {"order_index": "2", "status": "filled", "is_ask": True,
                 "initial_base_amount": "2", "filled_base_amount": "2",
                 "filled_quote_amount": "3600"},
            ],
            "market_index": 0,
            "ts_local": 1700000000000,
        }
        result = lighter.normalize_order(raw)
        assert len(result) == 2
        assert result[0].data.order_id == "1"
        assert result[1].data.order_id == "2"

    def test_remaining_derived_from_amount_minus_filled(self, lighter):
        raw = {
            "orders": [{
                "order_index": "1",
                "status": "partially_filled",
                "is_ask": False,
                "initial_base_amount": "10",
                "filled_base_amount": "3",
                # no remaining_base_amount
            }],
            "market_index": 0,
            "ts_local": 1700000000000,
        }
        result = lighter.normalize_order(raw)
        assert result[0].data.remaining == Decimal("7")


# ============================================================
# BackpackNormalizer
# ============================================================

class TestBackpackNormalizeSymbol:
    def test_underscore_to_slash(self, backpack):
        assert backpack.normalize_symbol("SOL_USDC") == "SOL/USDC"

    def test_already_normalized(self, backpack):
        assert backpack.normalize_symbol("SOL/USDC") == "SOL/USDC"

    def test_empty_string(self, backpack):
        assert backpack.normalize_symbol("") == "UNKNOWN"

    def test_plain_symbol(self, backpack):
        # no underscore, no slash -> returned as-is
        assert backpack.normalize_symbol("SOLUSDC") == "SOLUSDC"


class TestBackpackNormalizeOrderStatus:
    @pytest.mark.parametrize("raw,expected", [
        ("new", OrderStatus.OPEN),
        ("New", OrderStatus.OPEN),
        ("open", OrderStatus.OPEN),
        ("partiallyfilled", OrderStatus.PARTIALLY_FILLED),
        ("partially_filled", OrderStatus.PARTIALLY_FILLED),
        ("filled", OrderStatus.FILLED),
        ("cancelled", OrderStatus.CANCELLED),
        ("canceled", OrderStatus.CANCELLED),
        ("rejected", OrderStatus.REJECTED),
        ("expired", OrderStatus.EXPIRED),
    ])
    def test_known_statuses(self, backpack, raw, expected):
        assert backpack.normalize_order_status(raw) == expected

    def test_unknown_defaults_to_open(self, backpack):
        assert backpack.normalize_order_status("xyz") == OrderStatus.OPEN

    def test_empty_defaults_to_open(self, backpack):
        assert backpack.normalize_order_status("") == OrderStatus.OPEN


class TestBackpackNormalizeBbo:
    def test_valid_bbo(self, backpack):
        raw = {
            "bids": [["100.5", "20"]],
            "asks": [["101.0", "15"]],
            "symbol": "SOL_USDC",
            "ts_local": 1700000000000,
            "ts_exchange": 1699999999900,
            "raw": {"c": "100.75"},
        }
        result = backpack.normalize_bbo(raw)
        assert result is not None
        assert result.exchange == "backpack"
        assert result.symbol == "SOL/USDC"
        assert result.data.bid == Decimal("100.5")
        assert result.data.ask == Decimal("101.0")
        assert result.data.bid_size == Decimal("20")
        assert result.data.ask_size == Decimal("15")
        assert result.data.last_price == Decimal("100.75")
        assert result.metadata.event_type == EventType.BBO_UPDATE

    def test_missing_bids_returns_none(self, backpack):
        assert backpack.normalize_bbo({"asks": [["101", "5"]]}) is None

    def test_missing_asks_returns_none(self, backpack):
        assert backpack.normalize_bbo({"bids": [["100", "5"]]}) is None

    def test_empty_bids_returns_none(self, backpack):
        assert backpack.normalize_bbo({"bids": [], "asks": [["101", "5"]]}) is None

    def test_last_price_from_raw_lastprice(self, backpack):
        raw = {
            "bids": [["100", "1"]],
            "asks": [["101", "1"]],
            "symbol": "SOL_USDC",
            "ts_local": 1700000000000,
            "raw": {"lastPrice": "100.5"},
        }
        result = backpack.normalize_bbo(raw)
        assert result.data.last_price == Decimal("100.5")


class TestBackpackNormalizeOrder:
    def test_valid_order(self, backpack):
        raw = {
            "order_id": "ord_001",
            "client_order_id": "cl_001",
            "status": "new",
            "side": "buy",
            "price": "100",
            "orig_qty": "10",
            "filled_qty": "0",
            "symbol": "SOL_USDC",
            "ts_local": 1700000000000,
            "ts_exchange": 1699999999900,
        }
        result = backpack.normalize_order(raw)
        assert isinstance(result, OrderUpdate)
        assert result.exchange == "backpack"
        assert result.symbol == "SOL/USDC"
        assert result.data.order_id == "ord_001"
        assert result.data.client_order_id == "cl_001"
        assert result.data.status == OrderStatus.OPEN
        assert result.data.side == OrderSide.BUY
        assert result.data.amount == Decimal("10")
        assert result.data.filled == Decimal("0")
        assert result.data.remaining == Decimal("10")
        assert result.metadata.event_type == EventType.ORDER_UPDATE

    def test_fill_update_event_type(self, backpack):
        raw = {
            "order_id": "ord_002",
            "status": "filled",
            "side": "sell",
            "orig_qty": "5",
            "filled_qty": "5",
            "last_price": "101",
            "last_qty": "5",
            "event_type": "FILL_UPDATE",
            "symbol": "SOL_USDC",
            "ts_local": 1700000000000,
        }
        result = backpack.normalize_order(raw)
        assert result.metadata.event_type == EventType.FILL_UPDATE
        assert result.data.fill_price == Decimal("101")
        assert result.data.filled_amount == Decimal("5")

    def test_missing_order_id_returns_none(self, backpack):
        assert backpack.normalize_order({"status": "new", "side": "buy"}) is None

    def test_trade_id_fallback(self, backpack):
        raw = {
            "trade_id": "t_001",
            "status": "filled",
            "side": "buy",
            "orig_qty": "1",
            "filled_qty": "1",
            "symbol": "SOL_USDC",
            "ts_local": 1700000000000,
        }
        result = backpack.normalize_order(raw)
        assert result.data.order_id == "t_001"

    def test_sell_side(self, backpack):
        raw = {
            "order_id": "1",
            "side": "sell",
            "orig_qty": "1",
            "filled_qty": "0",
            "symbol": "SOL_USDC",
            "ts_local": 1700000000000,
        }
        result = backpack.normalize_order(raw)
        assert result.data.side == OrderSide.SELL


# ============================================================
# BinanceNormalizer
# ============================================================

class TestBinanceNormalizeSymbol:
    def test_concat_symbol_usdt(self, binance):
        assert binance.normalize_symbol("ETHUSDT") == "ETH/USDT"

    def test_concat_symbol_usdc(self, binance):
        assert binance.normalize_symbol("BTCUSDC") == "BTC/USDC"

    def test_concat_symbol_btc_quote(self, binance):
        assert binance.normalize_symbol("ETHBTC") == "ETH/BTC"

    def test_concat_symbol_busd(self, binance):
        assert binance.normalize_symbol("SOLBUSD") == "SOL/BUSD"

    def test_concat_symbol_bnb(self, binance):
        assert binance.normalize_symbol("ETHBNB") == "ETH/BNB"

    def test_underscore_format(self, binance):
        assert binance.normalize_symbol("ETH_USDT") == "ETH/USDT"

    def test_already_normalized(self, binance):
        assert binance.normalize_symbol("ETH/USDT") == "ETH/USDT"

    def test_lowercase_uppercased(self, binance):
        assert binance.normalize_symbol("ethusdt") == "ETH/USDT"

    def test_empty_string(self, binance):
        assert binance.normalize_symbol("") == "UNKNOWN"

    def test_no_matching_quote(self, binance):
        # If the symbol doesn't end with a known quote asset, return as-is
        assert binance.normalize_symbol("XYZABC") == "XYZABC"

    def test_fdusd(self, binance):
        assert binance.normalize_symbol("BTCFDUSD") == "BTC/FDUSD"

    def test_quote_only_returns_as_is(self, binance):
        """A symbol that is exactly a quote asset should not split."""
        assert binance.normalize_symbol("USDT") == "USDT"


class TestBinanceNormalizeOrderStatus:
    @pytest.mark.parametrize("raw,expected", [
        ("NEW", OrderStatus.OPEN),
        ("PARTIALLY_FILLED", OrderStatus.PARTIALLY_FILLED),
        ("FILLED", OrderStatus.FILLED),
        ("CANCELED", OrderStatus.CANCELLED),
        ("CANCELLED", OrderStatus.CANCELLED),
        ("PENDING_CANCEL", OrderStatus.CANCELLED),
        ("REJECTED", OrderStatus.REJECTED),
        ("EXPIRED", OrderStatus.EXPIRED),
    ])
    def test_known_statuses(self, binance, raw, expected):
        assert binance.normalize_order_status(raw) == expected

    def test_unknown_defaults_to_open(self, binance):
        assert binance.normalize_order_status("SOMETHING_ELSE") == OrderStatus.OPEN

    def test_empty_defaults_to_open(self, binance):
        assert binance.normalize_order_status("") == OrderStatus.OPEN

    def test_lowercase_mapped(self, binance):
        # Binance uppercases first, so "new" -> "NEW"
        assert binance.normalize_order_status("new") == OrderStatus.OPEN


class TestBinanceNormalizeBbo:
    def test_valid_bbo(self, binance):
        raw = {
            "bids": [["50000.00", "1.5"]],
            "asks": [["50001.00", "2.0"]],
            "symbol": "BTCUSDT",
            "ts_local": 1700000000000,
            "ts_exchange": 1699999999900,
            "raw": {"c": "50000.50"},
        }
        result = binance.normalize_bbo(raw)
        assert result is not None
        assert result.exchange == "binance"
        assert result.symbol == "BTC/USDT"
        assert result.data.bid == Decimal("50000.00")
        assert result.data.ask == Decimal("50001.00")
        assert result.data.last_price == Decimal("50000.50")

    def test_empty_bids_returns_none(self, binance):
        assert binance.normalize_bbo({"bids": [], "asks": [["100", "1"]]}) is None

    def test_empty_asks_returns_none(self, binance):
        assert binance.normalize_bbo({"bids": [["100", "1"]], "asks": []}) is None


class TestBinanceNormalizeOrder:
    def test_valid_order(self, binance):
        raw = {
            "order_id": "12345",
            "client_order_id": "cl_12345",
            "status": "NEW",
            "side": "buy",
            "price": "50000",
            "orig_qty": "0.1",
            "filled_qty": "0",
            "symbol": "BTCUSDT",
            "ts_local": 1700000000000,
            "ts_exchange": 1699999999900,
        }
        result = binance.normalize_order(raw)
        assert isinstance(result, OrderUpdate)
        assert result.exchange == "binance"
        assert result.symbol == "BTC/USDT"
        assert result.data.order_id == "12345"
        assert result.data.status == OrderStatus.OPEN
        assert result.data.side == OrderSide.BUY
        assert result.data.amount == Decimal("0.1")
        assert result.data.remaining == Decimal("0.1")
        assert result.metadata.event_type == EventType.ORDER_UPDATE

    def test_fill_triggers_fill_event(self, binance):
        raw = {
            "order_id": "12345",
            "status": "FILLED",
            "side": "sell",
            "orig_qty": "1",
            "filled_qty": "1",
            "last_qty": "1",
            "last_price": "50000",
            "symbol": "BTCUSDT",
            "ts_local": 1700000000000,
        }
        result = binance.normalize_order(raw)
        assert result.metadata.event_type == EventType.FILL_UPDATE
        assert result.data.fill_price == Decimal("50000")
        assert result.data.filled_amount == Decimal("1")

    def test_no_fill_when_last_qty_zero(self, binance):
        raw = {
            "order_id": "12345",
            "status": "NEW",
            "side": "buy",
            "orig_qty": "1",
            "filled_qty": "0",
            "last_qty": "0",
            "symbol": "BTCUSDT",
            "ts_local": 1700000000000,
        }
        result = binance.normalize_order(raw)
        assert result.metadata.event_type == EventType.ORDER_UPDATE

    def test_missing_order_id_returns_none(self, binance):
        assert binance.normalize_order({"status": "NEW"}) is None


# ============================================================
# AsterNormalizer
# ============================================================

class TestAsterNormalizeSymbol:
    def test_concat_symbol_usdt(self, aster):
        assert aster.normalize_symbol("ETHUSDT") == "ETH/USDT"

    def test_concat_symbol_usdc(self, aster):
        assert aster.normalize_symbol("BTCUSDC") == "BTC/USDC"

    def test_underscore_format(self, aster):
        assert aster.normalize_symbol("ETH_USDT") == "ETH/USDT"

    def test_already_normalized(self, aster):
        assert aster.normalize_symbol("ETH/USDT") == "ETH/USDT"

    def test_empty_string(self, aster):
        assert aster.normalize_symbol("") == "UNKNOWN"

    def test_lowercase_uppercased(self, aster):
        assert aster.normalize_symbol("ethusdc") == "ETH/USDC"

    def test_no_matching_quote(self, aster):
        assert aster.normalize_symbol("XYZABC") == "XYZABC"

    def test_busd(self, aster):
        assert aster.normalize_symbol("SOLBUSD") == "SOL/BUSD"


class TestAsterNormalizeOrderStatus:
    @pytest.mark.parametrize("raw,expected", [
        ("NEW", OrderStatus.OPEN),
        ("PARTIALLY_FILLED", OrderStatus.PARTIALLY_FILLED),
        ("FILLED", OrderStatus.FILLED),
        ("CANCELED", OrderStatus.CANCELLED),
        ("CANCELLED", OrderStatus.CANCELLED),
        ("REJECTED", OrderStatus.REJECTED),
        ("EXPIRED", OrderStatus.EXPIRED),
    ])
    def test_known_statuses(self, aster, raw, expected):
        assert aster.normalize_order_status(raw) == expected

    def test_unknown_defaults_to_open(self, aster):
        assert aster.normalize_order_status("BLAH") == OrderStatus.OPEN

    def test_empty_defaults_to_open(self, aster):
        assert aster.normalize_order_status("") == OrderStatus.OPEN


class TestAsterNormalizeBbo:
    def test_valid_bbo(self, aster):
        raw = {
            "bids": [["2000.00", "5"]],
            "asks": [["2001.00", "3"]],
            "symbol": "ETHUSDT",
            "ts_local": 1700000000000,
            "ts_exchange": 1699999999900,
        }
        result = aster.normalize_bbo(raw)
        assert result is not None
        assert result.exchange == "aster"
        assert result.symbol == "ETH/USDT"
        assert result.data.bid == Decimal("2000.00")
        assert result.data.ask == Decimal("2001.00")

    def test_missing_bids_returns_none(self, aster):
        assert aster.normalize_bbo({"asks": [["100", "1"]]}) is None

    def test_missing_asks_returns_none(self, aster):
        assert aster.normalize_bbo({"bids": [["100", "1"]]}) is None


class TestAsterNormalizeOrder:
    def test_valid_order(self, aster):
        raw = {
            "order_id": "a_001",
            "status": "NEW",
            "side": "buy",
            "price": "2000",
            "orig_qty": "1",
            "filled_qty": "0",
            "symbol": "ETHUSDT",
            "ts_local": 1700000000000,
        }
        result = aster.normalize_order(raw)
        assert isinstance(result, OrderUpdate)
        assert result.exchange == "aster"
        assert result.data.order_id == "a_001"
        assert result.data.status == OrderStatus.OPEN
        assert result.data.remaining == Decimal("1")

    def test_fill_event(self, aster):
        raw = {
            "order_id": "a_002",
            "status": "FILLED",
            "side": "sell",
            "orig_qty": "2",
            "filled_qty": "2",
            "last_qty": "2",
            "last_price": "2001",
            "symbol": "ETHUSDT",
            "ts_local": 1700000000000,
        }
        result = aster.normalize_order(raw)
        assert result.metadata.event_type == EventType.FILL_UPDATE
        assert result.data.fill_price == Decimal("2001")
        assert result.data.filled_amount == Decimal("2")

    def test_missing_order_id_returns_none(self, aster):
        assert aster.normalize_order({"status": "NEW"}) is None


# ============================================================
# VariationalNormalizer
# ============================================================

class TestVariationalNormalizeSymbol:
    def test_perp_suffix_removed(self, variational):
        assert variational.normalize_symbol("ETH_PERP") == "ETH"

    def test_underscore_with_perp(self, variational):
        assert variational.normalize_symbol("ETH_USDC_PERP") == "ETH/USDC"

    def test_underscore_to_slash(self, variational):
        assert variational.normalize_symbol("ETH_USDC") == "ETH/USDC"

    def test_already_normalized(self, variational):
        assert variational.normalize_symbol("ETH/USDC") == "ETH/USDC"

    def test_empty_string(self, variational):
        assert variational.normalize_symbol("") == "UNKNOWN"

    def test_plain_symbol(self, variational):
        assert variational.normalize_symbol("ETH") == "ETH"


class TestVariationalNormalizeOrderStatus:
    @pytest.mark.parametrize("raw,expected", [
        ("pending", OrderStatus.OPEN),
        ("Pending", OrderStatus.OPEN),
        ("filled", OrderStatus.FILLED),
        ("cancelled", OrderStatus.CANCELLED),
        ("canceled", OrderStatus.CANCELLED),
        ("rejected", OrderStatus.REJECTED),
    ])
    def test_known_statuses(self, variational, raw, expected):
        assert variational.normalize_order_status(raw) == expected

    def test_unknown_defaults_to_open(self, variational):
        assert variational.normalize_order_status("xyz") == OrderStatus.OPEN

    def test_empty_defaults_to_open(self, variational):
        assert variational.normalize_order_status("") == OrderStatus.OPEN


class TestVariationalNormalizeBbo:
    def test_valid_bbo_with_instrument(self, variational):
        raw = {
            "bid": "1800.00",
            "ask": "1801.00",
            "instrument": {
                "underlying": "ETH",
                "settlement_asset": "USDC",
            },
            "ts_local": 1700000000000,
            "ts_exchange": 1699999999900,
        }
        result = variational.normalize_bbo(raw)
        assert result is not None
        assert result.exchange == "variational"
        assert result.symbol == "ETH/USDC"
        assert result.data.bid == Decimal("1800.00")
        assert result.data.ask == Decimal("1801.00")
        # Variational always has zero sizes
        assert result.data.bid_size == Decimal(0)
        assert result.data.ask_size == Decimal(0)
        assert result.metadata.event_type == EventType.BBO_UPDATE

    def test_symbol_fallback_when_no_instrument(self, variational):
        raw = {
            "bid": "100",
            "ask": "101",
            "symbol": "ETH_USDC",
            "ts_local": 1700000000000,
        }
        result = variational.normalize_bbo(raw)
        assert result.symbol == "ETH/USDC"

    def test_missing_bid_returns_none(self, variational):
        assert variational.normalize_bbo({"ask": "101"}) is None

    def test_missing_ask_returns_none(self, variational):
        assert variational.normalize_bbo({"bid": "100"}) is None

    def test_latency_ms_used(self, variational):
        raw = {
            "bid": "100",
            "ask": "101",
            "ts_local": 1700000000000,
            "latency_ms": 50,
        }
        result = variational.normalize_bbo(raw)
        assert result.metadata.ts_exchange == 1700000000000 - 50

    def test_last_price_included(self, variational):
        raw = {
            "bid": "100",
            "ask": "101",
            "last_price": "100.5",
            "ts_local": 1700000000000,
        }
        result = variational.normalize_bbo(raw)
        assert result.data.last_price == Decimal("100.5")


class TestVariationalNormalizeOrder:
    def test_valid_order(self, variational):
        raw = {
            "transfer_id": "txn_001",
            "side": "buy",
            "price": "1800",
            "qty": "5",
            "symbol": "ETH_USDC",
            "ts_local": 1700000000000,
            "ts_exchange": 1699999999900,
        }
        result = variational.normalize_order(raw)
        assert isinstance(result, OrderUpdate)
        assert result.exchange == "variational"
        assert result.symbol == "ETH/USDC"
        assert result.data.order_id == "txn_001"
        assert result.data.client_order_id is None
        # Variational orders are always FILLED
        assert result.data.status == OrderStatus.FILLED
        assert result.data.side == OrderSide.BUY
        assert result.data.price == Decimal("1800")
        assert result.data.amount == Decimal("5")
        assert result.data.filled == Decimal("5")
        assert result.data.remaining == Decimal(0)
        assert result.data.fill_price == Decimal("1800")
        assert result.data.filled_amount == Decimal("5")
        assert result.metadata.event_type == EventType.FILL_UPDATE

    def test_sell_side(self, variational):
        raw = {
            "transfer_id": "txn_002",
            "side": "sell",
            "price": "1800",
            "qty": "3",
            "symbol": "ETH_USDC",
            "ts_local": 1700000000000,
        }
        result = variational.normalize_order(raw)
        assert result.data.side == OrderSide.SELL

    def test_missing_transfer_id_returns_none(self, variational):
        assert variational.normalize_order({"side": "buy", "qty": "1"}) is None

    def test_trade_id_fallback(self, variational):
        raw = {
            "trade_id": "t_001",
            "side": "buy",
            "qty": "1",
            "price": "100",
            "symbol": "ETH_USDC",
            "ts_local": 1700000000000,
        }
        result = variational.normalize_order(raw)
        assert result.data.order_id == "t_001"


# ============================================================
# Base Normalizer utility tests
# ============================================================

class TestToDecimal:
    """Test the shared to_decimal static method via any normalizer."""

    def test_string(self, backpack):
        assert backpack.to_decimal("123.45") == Decimal("123.45")

    def test_int(self, backpack):
        assert backpack.to_decimal(42) == Decimal("42")

    def test_float(self, backpack):
        result = backpack.to_decimal(1.5)
        assert result == Decimal("1.5")

    def test_decimal_passthrough(self, backpack):
        d = Decimal("99.99")
        assert backpack.to_decimal(d) is d

    def test_none_returns_none(self, backpack):
        assert backpack.to_decimal(None) is None

    def test_invalid_returns_none(self, backpack):
        assert backpack.to_decimal("not_a_number") is None


class TestExchangeNameInit:
    """Verify exchange_name is set correctly."""

    def test_lighter(self, lighter):
        assert lighter.exchange_name == "lighter"

    def test_backpack(self, backpack):
        assert backpack.exchange_name == "backpack"

    def test_binance(self, binance):
        assert binance.exchange_name == "binance"

    def test_aster(self, aster):
        assert aster.exchange_name == "aster"

    def test_variational(self, variational):
        assert variational.exchange_name == "variational"
