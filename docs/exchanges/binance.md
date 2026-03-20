# Binance Exchange Integration Guide

## Overview

Binance Spot provides a full REST API and WebSocket streams for market data and user events.

**Key Characteristics:**
- **Authentication:** HMAC-SHA256 signature with `timestamp` and API key header for signed endpoints.
- **Symbol Format:** Spot symbols are concatenated (e.g., `BTCUSDT`) in REST and WS payloads.
- **REST Base URL:** `https://api.binance.com` (Spot).
- **WebSocket Base URL:** `wss://stream.binance.com:9443` (combined streams).

---

## API Security Types

Binance Spot classifies endpoints by security type. This integration follows those categories:

- **NONE / Public**: Market data (no signature required).
- **SIGNED / Trade & User Data**: Requires `timestamp`, `signature`, and `X-MBX-APIKEY` header.
- **USER_STREAM**: ListenKey-based WS streams for private account events.

---

## Authentication

Implementation: `exchanges/auth/binance.py`

```python
from exchanges.auth.binance import sign_request

params = {
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "LIMIT",
    "quantity": "0.1",
    "timestamp": 1705834567890,
}
signature = sign_request("your_secret", params)
```

**Required fields for signed endpoints:**
- `timestamp` (milliseconds)
- `signature` (HMAC-SHA256)
- `X-MBX-APIKEY` header

---

## REST API Client

### Basic Usage

```python
from exchanges import get_client

client = get_client("binance", {
    "apiKey": "your_api_key",
    "secret": "your_secret",
})

# Fetch market data
ticker = client.fetch_ticker("BTC/USDT")
orderbook = client.fetch_order_book("BTC/USDT", limit=20)

# Trading
order = client.create_order("BTC/USDT", "limit", "buy", 0.1, 65000)
client.cancel_order(order["id"], "BTC/USDT")

# Account
balance = client.fetch_balance()
```

---

## Data Structure Examples (REST)

### Order Book (`GET /api/v3/depth`)

```json
{
  "lastUpdateId": 1027024,
  "bids": [
    ["4.00000000", "431.00000000"]
  ],
  "asks": [
    ["4.00000200", "12.00000000"]
  ]
}
```


### Symbol Order Book Ticker (`GET /api/v3/ticker/bookTicker`)

```json
{
  "symbol": "BTCUSDT",
  "bidPrice": "4.00000000",
  "bidQty": "431.00000000",
  "askPrice": "4.00000200",
  "askQty": "9.00000000"
}
```


### Create Order Response (`POST /api/v3/order`)

```json
{
  "symbol": "BTCUSDT",
  "orderId": 28,
  "orderListId": -1,
  "clientOrderId": "6gCrw2kRUAF9CvJDGP16IP",
  "transactTime": 1507725176595
}
```


### Account Info (`GET /api/v3/account`)

```json
{
  "makerCommission": 15,
  "takerCommission": 15,
  "buyerCommission": 0,
  "sellerCommission": 0,
  "canTrade": true,
  "canWithdraw": true,
  "canDeposit": true,
  "balances": [
    {
      "asset": "BTC",
      "free": "4723846.89208129",
      "locked": "0.00000000"
    },
    {
      "asset": "LTC",
      "free": "4763368.68006011",
      "locked": "0.00000000"
    }
  ]
}
```


---

## WebSocket Clients

### Market Data WS (Book Ticker + Depth)

```python
from exchanges.ws import BinanceWS

ws = BinanceWS(
    symbols=["BTCUSDT", "ETHUSDT"],
    on_event=on_event,
    include_depth=True,
    depth_level=5,
    depth_interval_ms=100,
)
await ws.run_forever()
```

**Book Ticker Stream (`<symbol>@bookTicker`)**

```json
{
  "u": 400900217,
  "s": "BNBUSDT",
  "b": "25.35190000",
  "B": "31.21000000",
  "a": "25.36520000",
  "A": "40.66000000"
}
```


**Partial Depth Stream (`<symbol>@depth5@100ms`)**

```json
{
  "lastUpdateId": 160,
  "bids": [
    ["0.0024", "10"]
  ],
  "asks": [
    ["0.0026", "100"]
  ]
}
```


---

## User Data Stream (ListenKey)

This integration uses the listenKey flow to receive private events via WebSocket.

```python
from exchanges.ws import BinanceUserWS

ws = BinanceUserWS(
    api_key="your_api_key",
    on_event=on_event,
)
await ws.run_forever()
```

### Execution Report (Order Updates)

```json
{
  "e": "executionReport",
  "E": 1499405658658,
  "s": "ETHBTC",
  "c": "mUvoqJxFIILMdfAW5iGSOW",
  "S": "BUY",
  "o": "LIMIT",
  "f": "GTC",
  "q": "1.00000000",
  "p": "0.10264410",
  "X": "NEW",
  "x": "NEW",
  "i": 4293153,
  "l": "0.00000000",
  "z": "0.00000000",
  "L": "0.00000000",
  "n": "0",
  "N": null,
  "T": 1499405658657
}
```


### Account Position Update

```json
{
  "e": "outboundAccountPosition",
  "E": 1564034571105,
  "u": 1564034571073,
  "B": [
    {
      "a": "ETH",
      "f": "10000.000000",
      "l": "0.000000"
    }
  ]
}
```


---

## Integration Checklist

- [ ] Add REST endpoints (`exchanges/endpoints/binance.py`)
- [ ] Implement signer (`exchanges/auth/binance.py`)
- [ ] Implement REST client (`exchanges/binance.py`)
- [ ] Implement WS market data (`exchanges/ws/binance.py`)
- [ ] Implement WS user stream (`exchanges/ws/binance.py`)
- [ ] Register normalizer + dispatcher (`exchanges/ws/normalizer.py`, `exchanges/ws/dispatcher.py`)
- [ ] Add config entries (`config.py`)
- [ ] Add tests (`tests/test_binance_integration.py`)
- [ ] Update docs (`CLAUDE.md`, `exchanges/README.md`, `docs/exchanges/binance.md`)

---

## References

- REST API (Spot): `binance-spot-api-docs/rest-api.md`
- WebSocket Streams: `binance-spot-api-docs/web-socket-streams.md`
- User Data Stream: Binance Spot user data stream docs (listenKey)
