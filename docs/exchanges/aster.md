# Aster Exchange Integration Guide

## Overview

Aster is a Binance-style futures DEX with full WebSocket support for market data and user streams.

**Key Characteristics:**
- **Authentication:** HMAC-SHA256 signatures
- **Symbol Format:** Lowercase (e.g., `xauusdt`, `btcusdt`)
- **WebSocket Protocol:** Binance-compatible streams
- **API Base URL:** `https://fapi.asterdex.com`
- **Market Data WS:** `wss://fstream.asterdex.com/stream`
- **User Data WS:** `wss://fstream.asterdex.com/ws/<listenKey>`

---

## Authentication

Aster uses **HMAC-SHA256 signatures** similar to Binance Futures.

### Implementation

Located in `exchanges/auth/aster.py`:

```python
from exchanges.auth.aster import sign_request

params = {
    "symbol": "XAUUSDT",
    "side": "BUY",
    "quantity": "0.1",
    "timestamp": 1768490299726
}
signature = sign_request(params, secret_key)
```

### Requirements
- HMAC-SHA256 signature of sorted query string
- Timestamp parameter required (13-digit milliseconds)
- Signature appended to request parameters

---

## REST API Client

### Basic Usage

```python
from exchanges import get_client

client = get_client("aster", {
    "apiKey": "your_api_key",
    "secret": "your_secret"
})

# Fetch ticker
ticker = client.fetch_ticker("XAUUSDT")

# Create order
order = client.create_order("XAUUSDT", "limit", "buy", 0.1, 2875.0)

# Set leverage
client.set_leverage(10, "XAUUSDT")
```

### Symbol Format

- **Perpetuals:** Lowercase, no separator (e.g., `xauusdt`, `btcusdt`, `ethusdt`)

---

## WebSocket Clients

Aster provides **three WebSocket client types** for different use cases:

### 1. AsterWS - Incremental Updates (High-Frequency)

**Use Case:** High-frequency trading requiring minimal latency

**Characteristics:**
- Pushes only changed orderbook levels
- Latency < 10ms
- Requires client-side orderbook maintenance

```python
from exchanges.ws import AsterWS

ws = AsterWS(
    symbols=['xauusdt', 'btcusdt'],
    on_event=on_event
)
await ws.run_forever()
```

**WebSocket URL:**
```
wss://fstream.asterdex.com/stream?streams=xauusdt@depth/btcusdt@depth
```

**Message Format:**
```json
{
  "stream": "xauusdt@depth",
  "data": {
    "e": "depthUpdate",
    "E": 1768490299726,
    "s": "XAUUSDT",
    "U": 167043001,
    "u": 167043010,
    "b": [["2875.50", "1.5"], ["2875.40", "0"]],
    "a": [["2875.60", "2.0"]]
  }
}
```

**Important:** Quantity `"0"` means remove that price level.

### 2. AsterDepthWS - Full Snapshots (Recommended)

**Use Case:** General trading, no state maintenance required

**Characteristics:**
- Pushes complete orderbook snapshot every 250ms
- Supports 5/10/20 depth levels
- No initialization required

```python
from exchanges.ws import AsterDepthWS

ws = AsterDepthWS(
    symbols=['xauusdt'],
    on_event=on_event,
    depth_level=20  # Options: 5, 10, 20
)
await ws.run_forever()
```

**WebSocket URL:**
```
wss://fstream.asterdex.com/stream?streams=xauusdt@depth20
```

**Message Format:**
```json
{
  "stream": "xauusdt@depth20",
  "data": {
    "lastUpdateId": 167043010,
    "bids": [["2875.50", "10.5"], ["2875.40", "5.2"]],
    "asks": [["2875.60", "8.3"], ["2875.70", "12.1"]]
  }
}
```

### 3. AsterUserWS - User Data Stream

**Use Case:** Account monitoring, order/position updates

**Requires Authentication**

```python
from exchanges.ws import AsterUserWS

ws = AsterUserWS(
    api_key="your_api_key",
    on_event=on_event
)
await ws.run_forever()
```

**Authentication Flow:**
1. POST to `/fapi/v1/listenKey` to get listen key
2. Connect to `wss://fstream.asterdex.com/ws/<listenKey>`
3. Keep-alive every 30 minutes (PUT `/fapi/v1/listenKey`)

**Supported Events:**
- `ORDER_TRADE_UPDATE` - Order status changes
- `ACCOUNT_UPDATE` - Balance and position updates

---

## Client Selection Guide

| Scenario | Recommended Client | Reason |
|----------|-------------------|--------|
| General trading | `AsterDepthWS` | No state maintenance, easy to use |
| Market making | `AsterWS` | Lowest latency, captures every change |
| High-frequency arbitrage | `AsterWS` | Real-time incremental updates |
| Account monitoring | `AsterUserWS` | Private data stream |
| Portfolio tracking | `AsterDepthWS` + `AsterUserWS` | Combination of market + account data |

---

## Known Issues & Considerations

### ⚠️ Known Issues

**1. URL Path Duplication (Fixed)**
- Early versions had `base_url` including `/api/v1`
- Caused requests to `/api/v1/api/v1/endpoint`
- **Current Status:** ✅ Fixed in latest version

**2. timeInForce Parameter**
- Required field but wasn't properly handled in early versions
- **Current Status:** ✅ Properly handled with default `GTC`

**3. amount_to_precision Precision Bug**
- Early implementation had rounding errors
- **Current Status:** ✅ Fixed with Decimal-based precision

### ✅ Strengths
- Full Binance-compatible API
- Complete WebSocket support (market + user data)
- Leverage control available
- Accurate price feeds
- Active development and bug fixes

---

## Message Format Examples

### Incremental Update
```json
{
  "stream": "xauusdt@depth",
  "data": {
    "e": "depthUpdate",
    "E": 1768490299726,
    "s": "XAUUSDT",
    "U": 167043001,
    "u": 167043010,
    "b": [["2875.50", "1.5"]],
    "a": [["2875.60", "2.0"]]
  }
}
```

### Order Update
```json
{
  "e": "ORDER_TRADE_UPDATE",
  "T": 1768490299726,
  "o": {
    "s": "XAUUSDT",
    "c": "client_order_id",
    "S": "BUY",
    "o": "LIMIT",
    "q": "0.1",
    "p": "2875.00",
    "X": "FILLED",
    "i": 12345,
    "l": "0.1",
    "z": "0.1",
    "n": "0.0001"
  }
}
```

---

## Integration Checklist

- [ ] Configure HMAC-SHA256 authentication
- [ ] Verify symbol format (lowercase)
- [ ] Choose appropriate WebSocket client type
- [ ] Implement listenKey management for user stream
- [ ] Handle orderbook update sequence validation (for AsterWS)
- [ ] Test leverage setting functionality
- [ ] Monitor for precision errors in order amounts

---

## References

- Implementation: `exchanges/aster.py`
- WebSocket: `exchanges/ws/aster.py`
- Authentication: `exchanges/auth/aster.py`
- Abstract API: `exchanges/endpoints/aster.py`
