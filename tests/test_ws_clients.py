import asyncio
import json

from api.ws import AsterWS, BackpackWS


def _run(coro):
    asyncio.run(coro)


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
