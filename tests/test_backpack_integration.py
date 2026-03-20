"""Test Backpack WS integration with unified architecture."""
import asyncio
import json
from decimal import Decimal

import pytest

from exchanges.ws.dispatcher import create_dispatcher
from exchanges.ws.backpack import BackpackWS, BackpackUserWS
from exchanges.ws.types import EventType, OrderStatus, OrderSide
from conftest import MockWebsocket


@pytest.mark.asyncio
async def test_backpack_bbo_to_dispatcher():
    """Test Backpack BBO events flow through dispatcher."""
    # Setup
    dispatcher = create_dispatcher()

    events_received = []

    async def mock_on_event(event):
        events_received.append(event)
        await dispatcher.on_raw_event(event)

    ws_client = BackpackWS(
        symbols=["SOL_USDC"],
        on_event=mock_on_event,
        include_depth=False,  # BBO only
    )

    # Simulate connection
    mock_ws = MockWebsocket()
    await ws_client.on_connect(mock_ws)

    # Simulate bookTicker message
    bookticker_msg = json.dumps({
        "stream": "bookTicker.SOL_USDC",
        "data": {
            "s": "SOL_USDC",
            "b": "98.50",      # Best bid
            "B": "100.0",      # Best bid size
            "a": "98.51",      # Best ask
            "A": "50.0",       # Best ask size
            "T": 1705834567890,  # Exchange timestamp
        }
    })

    await ws_client.handle_message(bookticker_msg, ts_local_ms=1705834567891)

    # Verify raw event
    assert len(events_received) == 1
    raw_event = events_received[0]

    assert raw_event["exchange"] == "backpack"
    assert raw_event["symbol"] == "SOL_USDC"
    assert raw_event["stream"] == "bbo"
    assert raw_event["ts_exchange"] == 1705834567890
    assert raw_event["ts_local"] == 1705834567891
    assert raw_event["bids"] == [[98.50, 100.0]]
    assert raw_event["asks"] == [[98.51, 50.0]]

    # Verify normalized event from dispatcher
    normalized = await asyncio.wait_for(
        dispatcher.get_market_data(),
        timeout=0.1
    )

    assert normalized.exchange == "backpack"
    assert normalized.symbol == "SOL/USDC"  # Normalized from SOL_USDC
    assert normalized.data.bid == Decimal("98.50")
    assert normalized.data.ask == Decimal("98.51")
    assert normalized.data.bid_size == Decimal("100.0")
    assert normalized.data.ask_size == Decimal("50.0")
    assert normalized.metadata.event_type == EventType.BBO_UPDATE
    assert normalized.metadata.latency_ms == 1  # 1705834567891 - 1705834567890

    # Verify spread calculation
    assert normalized.data.spread == Decimal("0.01")
    spread_bps = normalized.data.spread_bps
    assert 0 < spread_bps < 2  # Should be ~1.01 bps


@pytest.mark.asyncio
async def test_backpack_depth_to_dispatcher():
    """Test Backpack depth (L2) events flow through dispatcher."""
    dispatcher = create_dispatcher()

    events_received = []

    async def mock_on_event(event):
        events_received.append(event)
        await dispatcher.on_raw_event(event)

    ws_client = BackpackWS(
        symbols=["BTC_USDC"],
        on_event=mock_on_event,
        include_depth=True,
    )

    mock_ws = MockWebsocket()
    await ws_client.on_connect(mock_ws)

    # Simulate depth message
    depth_msg = json.dumps({
        "stream": "depth.BTC_USDC",
        "data": {
            "s": "BTC_USDC",
            "b": [
                ["45000.00", "1.5"],
                ["44999.00", "2.0"],
                ["44998.00", "0.5"],
            ],
            "a": [
                ["45001.00", "1.2"],
                ["45002.00", "0.8"],
            ],
            "E": 1705834567900,  # Exchange timestamp
        }
    })

    await ws_client.handle_message(depth_msg, ts_local_ms=1705834567905)

    # Verify raw event
    assert len(events_received) == 1
    raw_event = events_received[0]

    assert raw_event["exchange"] == "backpack"
    assert raw_event["symbol"] == "BTC_USDC"
    assert raw_event["stream"] == "l2"
    assert len(raw_event["bids"]) == 3
    assert len(raw_event["asks"]) == 2
    assert raw_event["bids"][0] == [45000.00, 1.5]  # Best bid

    # Verify normalized event
    normalized = await asyncio.wait_for(
        dispatcher.get_market_data(),
        timeout=0.1
    )

    assert normalized.exchange == "backpack"
    assert normalized.symbol == "BTC/USDC"
    assert normalized.data.bid == Decimal("45000.00")
    assert normalized.data.ask == Decimal("45001.00")
    assert normalized.data.bid_size == Decimal("1.5")
    assert normalized.data.ask_size == Decimal("1.2")


@pytest.mark.asyncio
async def test_backpack_user_order_update():
    """Test Backpack user order updates flow through dispatcher."""
    dispatcher = create_dispatcher()

    events_received = []

    async def mock_on_event(event):
        events_received.append(event)
        await dispatcher.on_raw_event(event)

    # Mock API key/secret (won't actually connect)
    ws_client = BackpackUserWS(
        api_key="test_key",
        secret="dGVzdF9zZWNyZXRfa2V5X2Jhc2U2NA==",  # base64: test_secret_key_base64
        on_event=mock_on_event,
    )

    mock_ws = MockWebsocket()
    await ws_client.on_connect(mock_ws)

    # Simulate order update message
    order_msg = json.dumps({
        "stream": "account.orderUpdate",
        "data": {
            "orderId": 123456,
            "clientOrderId": "789",
            "symbol": "SOL_USDC",
            "side": "Buy",
            "orderType": "Limit",
            "status": "Filled",
            "quantity": "10.0",
            "executedQuantity": "10.0",
            "price": "98.50",
            "timeInForce": "GTC",
            "E": 1705834567900,
        }
    })

    await ws_client.handle_message(order_msg, ts_local_ms=1705834567905)

    # Verify raw event
    assert len(events_received) == 1
    raw_event = events_received[0]

    assert raw_event["exchange"] == "backpack"
    assert raw_event["stream"] == "user"
    assert raw_event["event_type"] == "ORDER_UPDATE"
    assert raw_event["type"] == "order"
    assert raw_event["symbol"] == "SOL_USDC"
    assert raw_event["order_id"] == "123456"
    assert raw_event["client_order_id"] == "789"  # clientOrderId from data
    assert raw_event["side"] == "Buy"
    assert raw_event["status"] == "Filled"
    assert raw_event["orig_qty"] == "10.0"
    assert raw_event["filled_qty"] == "10.0"
    assert raw_event["price"] == "98.50"

    # Verify normalized order update
    normalized = await asyncio.wait_for(
        dispatcher.get_order_update(),
        timeout=0.1
    )

    assert normalized.exchange == "backpack"
    assert normalized.symbol == "SOL/USDC"
    assert normalized.data.order_id == "123456"
    assert normalized.data.client_order_id == "789"
    assert normalized.data.status == OrderStatus.FILLED
    assert normalized.data.side == OrderSide.BUY  # "Buy" -> BUY
    assert normalized.data.price == Decimal("98.50")
    assert normalized.data.amount == Decimal("10.0")
    assert normalized.data.filled == Decimal("10.0")
    assert normalized.data.remaining == Decimal("0.0")
    assert normalized.metadata.event_type == EventType.ORDER_UPDATE


@pytest.mark.asyncio
async def test_backpack_user_fill_update():
    """Test Backpack fill updates flow through dispatcher."""
    dispatcher = create_dispatcher()

    events_received = []

    async def mock_on_event(event):
        events_received.append(event)
        await dispatcher.on_raw_event(event)

    ws_client = BackpackUserWS(
        api_key="test_key",
        secret="dGVzdF9zZWNyZXRfa2V5X2Jhc2U2NA==",
        on_event=mock_on_event,
    )

    mock_ws = MockWebsocket()
    await ws_client.on_connect(mock_ws)

    # Simulate fill update message
    fill_msg = json.dumps({
        "stream": "account.fillUpdate",
        "data": {
            "orderId": 123456,
            "clientOrderId": "789",
            "symbol": "SOL_USDC",
            "side": "Sell",
            "price": "98.75",      # Fill price
            "quantity": "5.0",     # Fill quantity
            "E": 1705834567900,
        }
    })

    await ws_client.handle_message(fill_msg, ts_local_ms=1705834567905)

    # Verify raw event
    assert len(events_received) == 1
    raw_event = events_received[0]

    assert raw_event["exchange"] == "backpack"
    assert raw_event["stream"] == "user"
    assert raw_event["event_type"] == "FILL_UPDATE"
    assert raw_event["type"] == "trade"
    assert raw_event["symbol"] == "SOL_USDC"
    assert raw_event["order_id"] == "123456"
    assert raw_event["last_price"] == "98.75"  # Fill price
    assert raw_event["last_qty"] == "5.0"      # Fill quantity

    # Verify normalized fill update
    normalized = await asyncio.wait_for(
        dispatcher.get_order_update(),
        timeout=0.1
    )

    assert normalized.exchange == "backpack"
    assert normalized.symbol == "SOL/USDC"
    assert normalized.data.order_id == "123456"
    assert normalized.data.side == OrderSide.SELL
    assert normalized.data.fill_price == Decimal("98.75")
    assert normalized.data.filled_amount == Decimal("5.0")
    assert normalized.metadata.event_type == EventType.FILL_UPDATE


def test_backpack_parse_levels():
    """Test _parse_levels helper function."""
    from exchanges.ws.backpack import _parse_levels

    # Valid levels
    levels = [
        ["100.5", "10.0"],
        ["100.0", "5.5"],
        ["99.5", "3.2"],
    ]
    result = _parse_levels(levels)
    assert result == [[100.5, 10.0], [100.0, 5.5], [99.5, 3.2]]

    # Invalid levels (should be filtered out)
    levels_with_invalid = [
        ["100.5", "10.0"],
        ["invalid", "5.0"],  # Invalid price
        ["100.0", "abc"],    # Invalid size
        ["99.5", "3.2"],
    ]
    result = _parse_levels(levels_with_invalid)
    assert result == [[100.5, 10.0], [99.5, 3.2]]

    # Empty
    assert _parse_levels([]) == []


def test_backpack_parse_book_ticker():
    """Test _parse_book_ticker helper function."""
    from exchanges.ws.backpack import _parse_book_ticker

    # Valid bookTicker
    data = {
        "b": "98.50",
        "B": "100.0",
        "a": "98.51",
        "A": "50.0",
    }
    result = _parse_book_ticker(data)
    assert result == (98.50, 100.0, 98.51, 50.0)

    # Missing fields
    assert _parse_book_ticker({"b": "98.50"}) is None
    assert _parse_book_ticker({}) is None

    # Invalid values
    assert _parse_book_ticker({
        "b": "invalid",
        "B": "100.0",
        "a": "98.51",
        "A": "50.0",
    }) is None


if __name__ == "__main__":
    # Run simple test
    asyncio.run(test_backpack_bbo_to_dispatcher())
    print("✅ All Backpack integration tests passed!")
