"""Tests for MarketDataManager – price snapshots, position tracking, listeners."""

import asyncio
import time

import pytest

from exchanges.market_data import MarketDataManager, PriceSnapshot, PositionSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.time() * 1000)


def _make_mgr(**kwargs) -> MarketDataManager:
    return MarketDataManager(**kwargs)


def _account_orders_event(
    *,
    exchange: str = "lighter",
    market_index: int = 0,
    orders: list | None = None,
    symbol: str | None = None,
) -> dict:
    evt = {
        "stream": "account_orders",
        "exchange": exchange,
        "market_index": market_index,
        "orders": orders or [],
    }
    if symbol:
        evt["symbol"] = symbol
    return evt


def _filled_order(
    order_id,
    filled_base_amount,
    is_ask: bool = False,
    status: str = "filled",
) -> dict:
    return {
        "order_id": order_id,
        "filled_base_amount": filled_base_amount,
        "is_ask": is_ask,
        "status": status,
    }


# ===================================================================
# 1. _make_key
# ===================================================================


class TestMakeKey:
    def test_exchange_and_symbol(self):
        mgr = _make_mgr()
        assert mgr._make_key("binance", symbol="ETH/USDC", market_index=None) == "binance:ETH/USDC"

    def test_exchange_and_market_index(self):
        mgr = _make_mgr()
        assert mgr._make_key("lighter", symbol=None, market_index=0) == "lighter:market_index=0"

    def test_exchange_only(self):
        mgr = _make_mgr()
        assert mgr._make_key("backpack", symbol=None, market_index=None) == "backpack"

    def test_none_exchange_defaults_to_unknown(self):
        mgr = _make_mgr()
        assert mgr._make_key(None, symbol="BTC/USD", market_index=None) == "unknown:BTC/USD"

    def test_symbol_takes_priority_over_market_index(self):
        mgr = _make_mgr()
        # When both symbol and market_index are provided, symbol wins
        assert mgr._make_key("ex", symbol="X", market_index=5) == "ex:X"


# ===================================================================
# 2. Price Snapshot Management
# ===================================================================


class TestPriceSnapshots:
    def test_set_and_get_snapshot(self):
        mgr = _make_mgr()
        snap = PriceSnapshot(
            exchange="backpack", bid=100.0, ask=101.0,
            ts_exchange=1000, ts_local=_now_ms(), symbol="SOL/USDC",
        )
        mgr.set_snapshot("backpack:SOL/USDC", snap)
        result = mgr.get_snapshot(key="backpack:SOL/USDC")
        assert result is snap
        assert result.bid == 100.0
        assert result.ask == 101.0
        assert result.mid == 100.5

    def test_get_snapshot_returns_none_for_missing_key(self):
        mgr = _make_mgr()
        assert mgr.get_snapshot(key="nonexistent") is None

    def test_get_snapshot_by_exchange_and_symbol(self):
        mgr = _make_mgr()
        snap = PriceSnapshot(
            exchange="aster", bid=50.0, ask=51.0,
            ts_exchange=None, ts_local=_now_ms(),
        )
        mgr.set_snapshot("aster:ETH/USDC", snap)
        assert mgr.get_snapshot(exchange="aster", symbol="ETH/USDC") is snap

    def test_get_snapshot_by_market_index(self):
        mgr = _make_mgr()
        snap = PriceSnapshot(
            exchange="lighter", bid=1.0, ask=2.0,
            ts_exchange=None, ts_local=_now_ms(),
        )
        mgr.set_snapshot("lighter:market_index=0", snap)
        assert mgr.get_snapshot(exchange="lighter", market_index=0) is snap

    def test_multiple_exchanges(self):
        mgr = _make_mgr()
        snap_a = PriceSnapshot(exchange="a", bid=1.0, ask=2.0, ts_exchange=None, ts_local=_now_ms())
        snap_b = PriceSnapshot(exchange="b", bid=3.0, ask=4.0, ts_exchange=None, ts_local=_now_ms())
        mgr.set_snapshot("a:X", snap_a)
        mgr.set_snapshot("b:X", snap_b)
        assert mgr.get_snapshot(key="a:X").bid == 1.0
        assert mgr.get_snapshot(key="b:X").bid == 3.0

    def test_mid_none_when_bid_or_ask_missing(self):
        snap = PriceSnapshot(exchange="x", bid=None, ask=10.0, ts_exchange=None, ts_local=0)
        assert snap.mid is None
        snap2 = PriceSnapshot(exchange="x", bid=10.0, ask=None, ts_exchange=None, ts_local=0)
        assert snap2.mid is None

    def test_snapshot_overwrite(self):
        mgr = _make_mgr()
        old = PriceSnapshot(exchange="e", bid=1.0, ask=2.0, ts_exchange=None, ts_local=0)
        new = PriceSnapshot(exchange="e", bid=5.0, ask=6.0, ts_exchange=None, ts_local=1)
        mgr.set_snapshot("k", old)
        mgr.set_snapshot("k", new)
        assert mgr.get_snapshot(key="k").bid == 5.0


# ===================================================================
# 3. Snapshot Freshness / Staleness
# ===================================================================


class TestSnapshotFreshness:
    def test_fresh_snapshot(self):
        mgr = _make_mgr(stale_ms=5000)
        snap = PriceSnapshot(exchange="e", bid=1.0, ask=2.0, ts_exchange=None, ts_local=_now_ms())
        mgr.set_snapshot("k", snap)
        result, fresh, latency = mgr.get_snapshot_with_status(key="k")
        assert result is snap
        assert fresh is True
        assert latency < 1000

    def test_stale_snapshot(self):
        mgr = _make_mgr(stale_ms=100)
        snap = PriceSnapshot(exchange="e", bid=1.0, ask=2.0, ts_exchange=None, ts_local=_now_ms() - 500)
        mgr.set_snapshot("k", snap)
        _, fresh, latency = mgr.get_snapshot_with_status(key="k")
        assert fresh is False
        assert latency >= 400

    def test_get_ticker_returns_none_when_stale(self):
        mgr = _make_mgr(stale_ms=50)
        snap = PriceSnapshot(exchange="e", bid=1.0, ask=2.0, ts_exchange=None, ts_local=_now_ms() - 200)
        mgr.set_snapshot("k", snap)
        assert mgr.get_ticker(key="k") is None

    def test_get_ticker_returns_dict_when_fresh(self):
        mgr = _make_mgr(stale_ms=5000)
        snap = PriceSnapshot(exchange="e", bid=10.0, ask=11.0, ts_exchange=None, ts_local=_now_ms())
        mgr.set_snapshot("k", snap)
        ticker = mgr.get_ticker(key="k")
        assert ticker == {"bid": 10.0, "ask": 11.0}

    def test_custom_stale_ms_override(self):
        mgr = _make_mgr(stale_ms=50)
        snap = PriceSnapshot(exchange="e", bid=1.0, ask=2.0, ts_exchange=None, ts_local=_now_ms() - 100)
        mgr.set_snapshot("k", snap)
        # Default threshold would mark stale
        assert mgr.get_ticker(key="k") is None
        # Override with larger threshold
        assert mgr.get_ticker(key="k", stale_ms=5000) is not None


# ===================================================================
# 4. Orderbook
# ===================================================================


class TestOrderbook:
    def test_get_orderbook_with_bids_asks(self):
        mgr = _make_mgr()
        snap = PriceSnapshot(
            exchange="e", bid=1.0, ask=2.0, ts_exchange=100, ts_local=200,
            meta={"bids": [[1.0, 5.0]], "asks": [[2.0, 3.0]]},
        )
        mgr.set_snapshot("k", snap)
        ob = mgr.get_orderbook(key="k")
        assert ob["bids"] == [[1.0, 5.0]]
        assert ob["asks"] == [[2.0, 3.0]]
        assert ob["timestamp"] == 100
        assert ob["ts_local"] == 200

    def test_get_orderbook_none_when_missing(self):
        mgr = _make_mgr()
        assert mgr.get_orderbook(key="missing") is None

    def test_get_orderbook_none_when_no_bids_asks_in_meta(self):
        mgr = _make_mgr()
        snap = PriceSnapshot(exchange="e", bid=1.0, ask=2.0, ts_exchange=None, ts_local=0, meta={})
        mgr.set_snapshot("k", snap)
        assert mgr.get_orderbook(key="k") is None


# ===================================================================
# 5. Position Tracking (_update_position_from_orders)
# ===================================================================


class TestPositionTracking:
    @pytest.mark.asyncio
    async def test_buy_increases_position(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[
            _filled_order("o1", "1.5", is_ask=False),
        ])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(1.5)

    @pytest.mark.asyncio
    async def test_sell_decreases_position(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[
            _filled_order("o1", "2.0", is_ask=True),
        ])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(-2.0)

    @pytest.mark.asyncio
    async def test_multiple_fills_accumulate(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[
            _filled_order("o1", "1.0", is_ask=False),
            _filled_order("o2", "0.5", is_ask=False),
            _filled_order("o3", "0.3", is_ask=True),
        ])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(1.0 + 0.5 - 0.3)

    @pytest.mark.asyncio
    async def test_dedup_same_order_id(self):
        mgr = _make_mgr()
        event1 = _account_orders_event(orders=[_filled_order("o1", "1.0")])
        event2 = _account_orders_event(orders=[_filled_order("o1", "1.0")])
        await mgr._on_event(event1, source_key=None, source_exchange="lighter")
        await mgr._on_event(event2, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(1.0)  # Not 2.0

    @pytest.mark.asyncio
    async def test_dedup_within_single_event(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[
            _filled_order("o1", "1.0"),
            _filled_order("o1", "1.0"),
        ])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_different_order_ids_both_counted(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[
            _filled_order("o1", "1.0"),
            _filled_order("o2", "2.0"),
        ])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(3.0)

    @pytest.mark.asyncio
    async def test_non_filled_orders_ignored(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[
            _filled_order("o1", "1.0", status="open"),
            _filled_order("o2", "2.0", status="cancelled"),
            _filled_order("o3", "3.0", status="filled"),
        ])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(3.0)

    @pytest.mark.asyncio
    async def test_order_with_id_field_instead_of_order_id(self):
        """Order dedup also works with 'id' key."""
        mgr = _make_mgr()
        order = {"id": "alt1", "filled_base_amount": "1.0", "is_ask": False, "status": "filled"}
        event = _account_orders_event(orders=[order, order])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(1.0)

    def test_get_position_returns_none_if_no_data(self):
        mgr = _make_mgr()
        assert mgr.get_position(exchange="lighter", market_index=0) is None

    def test_set_position_creates_new(self):
        mgr = _make_mgr()
        mgr.set_position(5.0, exchange="lighter", market_index=0, source="api")
        assert mgr.get_position(exchange="lighter", market_index=0) == pytest.approx(5.0)

    def test_set_position_overwrites_existing(self):
        mgr = _make_mgr()
        mgr.set_position(5.0, exchange="lighter", market_index=0)
        mgr.set_position(-2.0, exchange="lighter", market_index=0)
        assert mgr.get_position(exchange="lighter", market_index=0) == pytest.approx(-2.0)

    def test_get_position_snapshot(self):
        mgr = _make_mgr()
        mgr.set_position(3.14, exchange="lighter", symbol="ETH/USDC", source="api")
        snap = mgr.get_position_snapshot(exchange="lighter", symbol="ETH/USDC")
        assert isinstance(snap, PositionSnapshot)
        assert snap.position == pytest.approx(3.14)
        assert snap.source == "api"
        assert snap.ts_local > 0

    def test_get_position_snapshot_returns_none_if_missing(self):
        mgr = _make_mgr()
        assert mgr.get_position_snapshot(key="nope") is None

    def test_set_position_with_explicit_key(self):
        mgr = _make_mgr()
        mgr.set_position(7.0, key="custom_key")
        assert mgr.get_position(key="custom_key") == pytest.approx(7.0)


# ===================================================================
# 6. Edge Cases for Position Updates
# ===================================================================


class TestPositionEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_orders_list(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        # Position key is created but stays at 0
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_orders_none(self):
        mgr = _make_mgr()
        event = _account_orders_event()
        event["orders"] = None
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_non_dict_order_skipped(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=["not_a_dict", 42, None])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_missing_filled_base_amount(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[
            {"order_id": "o1", "status": "filled", "is_ask": False},
        ])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_invalid_filled_base_amount(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[
            {"order_id": "o1", "status": "filled", "filled_base_amount": "abc", "is_ask": False},
        ])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_missing_status_field(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[
            {"order_id": "o1", "filled_base_amount": "1.0", "is_ask": False},
        ])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        # Status defaults to "" which != "filled", so order is skipped
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_order_without_id_still_counted(self):
        """Orders without any ID field are counted but can't be deduped."""
        mgr = _make_mgr()
        order = {"status": "filled", "filled_base_amount": "1.0", "is_ask": False}
        event = _account_orders_event(orders=[order, order])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        # Both counted since no ID for dedup
        pos = mgr.get_position(exchange="lighter", market_index=0)
        assert pos == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_source_key_overrides_generated_key(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[_filled_order("o1", "1.0")])
        await mgr._on_event(event, source_key="custom:key", source_exchange="lighter")
        assert mgr.get_position(key="custom:key") == pytest.approx(1.0)
        # Default key should not have data
        assert mgr.get_position(exchange="lighter", market_index=0) is None


# ===================================================================
# 7. Quote ID Management
# ===================================================================


class TestQuoteId:
    def test_get_quote_id_from_meta(self):
        mgr = _make_mgr()
        snap = PriceSnapshot(
            exchange="variational", bid=1.0, ask=2.0,
            ts_exchange=None, ts_local=_now_ms(),
            meta={"quote_id": "q123"},
        )
        mgr.set_snapshot("variational:ETH", snap)
        assert mgr.get_quote_id(exchange="variational", key="variational:ETH") == "q123"

    def test_get_quote_id_buy_side(self):
        mgr = _make_mgr()
        snap = PriceSnapshot(
            exchange="variational", bid=1.0, ask=2.0,
            ts_exchange=None, ts_local=_now_ms(),
            meta={"ask_quote_id": "ask_q", "bid_quote_id": "bid_q"},
        )
        mgr.set_snapshot("k", snap)
        assert mgr.get_quote_id(exchange="variational", key="k", side="buy") == "ask_q"

    def test_get_quote_id_sell_side(self):
        mgr = _make_mgr()
        snap = PriceSnapshot(
            exchange="variational", bid=1.0, ask=2.0,
            ts_exchange=None, ts_local=_now_ms(),
            meta={"ask_quote_id": "ask_q", "bid_quote_id": "bid_q"},
        )
        mgr.set_snapshot("k", snap)
        assert mgr.get_quote_id(exchange="variational", key="k", side="sell") == "bid_q"

    def test_get_quote_id_returns_none_when_no_snapshot(self):
        mgr = _make_mgr()
        assert mgr.get_quote_id(exchange="variational", key="missing") is None

    def test_get_quote_id_returns_none_no_side_no_quote_id(self):
        mgr = _make_mgr()
        snap = PriceSnapshot(
            exchange="variational", bid=1.0, ask=2.0,
            ts_exchange=None, ts_local=_now_ms(), meta={},
        )
        mgr.set_snapshot("k", snap)
        assert mgr.get_quote_id(exchange="variational", key="k") is None

    def test_get_quote_id_case_insensitive_side(self):
        mgr = _make_mgr()
        snap = PriceSnapshot(
            exchange="variational", bid=1.0, ask=2.0,
            ts_exchange=None, ts_local=_now_ms(),
            meta={"ask_quote_id": "aq", "bid_quote_id": "bq"},
        )
        mgr.set_snapshot("k", snap)
        assert mgr.get_quote_id(exchange="variational", key="k", side="BUY") == "aq"
        assert mgr.get_quote_id(exchange="variational", key="k", side="Sell") == "bq"


# ===================================================================
# 8. Listener System
# ===================================================================


class TestListeners:
    @pytest.mark.asyncio
    async def test_add_listener_and_emit(self):
        mgr = _make_mgr()
        received = []

        async def handler(event):
            received.append(event)

        mgr.add_listener(handler)
        event = _account_orders_event(orders=[_filled_order("o1", "1.0")])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        # Let the fire-and-forget task complete
        await asyncio.sleep(0.05)
        assert len(received) == 1
        assert received[0] is event

    @pytest.mark.asyncio
    async def test_multiple_listeners(self):
        mgr = _make_mgr()
        r1, r2 = [], []

        async def h1(event):
            r1.append(event)

        async def h2(event):
            r2.append(event)

        mgr.add_listener(h1)
        mgr.add_listener(h2)
        event = _account_orders_event(orders=[])
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        await asyncio.sleep(0.05)
        assert len(r1) == 1
        assert len(r2) == 1

    @pytest.mark.asyncio
    async def test_listener_exception_does_not_propagate(self):
        mgr = _make_mgr()
        call_count = 0

        async def bad_handler(event):
            raise RuntimeError("boom")

        async def good_handler(event):
            nonlocal call_count
            call_count += 1

        mgr.add_listener(bad_handler)
        mgr.add_listener(good_handler)
        event = _account_orders_event(orders=[])
        # Should not raise
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        await asyncio.sleep(0.05)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_no_listeners_no_error(self):
        mgr = _make_mgr()
        event = _account_orders_event(orders=[])
        # Should not raise even without listeners
        await mgr._on_event(event, source_key=None, source_exchange="lighter")

    @pytest.mark.asyncio
    async def test_listener_called_for_orderbook_events(self):
        mgr = _make_mgr()
        received = []

        async def handler(event):
            received.append(event)

        mgr.add_listener(handler)
        event = {
            "exchange": "backpack",
            "symbol": "SOL/USDC",
            "best_bid": "100.0",
            "best_ask": "101.0",
            "ts_local": _now_ms(),
        }
        await mgr._on_event(event, source_key=None, source_exchange="backpack")
        await asyncio.sleep(0.05)
        assert len(received) == 1


# ===================================================================
# 9. _on_event / Orderbook Event Handling
# ===================================================================


class TestOnEvent:
    @pytest.mark.asyncio
    async def test_orderbook_event_creates_snapshot(self):
        mgr = _make_mgr()
        event = {
            "exchange": "backpack",
            "symbol": "SOL/USDC",
            "best_bid": "100.0",
            "best_ask": "101.0",
            "bids": [[100.0, 5.0]],
            "asks": [[101.0, 3.0]],
            "ts_local": _now_ms(),
        }
        await mgr._on_event(event, source_key=None, source_exchange="backpack")
        snap = mgr.get_snapshot(exchange="backpack", symbol="SOL/USDC")
        assert snap is not None
        assert snap.bid == 100.0
        assert snap.ask == 101.0

    @pytest.mark.asyncio
    async def test_orderbook_event_fallback_to_bids_asks_for_best(self):
        mgr = _make_mgr()
        event = {
            "exchange": "lighter",
            "symbol": "ETH/USDC",
            "bids": [[2000.0, 1.0]],
            "asks": [[2001.0, 2.0]],
            "ts_local": _now_ms(),
        }
        await mgr._on_event(event, source_key=None, source_exchange="lighter")
        snap = mgr.get_snapshot(exchange="lighter", symbol="ETH/USDC")
        assert snap.bid == 2000.0
        assert snap.ask == 2001.0

    @pytest.mark.asyncio
    async def test_event_count_incremented(self):
        mgr = _make_mgr()
        assert mgr._event_count == 0
        event = {"exchange": "x", "symbol": "Y", "best_bid": "1", "best_ask": "2", "ts_local": _now_ms()}
        await mgr._on_event(event, source_key=None, source_exchange="x")
        assert mgr._event_count == 1
        await mgr._on_event(event, source_key=None, source_exchange="x")
        assert mgr._event_count == 2

    @pytest.mark.asyncio
    async def test_non_dict_event_ignored(self):
        mgr = _make_mgr()
        await mgr._on_event("not a dict", source_key=None, source_exchange="x")
        assert mgr._event_count == 0

    @pytest.mark.asyncio
    async def test_source_key_overrides_event_key(self):
        mgr = _make_mgr()
        event = {"exchange": "x", "symbol": "Y", "best_bid": "1", "best_ask": "2", "ts_local": _now_ms()}
        await mgr._on_event(event, source_key="override:key", source_exchange="x")
        assert mgr.get_snapshot(key="override:key") is not None
        assert mgr.get_snapshot(exchange="x", symbol="Y") is None


# ===================================================================
# 10. Variational Event Handling
# ===================================================================


class TestVariationalEvents:
    @pytest.mark.asyncio
    async def test_variational_event_creates_snapshot(self):
        mgr = _make_mgr()
        event = {
            "exchange": "variational",
            "symbol": "ETH",
            "bid": "1800.0",
            "ask": "1801.0",
            "quote_id": "q42",
            "ts_local": _now_ms(),
        }
        await mgr._on_event(event, source_key=None, source_exchange="variational")
        snap = mgr.get_snapshot(exchange="variational", symbol="ETH")
        assert snap is not None
        assert snap.bid == 1800.0
        assert snap.ask == 1801.0
        assert snap.meta["quote_id"] == "q42"

    @pytest.mark.asyncio
    async def test_variational_event_without_bid_or_ask_skipped(self):
        mgr = _make_mgr()
        event = {
            "exchange": "variational",
            "symbol": "ETH",
            "bid": None,
            "ask": "1801.0",
            "ts_local": _now_ms(),
        }
        await mgr._on_event(event, source_key=None, source_exchange="variational")
        assert mgr.get_snapshot(exchange="variational", symbol="ETH") is None

    @pytest.mark.asyncio
    async def test_variational_instrument_symbol_extraction(self):
        mgr = _make_mgr()
        event = {
            "exchange": "variational",
            "instrument": {"underlying": "XAU"},
            "bid": "2000.0",
            "ask": "2001.0",
            "ts_local": _now_ms(),
        }
        await mgr._on_event(event, source_key="variational:XAU", source_exchange="variational")
        snap = mgr.get_snapshot(key="variational:XAU")
        assert snap is not None
        assert snap.symbol == "XAU"


# ===================================================================
# 11. Health / Metrics
# ===================================================================


class TestHealthMetrics:
    def test_get_health_empty(self):
        mgr = _make_mgr()
        health = mgr.get_health()
        assert health["source_count"] == 0
        assert health["snapshot_count"] == 0
        assert health["stale_count"] == 0

    def test_get_health_with_snapshots(self):
        mgr = _make_mgr(stale_ms=100)
        mgr.set_snapshot("k1", PriceSnapshot(exchange="e", bid=1.0, ask=2.0, ts_exchange=None, ts_local=_now_ms()))
        mgr.set_snapshot("k2", PriceSnapshot(exchange="e", bid=1.0, ask=2.0, ts_exchange=None, ts_local=_now_ms() - 500))
        health = mgr.get_health()
        assert health["snapshot_count"] == 2
        assert health["stale_count"] == 1
        assert "k2" in health["stale_keys"]

    def test_export_metrics(self):
        mgr = _make_mgr()
        mgr.set_snapshot("k", PriceSnapshot(exchange="e", bid=1.0, ask=2.0, ts_exchange=None, ts_local=_now_ms()))
        metrics = mgr.export_metrics()
        assert "market_data_snapshots" in metrics
        assert metrics["market_data_snapshots"] == 1
        assert metrics["market_data_event_count"] == 0


# ===================================================================
# 12. _coerce_float
# ===================================================================


class TestCoerceFloat:
    def test_none(self):
        assert MarketDataManager._coerce_float(None) is None

    def test_string_number(self):
        assert MarketDataManager._coerce_float("3.14") == pytest.approx(3.14)

    def test_int(self):
        assert MarketDataManager._coerce_float(42) == 42.0

    def test_invalid_string(self):
        assert MarketDataManager._coerce_float("not_a_number") is None

    def test_non_convertible(self):
        assert MarketDataManager._coerce_float(object()) is None


# ===================================================================
# 13. _event_key
# ===================================================================


class TestEventKey:
    def test_with_symbol(self):
        mgr = _make_mgr()
        assert mgr._event_key({"exchange": "bp", "symbol": "SOL"}, None) == "bp:SOL"

    def test_with_instrument_underlying(self):
        mgr = _make_mgr()
        event = {"exchange": "var", "instrument": {"underlying": "XAU"}}
        assert mgr._event_key(event, None) == "var:XAU"

    def test_with_instrument_symbol(self):
        mgr = _make_mgr()
        event = {"exchange": "var", "instrument": {"symbol": "XAU/USD"}}
        assert mgr._event_key(event, None) == "var:XAU/USD"

    def test_with_market_index(self):
        mgr = _make_mgr()
        assert mgr._event_key({"exchange": "lg", "market_index": 2}, None) == "lg:market_index=2"

    def test_fallback_to_source_exchange(self):
        mgr = _make_mgr()
        assert mgr._event_key({}, "fallback") == "fallback"

    def test_unknown_fallback(self):
        mgr = _make_mgr()
        assert mgr._event_key({}, None) == "unknown"
