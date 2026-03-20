"""Test Variational WS integration with unified architecture."""
import asyncio
import json
import time
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from exchanges.ws.dispatcher import create_dispatcher
from exchanges.ws.variational import (
    VariationalPricePoller,
    VariationalFillPoller,
    VariationalEventsWS,
    _format_instrument_symbol,
)
from exchanges.ws.types import EventType, OrderStatus, OrderSide
from conftest import MockWebsocket


class MockVariationalClient:
    """Mock Variational client for testing."""

    def __init__(self):
        self.quote_count = 0
        self.trade_count = 0

    def request_indicative_quote(self, qty, instrument=None):
        """Mock RFQ quote request."""
        self.quote_count += 1
        mock_response = Mock()
        mock_response.success = True
        mock_response.data = {
            "quote_id": f"quote_{self.quote_count}",
            "bid": Decimal("3250.50"),
            "ask": Decimal("3251.00"),
            "raw": {
                "quote_id": f"quote_{self.quote_count}",
                "bid": "3250.50",
                "ask": "3251.00",
                "instrument": instrument or {},
            }
        }
        return mock_response

    def fetch_trades(self, symbol=None, limit=50):
        """Mock fetch trades."""
        self.trade_count += 1
        mock_response = Mock()
        mock_response.data = {
            "transfers": [
                {
                    "transfer_id": f"transfer_{self.trade_count}",
                    "id": f"trade_{self.trade_count}",
                    "side": "buy",
                    "price": "3250.50",
                    "qty": "10.0",
                    "created_at": int(time.time() * 1000),
                }
            ]
        }
        return mock_response


@pytest.mark.asyncio
async def test_variational_price_poller_to_dispatcher():
    """Test Variational RFQ price polling flow through dispatcher."""
    # Setup
    dispatcher = create_dispatcher()

    events_received = []

    async def mock_on_event(event):
        events_received.append(event)
        await dispatcher.on_raw_event(event)

    mock_client = MockVariationalClient()
    instrument = {
        "underlying": "ETH",
        "settlement_asset": "USDC",
        "instrument_type": "perpetual",
    }

    poller = VariationalPricePoller(
        client=mock_client,
        instrument=instrument,
        qty=Decimal("10.0"),
        on_event=mock_on_event,
        interval=0.1,  # Fast polling for test
    )

    # Run one poll cycle
    poller_task = asyncio.create_task(poller.run_forever())

    # Wait for first event
    await asyncio.sleep(0.2)

    # Stop poller
    await poller.stop()
    await asyncio.wait_for(poller_task, timeout=1.0)

    # Verify raw event
    assert len(events_received) >= 1
    raw_event = events_received[0]

    assert raw_event["exchange"] == "variational"
    assert raw_event["stream"] == "rfq_quote"
    assert raw_event["bid"] == Decimal("3250.50")
    assert raw_event["ask"] == Decimal("3251.00")
    assert "quote_id" in raw_event
    assert raw_event["instrument"] == instrument
    assert "ts_local" in raw_event
    assert "latency_ms" in raw_event
    assert "raw" in raw_event

    # Verify normalized event from dispatcher
    normalized = await asyncio.wait_for(
        dispatcher.get_market_data(),
        timeout=0.1
    )

    assert normalized.exchange == "variational"
    assert normalized.symbol == "ETH/USDC"  # Normalized from instrument
    assert normalized.data.bid == Decimal("3250.50")
    assert normalized.data.ask == Decimal("3251.00")
    assert normalized.data.bid_size == Decimal("0")  # RFQ has no size
    assert normalized.data.ask_size == Decimal("0")
    assert normalized.metadata.event_type == EventType.BBO_UPDATE

    # Verify spread calculation
    assert normalized.data.spread == Decimal("0.50")
    spread_bps = normalized.data.spread_bps
    assert Decimal("1") < spread_bps < Decimal("2")  # Should be ~1.54 bps


@pytest.mark.asyncio
async def test_variational_fill_poller_to_dispatcher():
    """Test Variational fill polling flow through dispatcher."""
    # Setup
    dispatcher = create_dispatcher()

    events_received = []

    async def mock_on_event(event):
        events_received.append(event)
        await dispatcher.on_raw_event(event)

    mock_client = MockVariationalClient()

    poller = VariationalFillPoller(
        client=mock_client,
        on_event=mock_on_event,
        limit=50,
        interval=0.1,
    )

    # Run one poll cycle
    poller_task = asyncio.create_task(poller.run_forever())

    # Wait for first event
    await asyncio.sleep(0.2)

    # Stop poller
    await poller.stop()
    await asyncio.wait_for(poller_task, timeout=1.0)

    # Verify raw event
    assert len(events_received) >= 1
    raw_event = events_received[0]

    assert raw_event["exchange"] == "variational"
    assert raw_event["stream"] == "fills"
    assert raw_event["event_type"] == "FILL_UPDATE"
    assert "transfer_id" in raw_event
    assert "ts_local" in raw_event
    assert "raw" in raw_event

    # Verify normalized order update from dispatcher
    normalized = await asyncio.wait_for(
        dispatcher.get_order_update(),
        timeout=0.1
    )

    assert normalized.exchange == "variational"
    assert normalized.data.order_id == raw_event["transfer_id"]
    assert normalized.data.status == OrderStatus.FILLED  # RFQ fills are always FILLED
    assert normalized.metadata.event_type == EventType.FILL_UPDATE


@pytest.mark.asyncio
async def test_variational_fill_poller_deduplication():
    """Test Variational fill poller deduplicates transfer IDs."""
    events_received = []

    async def mock_on_event(event):
        events_received.append(event)

    # Mock client that returns same transfer twice
    mock_client = Mock()
    mock_response = Mock()
    mock_response.data = {
        "transfers": [
            {"transfer_id": "transfer_123", "price": "100"},
            {"transfer_id": "transfer_123", "price": "100"},  # Duplicate
            {"transfer_id": "transfer_456", "price": "200"},
        ]
    }
    mock_client.fetch_trades = Mock(return_value=mock_response)

    poller = VariationalFillPoller(
        client=mock_client,
        on_event=mock_on_event,
        interval=0.1,
    )

    # Run one poll cycle
    poller_task = asyncio.create_task(poller.run_forever())
    await asyncio.sleep(0.15)
    await poller.stop()
    await asyncio.wait_for(poller_task, timeout=1.0)

    # Should only receive 2 events (duplicate filtered)
    assert len(events_received) == 2
    assert events_received[0]["transfer_id"] == "transfer_123"
    assert events_received[1]["transfer_id"] == "transfer_456"


@pytest.mark.asyncio
async def test_variational_events_ws_trade():
    """Test Variational events WebSocket trade messages."""
    dispatcher = create_dispatcher()

    events_received = []

    async def mock_on_event(event):
        events_received.append(event)
        await dispatcher.on_raw_event(event)

    ws_client = VariationalEventsWS(
        on_event=mock_on_event,
        cookie="test_cookie",
        claims_token="test_claims",
    )

    # Simulate connection and subscription (subscribe sends claims token)
    mock_ws = MockWebsocket()
    await ws_client.on_connect(mock_ws)
    await ws_client.subscribe(mock_ws)

    # Verify claims token was sent
    assert len(mock_ws.sent_messages) == 1
    assert "test_claims" in mock_ws.sent_messages[0]

    # Simulate trade message
    trade_msg = json.dumps({
        "type": "trade",
        "data": {
            "id": "trade_12345",
            "side": "buy",
            "price": "3250.50",
            "qty": "10.0",
            "instrument": {
                "underlying": "ETH",
                "settlement_asset": "USDC",
                "instrument_type": "perpetual",
            },
            "mark_price": "3250.00",
            "created_at": 1705834567890,
            "role": "taker",
        }
    })

    await ws_client.handle_message(trade_msg, ts_local_ms=1705834567895)

    # Verify raw event
    assert len(events_received) == 1
    raw_event = events_received[0]

    assert raw_event["exchange"] == "variational"
    assert raw_event["stream"] == "events"
    assert raw_event["event_type"] == "trade"
    assert raw_event["trade_id"] == "trade_12345"
    assert raw_event["side"] == "buy"
    assert raw_event["price"] == "3250.50"
    assert raw_event["qty"] == "10.0"
    assert raw_event["symbol"] == "ETH_USDC_PERP"
    assert raw_event["mark_price"] == "3250.00"
    assert raw_event["created_at"] == 1705834567890
    assert raw_event["role"] == "taker"

    # Verify normalized order update
    normalized = await asyncio.wait_for(
        dispatcher.get_order_update(),
        timeout=0.1
    )

    assert normalized.exchange == "variational"
    assert normalized.symbol == "ETH/USDC"  # Normalized from ETH_USDC_PERP
    assert normalized.data.order_id == "trade_12345"
    assert normalized.data.side == OrderSide.BUY
    assert normalized.data.price == Decimal("3250.50")
    assert normalized.data.filled == Decimal("10.0")
    assert normalized.data.status == OrderStatus.FILLED
    assert normalized.metadata.event_type == EventType.FILL_UPDATE


def test_format_instrument_symbol():
    """Test _format_instrument_symbol helper function."""
    # Perpetual
    instrument = {
        "underlying": "ETH",
        "settlement_asset": "USDC",
        "instrument_type": "perpetual",
    }
    assert _format_instrument_symbol(instrument) == "ETH_USDC_PERP"

    # Non-perpetual (options, futures)
    instrument = {
        "underlying": "BTC",
        "settlement_asset": "USDC",
        "instrument_type": "option",
    }
    assert _format_instrument_symbol(instrument) == "BTC_USDC"

    # Missing fields
    assert _format_instrument_symbol({}) == ""
    assert _format_instrument_symbol(None) == ""
    assert _format_instrument_symbol("invalid") == "invalid"

    # Minimal instrument
    instrument = {
        "underlying": "SOL",
        "settlement_asset": "USDC",
    }
    assert _format_instrument_symbol(instrument) == "SOL_USDC"


@pytest.mark.asyncio
async def test_variational_price_poller_error_handling():
    """Test Variational price poller handles errors gracefully."""
    events_received = []

    async def mock_on_event(event):
        events_received.append(event)

    # Mock client that raises exception
    mock_client = Mock()
    mock_client.request_indicative_quote = Mock(side_effect=Exception("API Error"))

    instrument = {"underlying": "ETH", "settlement_asset": "USDC"}

    poller = VariationalPricePoller(
        client=mock_client,
        instrument=instrument,
        qty=Decimal("10.0"),
        on_event=mock_on_event,
        interval=0.1,
    )

    # Run poller - should not crash
    poller_task = asyncio.create_task(poller.run_forever())
    await asyncio.sleep(0.2)
    await poller.stop()
    await asyncio.wait_for(poller_task, timeout=1.0)

    # Should not emit any events due to errors
    assert len(events_received) == 0


@pytest.mark.asyncio
async def test_variational_price_poller_missing_bid_ask():
    """Test Variational price poller handles missing bid/ask."""
    events_received = []

    async def mock_on_event(event):
        events_received.append(event)

    # Mock client that returns quote without bid/ask
    mock_client = Mock()
    mock_response = Mock()
    mock_response.success = True
    mock_response.data = {
        "quote_id": "quote_123",
        # Missing bid/ask
        "raw": {},
    }
    mock_client.request_indicative_quote = Mock(return_value=mock_response)

    instrument = {"underlying": "ETH", "settlement_asset": "USDC"}

    poller = VariationalPricePoller(
        client=mock_client,
        instrument=instrument,
        qty=Decimal("10.0"),
        on_event=mock_on_event,
        interval=0.1,
    )

    # Run one cycle
    poller_task = asyncio.create_task(poller.run_forever())
    await asyncio.sleep(0.15)
    await poller.stop()
    await asyncio.wait_for(poller_task, timeout=1.0)

    # Should not emit events when bid/ask missing
    assert len(events_received) == 0


if __name__ == "__main__":
    # Run simple tests
    asyncio.run(test_variational_price_poller_to_dispatcher())
    print("✅ Variational price poller integration test passed!")

    asyncio.run(test_variational_fill_poller_to_dispatcher())
    print("✅ Variational fill poller integration test passed!")

    asyncio.run(test_variational_events_ws_trade())
    print("✅ Variational events WS integration test passed!")

    print("\n✅ All Variational integration tests passed!")
