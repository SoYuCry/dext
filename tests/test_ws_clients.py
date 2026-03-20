import asyncio
import json

from exchanges.ws import AsterWS, BackpackWS, LighterWS


def _run(coro):
    asyncio.run(coro)


class DummyWS:
    def __init__(self):
        self.sent = []
        self.closed = False

    async def send(self, payload):
        self.sent.append(payload)

    async def close(self):
        self.closed = True


def test_backpack_bookticker_parsing():
    events = []

    async def on_event(evt):
        events.append(evt)

    ws = BackpackWS(["BTC_USDC"], on_event, include_depth=False)

    payload = json.dumps(
        {
            "stream": "bookTicker.BTC_USDC",
            "data": {"b": "100.5", "B": "1.2", "a": "101.0", "A": "2.3", "T": 1700000000000},
        }
    )
    _run(ws.handle_message(payload, ts_local_ms=1700000000001))

    assert len(events) == 1
    evt = events[0]
    assert evt["exchange"] == "backpack"
    assert evt["symbol"] == "BTC_USDC"
    assert evt["stream"] == "bbo"
    assert evt["bids"][0][0] == 100.5
    assert evt["asks"][0][0] == 101.0


def test_backpack_depth_parsing():
    events = []

    async def on_event(evt):
        events.append(evt)

    ws = BackpackWS(["ETH_USDC"], on_event, include_depth=True)
    payload = json.dumps(
        {
            "stream": "depth.ETH_USDC",
            "data": {
                "b": [["2000.1", "0.5"]],
                "a": [["2001.2", "0.4"]],
                "T": 1700000000000,
            },
        }
    )
    _run(ws.handle_message(payload, ts_local_ms=1700000000002))
    assert len(events) == 1
    evt = events[0]
    assert evt["stream"] == "l2"
    assert evt["bids"][0] == [2000.1, 0.5]
    assert evt["asks"][0] == [2001.2, 0.4]


def test_aster_depth_parsing():
    events = []

    async def on_event(evt):
        events.append(evt)

    ws = AsterWS(["XAUUSDT"], on_event)
    payload = json.dumps(
        {
            "data": {
                "s": "XAUUSDT",
                "b": [["2300.5", "1.0"]],
                "a": [["2301.0", "2.0"]],
                "E": 1700000000000,
            }
        }
    )
    _run(ws.handle_message(payload, ts_local_ms=1700000000003))
    assert len(events) == 1
    evt = events[0]
    assert evt["exchange"] == "aster"
    assert evt["symbol"] == "XAUUSDT"
    assert evt["stream"] == "l2"
    assert evt["bids"][0] == [2300.5, 1.0]
    assert evt["asks"][0] == [2301.0, 2.0]


def test_lighter_orderbook_parsing():
    events = []

    async def on_event(evt):
        events.append(evt)

    ws = LighterWS(market_index=0, on_event=on_event)

    snapshot = json.dumps(
        {
            "type": "subscribed/order_book",
            "order_book": {
                "code": "ETH_USDC",
                "offset": 10,
                "bids": [{"price": "2500.0", "size": "1.0"}],
                "asks": [{"price": "2501.0", "size": "2.0"}],
            },
        }
    )
    update = json.dumps(
        {
            "type": "update/order_book",
            "order_book": {
                "code": "ETH_USDC",
                "offset": 11,
                "bids": [{"price": "2500.0", "size": "1.5"}],
                "asks": [{"price": "2501.0", "size": "1.0"}],
            },
        }
    )

    _run(ws.handle_message(snapshot, ts_local_ms=1700000000000))
    _run(ws.handle_message(update, ts_local_ms=1700000000100))

    assert len(events) == 1
    evt = events[0]
    assert evt["exchange"] == "lighter"
    assert evt["stream"] == "l2"
    assert evt["symbol"] == "ETH_USDC"
    assert evt["best_bid"] == 2500.0
    assert evt["best_ask"] == 2501.0
    assert evt["bids"][0] == [2500.0, 1.5]
    assert evt["asks"][0] == [2501.0, 1.0]


def test_lighter_bbo_only_tracks_worse_prices():
    events = []

    async def on_event(evt):
        events.append(evt)

    ws = LighterWS(market_index=0, on_event=on_event, bbo_only=True)

    snapshot = json.dumps(
        {
            "type": "subscribed/order_book",
            "order_book": {
                "code": "ETH_USDC",
                "offset": 20,
                "bids": [{"price": "2500.0", "size": "1.0"}],
                "asks": [{"price": "2501.0", "size": "1.0"}],
            },
        }
    )
    worse_bbo_update = json.dumps(
        {
            "type": "update/order_book",
            "order_book": {
                "code": "ETH_USDC",
                "offset": 21,
                "bids": [{"price": "2499.5", "size": "0.8"}],
                "asks": [{"price": "2502.0", "size": "1.1"}],
            },
        }
    )

    _run(ws.handle_message(snapshot, ts_local_ms=1700000000000))
    _run(ws.handle_message(worse_bbo_update, ts_local_ms=1700000000100))

    assert len(events) == 1
    evt = events[0]
    assert evt["best_bid"] == 2499.5
    assert evt["best_ask"] == 2502.0


def test_lighter_bbo_only_ignores_sequence_gaps():
    events = []

    async def on_event(evt):
        events.append(evt)

    ws = LighterWS(market_index=0, on_event=on_event, bbo_only=True)

    snapshot = json.dumps(
        {
            "type": "subscribed/order_book",
            "order_book": {
                "code": "ETH_USDC",
                "offset": 100,
                "bids": [{"price": "2500.0", "size": "1.0"}],
                "asks": [{"price": "2501.0", "size": "1.0"}],
            },
        }
    )
    gap_update = json.dumps(
        {
            "type": "update/order_book",
            "order_book": {
                "code": "ETH_USDC",
                "offset": 120,  # large jump that would normally trigger resubscribe
                "bids": [{"price": "2499.0", "size": "0.9"}],
                "asks": [{"price": "2502.5", "size": "1.2"}],
            },
        }
    )

    _run(ws.handle_message(snapshot, ts_local_ms=1700000000000))
    _run(ws.handle_message(gap_update, ts_local_ms=1700000000100))

    # Gap should be tolerated and event emitted
    assert len(events) == 1
    evt = events[0]
    assert evt["best_bid"] == 2499.0
    assert evt["best_ask"] == 2502.5
    assert ws.order_book_offset == 120


def test_lighter_ping_pong():
    dummy = DummyWS()
    events = []

    async def on_event(evt):
        events.append(evt)

    ws = LighterWS(market_index=1, on_event=on_event)

    _run(ws.on_connect(dummy))
    _run(ws.handle_message(json.dumps({"type": "ping"}), ts_local_ms=1700000000200))

    assert not events
    assert dummy.sent
    assert json.loads(dummy.sent[0]).get("type") == "pong"
