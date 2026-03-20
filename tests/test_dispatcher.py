"""Tests for the WebSocket dispatcher (exchanges/ws/dispatcher.py)."""

import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

import pytest

from exchanges.ws.dispatcher import WSDispatcher, create_dispatcher
from exchanges.ws.normalizer import (
    AsterNormalizer,
    BackpackNormalizer,
    BinanceNormalizer,
    LighterNormalizer,
    Normalizer,
    VariationalNormalizer,
)
from exchanges.ws.types import (
    BBOData,
    BBOUpdate,
    EventMetadata,
    EventType,
    OrderData,
    OrderSide,
    OrderStatus,
    OrderUpdate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bbo_event(
    exchange: str = "backpack",
    stream: str = "bbo",
    symbol: str = "ETH_USDC",
    bid: str = "2000",
    ask: str = "2001",
) -> Dict[str, Any]:
    """Build a minimal raw BBO event dict understood by BackpackNormalizer."""
    return {
        "exchange": exchange,
        "stream": stream,
        "symbol": symbol,
        "bids": [[float(bid), 1.0]],
        "asks": [[float(ask), 1.0]],
        "ts_local": 1700000000000,
        "ts_exchange": 1700000000000,
    }


def _make_order_event(
    exchange: str = "backpack",
    stream: str = "account_orders",
    symbol: str = "ETH_USDC",
    order_id: str = "ord-1",
    status: str = "new",
    side: str = "buy",
) -> Dict[str, Any]:
    """Build a minimal raw order event dict understood by BackpackNormalizer."""
    return {
        "exchange": exchange,
        "stream": stream,
        "symbol": symbol,
        "order_id": order_id,
        "status": status,
        "side": side,
        "orig_qty": "1.0",
        "filled_qty": "0",
        "price": "2000",
        "ts_local": 1700000000000,
        "ts_exchange": 1700000000000,
    }


def _make_lighter_bbo_event(
    market_index: int = 0,
    bid: str = "2000",
    ask: str = "2001",
) -> Dict[str, Any]:
    return {
        "exchange": "lighter",
        "stream": "bbo",
        "market_index": market_index,
        "best_bid": bid,
        "best_ask": ask,
        "best_bid_size": "1",
        "best_ask_size": "1",
        "ts_local": 1700000000000,
        "ts_exchange": 1700000000000,
    }


class StubNormalizer(Normalizer):
    """A trivial normalizer for testing registration and routing."""

    def __init__(self, name: str = "stub") -> None:
        super().__init__(name)
        self.bbo_calls: List[Dict] = []
        self.order_calls: List[Dict] = []

    def normalize_symbol(self, raw_symbol: str, *, market_index: Optional[int] = None) -> str:
        return raw_symbol or "UNKNOWN"

    def normalize_order_status(self, raw_status: str) -> OrderStatus:
        return OrderStatus.OPEN

    def normalize_bbo(self, raw_event: Dict[str, Any]) -> Optional[BBOUpdate]:
        self.bbo_calls.append(raw_event)
        return BBOUpdate(
            exchange=self.exchange_name,
            symbol=raw_event.get("symbol", "TEST/USD"),
            data=BBOData(
                bid=Decimal("100"),
                ask=Decimal("101"),
                bid_size=Decimal("1"),
                ask_size=Decimal("1"),
            ),
            metadata=EventMetadata(
                ts_exchange=1700000000000,
                ts_local=1700000000000,
                event_type=EventType.BBO_UPDATE,
            ),
        )

    def normalize_order(self, raw_event: Dict[str, Any]) -> Union[OrderUpdate, None]:
        self.order_calls.append(raw_event)
        return OrderUpdate(
            exchange=self.exchange_name,
            symbol=raw_event.get("symbol", "TEST/USD"),
            data=OrderData(
                order_id="stub-1",
                client_order_id=None,
                status=OrderStatus.OPEN,
                side=OrderSide.BUY,
                price=Decimal("100"),
                amount=Decimal("1"),
                filled=Decimal("0"),
                remaining=Decimal("1"),
            ),
            metadata=EventMetadata(
                ts_exchange=1700000000000,
                ts_local=1700000000000,
                event_type=EventType.ORDER_UPDATE,
            ),
        )


# ---------------------------------------------------------------------------
# a. Basic routing
# ---------------------------------------------------------------------------

class TestBasicRouting:
    """Market data and order update events are routed to correct queues."""

    @pytest.mark.asyncio
    async def test_bbo_event_goes_to_market_data_queue(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_bbo_event(stream="bbo"))

        assert d.market_data_queue.qsize() == 1
        assert d.order_update_queue.qsize() == 0
        item = d.market_data_queue.get_nowait()
        assert isinstance(item, BBOUpdate)
        assert item.exchange == "backpack"

    @pytest.mark.asyncio
    async def test_l2_stream_goes_to_market_data_queue(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_bbo_event(stream="l2"))

        assert d.market_data_queue.qsize() == 1
        assert d.order_update_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_orderbook_stream_goes_to_market_data_queue(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_bbo_event(stream="orderbook"))

        assert d.market_data_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_rfq_quote_stream_goes_to_market_data_queue(self):
        d = WSDispatcher()
        stub = StubNormalizer("testrfq")
        d.register_normalizer("testrfq", stub)
        await d.on_raw_event({"exchange": "testrfq", "stream": "rfq_quote", "symbol": "X/Y"})
        assert d.market_data_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_account_orders_goes_to_order_update_queue(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_order_event(stream="account_orders"))

        assert d.order_update_queue.qsize() == 1
        assert d.market_data_queue.qsize() == 0
        item = d.order_update_queue.get_nowait()
        assert isinstance(item, OrderUpdate)
        assert item.exchange == "backpack"

    @pytest.mark.asyncio
    async def test_user_stream_goes_to_order_update_queue(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_order_event(stream="user"))

        assert d.order_update_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_fills_stream_goes_to_order_update_queue(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_order_event(stream="fills"))

        assert d.order_update_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_events_stream_goes_to_order_update_queue(self):
        d = WSDispatcher()
        stub = StubNormalizer("testex")
        d.register_normalizer("testex", stub)
        await d.on_raw_event({
            "exchange": "testex",
            "stream": "events",
            "symbol": "X/Y",
            "order_id": "1",
        })
        assert d.order_update_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_non_dict_event_ignored(self):
        d = WSDispatcher()
        await d.on_raw_event("not a dict")  # type: ignore
        assert d.market_data_queue.qsize() == 0
        assert d.order_update_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_missing_exchange_field_ignored(self):
        d = WSDispatcher()
        await d.on_raw_event({"stream": "bbo"})
        assert d.market_data_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_unknown_stream_ignored(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event({"exchange": "backpack", "stream": "unknown_stream"})
        assert d.market_data_queue.qsize() == 0
        assert d.order_update_queue.qsize() == 0


# ---------------------------------------------------------------------------
# b. Normalizer registration
# ---------------------------------------------------------------------------

class TestNormalizerRegistration:

    def test_register_normalizer_stores_by_lowercase_key(self):
        d = WSDispatcher()
        norm = StubNormalizer("MyExchange")
        d.register_normalizer("MyExchange", norm)
        assert "myexchange" in d.normalizers
        assert d.normalizers["myexchange"] is norm

    def test_register_multiple_normalizers(self):
        d = WSDispatcher()
        n1 = StubNormalizer("a")
        n2 = StubNormalizer("b")
        d.register_normalizer("A", n1)
        d.register_normalizer("B", n2)
        assert len(d.normalizers) == 2
        assert d.normalizers["a"] is n1
        assert d.normalizers["b"] is n2

    @pytest.mark.asyncio
    async def test_unknown_exchange_event_silently_dropped(self):
        d = WSDispatcher()
        # No normalizer registered for "unknown_ex"
        await d.on_raw_event({"exchange": "unknown_ex", "stream": "bbo"})
        assert d.market_data_queue.qsize() == 0
        assert d.order_update_queue.qsize() == 0
        # Stats should show no increment (event never reached normalizer)
        assert d.stats["market_data_received"] == 0

    @pytest.mark.asyncio
    async def test_registered_normalizer_is_called(self):
        d = WSDispatcher()
        stub = StubNormalizer("testex")
        d.register_normalizer("testex", stub)
        await d.on_raw_event({"exchange": "testex", "stream": "bbo", "symbol": "A/B"})
        assert len(stub.bbo_calls) == 1

    @pytest.mark.asyncio
    async def test_case_insensitive_exchange_matching(self):
        d = WSDispatcher()
        stub = StubNormalizer("testex")
        d.register_normalizer("TestEx", stub)
        await d.on_raw_event({"exchange": "TESTEX", "stream": "bbo", "symbol": "A/B"})
        assert len(stub.bbo_calls) == 1


# ---------------------------------------------------------------------------
# c. Filtering (set_filters / _should_process)
# ---------------------------------------------------------------------------

class TestFiltering:

    def test_no_filters_accepts_all(self):
        d = WSDispatcher()
        assert d._should_process("any_exchange", "ANY/SYMBOL") is True

    def test_filter_by_exchange_accepts_match(self):
        d = WSDispatcher()
        d.set_filters(exchanges=["backpack", "lighter"])
        assert d._should_process("backpack", "ETH/USDC") is True
        assert d._should_process("Lighter", "ETH/USDC") is True

    def test_filter_by_exchange_rejects_non_match(self):
        d = WSDispatcher()
        d.set_filters(exchanges=["backpack"])
        assert d._should_process("binance", "ETH/USDC") is False

    def test_filter_by_symbol_accepts_match(self):
        d = WSDispatcher()
        d.set_filters(symbols=["ETH/USDC", "BTC/USDC"])
        assert d._should_process("backpack", "ETH/USDC") is True
        assert d._should_process("backpack", "eth/usdc") is True  # case-insensitive

    def test_filter_by_symbol_rejects_non_match(self):
        d = WSDispatcher()
        d.set_filters(symbols=["ETH/USDC"])
        assert d._should_process("backpack", "SOL/USDC") is False

    def test_filter_by_both_exchange_and_symbol(self):
        d = WSDispatcher()
        d.set_filters(exchanges=["backpack"], symbols=["ETH/USDC"])
        assert d._should_process("backpack", "ETH/USDC") is True
        assert d._should_process("binance", "ETH/USDC") is False
        assert d._should_process("backpack", "SOL/USDC") is False

    @pytest.mark.asyncio
    async def test_filtered_bbo_event_not_enqueued(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        d.set_filters(symbols=["SOL/USDC"])  # ETH/USDC will be filtered out
        await d.on_raw_event(_make_bbo_event(symbol="ETH_USDC"))

        assert d.stats["market_data_received"] == 1
        assert d.stats["market_data_normalized"] == 0
        assert d.market_data_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_filtered_order_event_not_enqueued(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        d.set_filters(exchanges=["lighter"])  # backpack events filtered out
        await d.on_raw_event(_make_order_event())

        assert d.stats["order_updates_received"] == 1
        assert d.stats["order_updates_normalized"] == 0
        assert d.order_update_queue.qsize() == 0

    def test_set_filters_clears_previous(self):
        d = WSDispatcher()
        d.set_filters(exchanges=["a"])
        assert d.enabled_exchanges == {"a"}
        d.set_filters(exchanges=["b"])
        assert d.enabled_exchanges == {"b"}
        d.set_filters()  # clear all
        assert d.enabled_exchanges is None
        assert d.enabled_symbols is None


# ---------------------------------------------------------------------------
# d. Queue management
# ---------------------------------------------------------------------------

class TestQueueManagement:

    @pytest.mark.asyncio
    async def test_get_market_data_retrieves_from_queue(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_bbo_event())

        bbo = await asyncio.wait_for(d.get_market_data(), timeout=1.0)
        assert isinstance(bbo, BBOUpdate)
        assert bbo.exchange == "backpack"
        assert bbo.symbol == "ETH/USDC"

    @pytest.mark.asyncio
    async def test_get_order_update_retrieves_from_queue(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_order_event())

        update = await asyncio.wait_for(d.get_order_update(), timeout=1.0)
        assert isinstance(update, OrderUpdate)
        assert update.exchange == "backpack"

    @pytest.mark.asyncio
    async def test_market_data_queue_full_drops_event(self):
        d = WSDispatcher(market_data_queue_maxsize=1)
        d.register_normalizer("backpack", BackpackNormalizer())

        # Fill the queue
        await d.on_raw_event(_make_bbo_event(bid="100", ask="101"))
        assert d.market_data_queue.qsize() == 1
        assert d.stats["queue_full_drops"] == 0

        # This one should be dropped
        await d.on_raw_event(_make_bbo_event(bid="200", ask="201"))
        assert d.market_data_queue.qsize() == 1
        assert d.stats["queue_full_drops"] == 1

    @pytest.mark.asyncio
    async def test_order_update_queue_full_drops_event(self):
        d = WSDispatcher(order_update_queue_maxsize=1)
        d.register_normalizer("backpack", BackpackNormalizer())

        await d.on_raw_event(_make_order_event(order_id="o1"))
        assert d.order_update_queue.qsize() == 1
        assert d.stats["queue_full_drops"] == 0

        await d.on_raw_event(_make_order_event(order_id="o2"))
        assert d.order_update_queue.qsize() == 1
        assert d.stats["queue_full_drops"] == 1

    @pytest.mark.asyncio
    async def test_multiple_events_queued_in_order(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())

        await d.on_raw_event(_make_bbo_event(bid="100", ask="101"))
        await d.on_raw_event(_make_bbo_event(bid="200", ask="201"))

        first = d.market_data_queue.get_nowait()
        second = d.market_data_queue.get_nowait()
        assert first.data.bid == Decimal("100")
        assert second.data.bid == Decimal("200")


# ---------------------------------------------------------------------------
# e. Statistics
# ---------------------------------------------------------------------------

class TestStatistics:

    @pytest.mark.asyncio
    async def test_stats_track_market_data_received_and_normalized(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_bbo_event())

        assert d.stats["market_data_received"] == 1
        assert d.stats["market_data_normalized"] == 1

    @pytest.mark.asyncio
    async def test_stats_track_order_updates_received_and_normalized(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_order_event())

        assert d.stats["order_updates_received"] == 1
        assert d.stats["order_updates_normalized"] == 1

    @pytest.mark.asyncio
    async def test_stats_track_queue_full_drops(self):
        d = WSDispatcher(market_data_queue_maxsize=1)
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_bbo_event())
        await d.on_raw_event(_make_bbo_event())

        assert d.stats["queue_full_drops"] == 1

    @pytest.mark.asyncio
    async def test_stats_not_incremented_for_filtered_events(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        d.set_filters(symbols=["SOL/USDC"])
        await d.on_raw_event(_make_bbo_event(symbol="ETH_USDC"))

        assert d.stats["market_data_received"] == 1
        assert d.stats["market_data_normalized"] == 0

    def test_get_stats_includes_queue_sizes(self):
        d = WSDispatcher()
        stats = d.get_stats()
        assert "market_data_queue_size" in stats
        assert "order_update_queue_size" in stats
        assert stats["market_data_queue_size"] == 0
        assert stats["order_update_queue_size"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_reflects_queue_contents(self):
        d = WSDispatcher()
        d.register_normalizer("backpack", BackpackNormalizer())
        await d.on_raw_event(_make_bbo_event())
        await d.on_raw_event(_make_order_event())

        stats = d.get_stats()
        assert stats["market_data_queue_size"] == 1
        assert stats["order_update_queue_size"] == 1

    def test_initial_stats_are_zero(self):
        d = WSDispatcher()
        for key in (
            "market_data_received",
            "market_data_normalized",
            "order_updates_received",
            "order_updates_normalized",
            "normalization_errors",
            "queue_full_drops",
        ):
            assert d.stats[key] == 0

    def test_log_stats_does_not_raise(self):
        d = WSDispatcher()
        d.log_stats()  # should not raise


# ---------------------------------------------------------------------------
# f. create_dispatcher factory
# ---------------------------------------------------------------------------

class TestCreateDispatcher:

    def test_returns_dispatcher_instance(self):
        d = create_dispatcher()
        assert isinstance(d, WSDispatcher)

    def test_has_all_normalizers_registered(self):
        d = create_dispatcher()
        expected = {"lighter", "backpack", "binance", "variational", "aster"}
        assert set(d.normalizers.keys()) == expected

    def test_normalizer_types(self):
        d = create_dispatcher()
        assert isinstance(d.normalizers["lighter"], LighterNormalizer)
        assert isinstance(d.normalizers["backpack"], BackpackNormalizer)
        assert isinstance(d.normalizers["binance"], BinanceNormalizer)
        assert isinstance(d.normalizers["variational"], VariationalNormalizer)
        assert isinstance(d.normalizers["aster"], AsterNormalizer)

    def test_lighter_market_mapping_passed_through(self):
        mapping = {0: "ETH/USDC", 1: "BTC/USDC"}
        d = create_dispatcher(lighter_market_mapping=mapping)
        lighter_norm = d.normalizers["lighter"]
        assert isinstance(lighter_norm, LighterNormalizer)
        assert lighter_norm.market_index_to_symbol == mapping

    def test_lighter_market_mapping_defaults_to_empty(self):
        d = create_dispatcher()
        lighter_norm = d.normalizers["lighter"]
        assert isinstance(lighter_norm, LighterNormalizer)
        assert lighter_norm.market_index_to_symbol == {}

    @pytest.mark.asyncio
    async def test_factory_dispatcher_routes_lighter_bbo(self):
        mapping = {0: "ETH/USDC"}
        d = create_dispatcher(lighter_market_mapping=mapping)
        await d.on_raw_event(_make_lighter_bbo_event(market_index=0))

        assert d.market_data_queue.qsize() == 1
        bbo = d.market_data_queue.get_nowait()
        assert bbo.exchange == "lighter"
        assert bbo.symbol == "ETH/USDC"

    @pytest.mark.asyncio
    async def test_factory_dispatcher_routes_backpack_order(self):
        d = create_dispatcher()
        await d.on_raw_event(_make_order_event(exchange="backpack"))

        assert d.order_update_queue.qsize() == 1
        update = d.order_update_queue.get_nowait()
        assert update.exchange == "backpack"
