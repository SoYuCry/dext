"""Test Lighter WS integration with unified architecture."""
import asyncio
import json
from decimal import Decimal

import pytest

from exchanges.ws.dispatcher import create_dispatcher
from exchanges.ws.lighter import LighterWS
from exchanges.ws.types import EventType, OrderStatus
from conftest import MockWebsocket


@pytest.mark.asyncio
async def test_lighter_bbo_to_dispatcher():
    """Test Lighter BBO events flow through dispatcher."""
    # Setup
    dispatcher = create_dispatcher(lighter_market_mapping={0: "ETH/USDC"})

    events_received = []

    async def mock_on_event(event):
        events_received.append(event)
        # Also send to dispatcher
        await dispatcher.on_raw_event(event)

    ws_client = LighterWS(
        market_index=0,
        on_event=mock_on_event,
        bbo_only=True,
    )

    # Simulate connection
    mock_ws = MockWebsocket()
    await ws_client.on_connect(mock_ws)

    # Simulate snapshot message
    snapshot_msg = json.dumps({
        "type": "subscribed/order_book",
        "order_book": {
            "offset": 100,
            "bids": [
                {"price": "3250.50", "size": "10.5"},
                {"price": "3250.00", "size": "5.0"},
            ],
            "asks": [
                {"price": "3251.00", "size": "8.2"},
                {"price": "3251.50", "size": "3.0"},
            ],
        }
    })

    await ws_client.handle_message(snapshot_msg, ts_local_ms=1705834567891)

    # Simulate update message
    update_msg = json.dumps({
        "type": "update/order_book",
        "order_book": {
            "offset": 101,
            "timestamp": 1705834567890,
            "code": "ETH_USDC",
            "bids": [
                {"price": "3250.75", "size": "12.0"},  # New best bid
            ],
            "asks": [],
        }
    })

    await ws_client.handle_message(update_msg, ts_local_ms=1705834567892)

    # Verify raw events
    assert len(events_received) == 1  # Only update event (snapshot doesn't emit)

    raw_event = events_received[0]
    assert raw_event["exchange"] == "lighter"
    assert raw_event["stream"] == "bbo"
    assert raw_event["market_index"] == 0
    assert raw_event["best_bid"] == 3250.75
    assert raw_event["best_ask"] == 3251.00  # From snapshot

    # Verify normalized event from dispatcher
    normalized = await asyncio.wait_for(
        dispatcher.get_market_data(),
        timeout=0.1
    )

    assert normalized.exchange == "lighter"
    assert normalized.symbol == "ETH/USDC"  # Mapped by dispatcher
    assert normalized.data.bid == Decimal("3250.75")
    assert normalized.data.ask == Decimal("3251.00")
    assert normalized.data.bid_size == Decimal("12.0")
    assert normalized.data.ask_size == Decimal("8.2")
    assert normalized.metadata.event_type == EventType.BBO_UPDATE
    assert normalized.metadata.latency_ms >= 0

    # Verify spread calculation
    assert normalized.data.spread == Decimal("0.25")
    spread_bps = normalized.data.spread_bps
    assert 0 < spread_bps < 10  # Should be ~0.77 bps


@pytest.mark.asyncio
async def test_lighter_orders_to_dispatcher():
    """Test Lighter account orders flow through dispatcher."""
    dispatcher = create_dispatcher(lighter_market_mapping={0: "ETH/USDC"})

    events_received = []

    async def mock_on_event(event):
        events_received.append(event)
        await dispatcher.on_raw_event(event)

    ws_client = LighterWS(
        market_index=0,
        on_event=mock_on_event,
        account_index=0,
        lighter_client=None,  # Mock
    )

    mock_ws = MockWebsocket()
    await ws_client.on_connect(mock_ws)

    # Simulate order update
    order_msg = json.dumps({
        "type": "update/account_orders",
        "timestamp": 1705834567890,
        "orders": {
            "0": [
                {
                    "order_index": "12345",
                    "client_order_index": 100,
                    "status": "filled",
                    "is_ask": False,
                    "price": "3250.50",
                    "initial_base_amount": "10.0",
                    "filled_base_amount": "10.0",
                    "remaining_base_amount": "0.0",
                    "filled_quote_amount": "32505.0",
                }
            ]
        }
    })

    await ws_client.handle_message(order_msg, ts_local_ms=1705834567895)

    # Verify raw event
    assert len(events_received) == 1
    raw_event = events_received[0]
    assert raw_event["exchange"] == "lighter"
    assert raw_event["stream"] == "account_orders"
    assert len(raw_event["orders"]) == 1

    # Verify fill_price was calculated
    order = raw_event["orders"][0]
    assert "fill_price" in order
    assert order["fill_price"] == 3250.5  # 32505.0 / 10.0

    # Verify normalized order from dispatcher
    normalized = await asyncio.wait_for(
        dispatcher.get_order_update(),
        timeout=0.1
    )

    assert normalized.exchange == "lighter"
    assert normalized.symbol == "ETH/USDC"
    assert normalized.data.order_id == "12345"
    assert normalized.data.client_order_id == "100"
    assert normalized.data.status == OrderStatus.FILLED
    assert normalized.data.side.value == "buy"
    assert normalized.data.price == Decimal("3250.50")
    assert normalized.data.filled == Decimal("10.0")
    assert normalized.data.remaining == Decimal("0.0")
    assert normalized.data.fill_price == Decimal("3250.5")
    assert normalized.metadata.event_type == EventType.FILL_UPDATE


@pytest.mark.asyncio
async def test_lighter_sequence_gap_recovery():
    """Test sequence gap detection triggers snapshot refresh."""
    events_received = []

    async def mock_on_event(event):
        events_received.append(event)

    ws_client = LighterWS(
        market_index=0,
        on_event=mock_on_event,
        bbo_only=False,
    )

    mock_ws = MockWebsocket()
    await ws_client.on_connect(mock_ws)

    # Snapshot with offset 100
    snapshot = json.dumps({
        "type": "subscribed/order_book",
        "order_book": {
            "offset": 100,
            "bids": [{"price": "3250", "size": "10"}],
            "asks": [{"price": "3251", "size": "10"}],
        }
    })
    await ws_client.handle_message(snapshot, ts_local_ms=1000)

    # Normal update (offset 101)
    update1 = json.dumps({
        "type": "update/order_book",
        "order_book": {
            "offset": 101,
            "bids": [{"price": "3250.5", "size": "5"}],
            "asks": [],
        }
    })
    await ws_client.handle_message(update1, ts_local_ms=1001)

    assert len(events_received) == 1  # One valid update

    # Gap! Jump from 101 to 110 (gap > max_offset_skip)
    update2 = json.dumps({
        "type": "update/order_book",
        "order_book": {
            "offset": 110,
            "bids": [{"price": "3251", "size": "20"}],
            "asks": [],
        }
    })
    await ws_client.handle_message(update2, ts_local_ms=1002)

    # Should NOT emit event due to sequence gap
    assert len(events_received) == 1  # Still only 1 event

    # Verify unsubscribe + subscribe was sent
    assert len(mock_ws.sent_messages) >= 2

    # Find unsubscribe and subscribe messages
    messages = [json.loads(msg) for msg in mock_ws.sent_messages]
    unsub = next((m for m in messages if m.get("type") == "unsubscribe"), None)
    sub = next((m for m in messages if m.get("type") == "subscribe"), None)

    assert unsub is not None
    assert sub is not None
    assert "order_book/0" in unsub.get("channel", "")


def test_lighter_bbo_only_update_logic():
    """Test BBO-only mode updates correctly."""
    ws_client = LighterWS(
        market_index=0,
        on_event=lambda e: None,
        bbo_only=True,
    )

    # Initial state
    assert ws_client.best_bid is None
    assert ws_client.best_ask is None

    # Update bids
    ws_client._update_bbo_only("bids", [
        {"price": "100", "size": "10"},
        {"price": "99", "size": "20"},
        {"price": "101", "size": "5"},  # This should be best
    ])

    assert ws_client.best_bid == 101.0
    assert ws_client.best_bid_size == 5.0

    # Update asks
    ws_client._update_bbo_only("asks", [
        {"price": "102", "size": "8"},  # This should be best
        {"price": "103", "size": "12"},
    ])

    assert ws_client.best_ask == 102.0
    assert ws_client.best_ask_size == 8.0

    # Remove current best bid
    ws_client._update_bbo_only("bids", [
        {"price": "101", "size": "0"},  # Remove
    ])

    # Should clear best bid since we removed it
    assert ws_client.best_bid is None
    assert ws_client.best_bid_size is None


if __name__ == "__main__":
    # Run simple test
    asyncio.run(test_lighter_bbo_to_dispatcher())
    print("✅ All Lighter integration tests passed!")
