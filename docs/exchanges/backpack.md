# Backpack Exchange Integration Guide

## Overview

Backpack is a centralized exchange supporting spot and perpetual futures trading with full WebSocket support.

**Key Characteristics:**
- **Authentication:** Ed25519 signatures (base64-encoded secret key)
- **Symbol Format:** Underscore separator (e.g., `SOL_USDC`, `PAXG_USDC_PERP`)
- **WebSocket Protocol:** JSON-RPC style (SUBSCRIBE/UNSUBSCRIBE)
- **API Base URL:** `https://api.backpack.exchange`

---

## Authentication

Backpack uses **Ed25519 signatures** for API authentication.

### Implementation

Located in `exchanges/auth/backpack.py`:

```python
from exchanges.auth.backpack import create_signature

# Create signature for API requests
secret_key = "base64_encoded_secret"
message = f"instruction=subscribe&timestamp={timestamp}&window={window}"
signature = create_signature(secret_key, message)
```

### Requirements
- `nacl` library for Ed25519 signing
- Secret key must be base64-decoded before signing
- Timestamp window validation (default: 5000ms)

---

## REST API Client

### Basic Usage

```python
from exchanges import get_client

client = get_client("backpack", {
    "apiKey": "your_api_key",
    "secret": "your_base64_secret"
})

# Fetch ticker
ticker = client.fetch_ticker("SOL_USDC")

# Create order
order = client.create_order("SOL_USDC", "limit", "buy", 1.0, 100.0)

# Fetch positions
positions = client.fetch_positions()
```

### Symbol Format

- **Spot:** `{BASE}_{QUOTE}` (e.g., `SOL_USDC`)
- **Perpetuals:** `{BASE}_{QUOTE}_PERP` (e.g., `BTC_USDC_PERP`)

---

## WebSocket Clients

### Market Data WebSocket

**Endpoint:** `wss://ws.backpack.exchange`

```python
from exchanges.ws import BackpackWS

ws = BackpackWS(
    symbols=["SOL_USDC", "PAXG_USDC_PERP"],
    on_event=on_event
)
await ws.run_forever()
```

**Supported Streams:**
- `bookTicker.{SYMBOL}` - Best bid/offer (BBO)
- `depth.{SYMBOL}` - Full orderbook snapshot

**Subscription Format:**
```json
{
  "method": "SUBSCRIBE",
  "params": ["bookTicker.PAXG_USDC_PERP", "depth.PAXG_USDC_PERP"]
}
```

### User Data WebSocket

**Requires Authentication**

```python
from exchanges.ws import BackpackUserWS

ws = BackpackUserWS(
    api_key="your_api_key",
    secret="your_secret",
    on_event=on_event
)
await ws.run_forever()
```

**Supported Streams:**
- `account.orderUpdate.{SYMBOL}` - Order status updates
- `account.fills.{SYMBOL}` - Trade fills

**Authentication:**
```json
{
  "method": "SUBSCRIBE",
  "params": ["account.orderUpdate.SOL_USDC"],
  "signature": [
    "<api_key>",
    "<signature>",
    "<timestamp>",
    "<window>"
  ]
}
```

---

## Known Issues & Considerations

### ✅ Strengths
- Clean API design without path duplication issues
- Non-required `timeInForce` parameter (more flexible)
- Accurate precision handling
- Minimum order size properly enforced

### ⚠️ Considerations

**1. Leverage Not Supported**
- No `set_leverage()` method
- Leverage managed at account level, not per-position

**2. Price Differences vs CEX**
- Backpack prices may differ from major CEXs (Binance, OKX)
- Consider price slippage when hedging between exchanges
- Recommended: Monitor basis spread for arbitrage strategies

**3. Contract Size Units**
- Verify whether order amounts are in USD or contracts
- Check market info for `contractSize` parameter

---

## Message Format Examples

### BBO Update (bookTicker)
```json
{
  "stream": "bookTicker.PAXG_USDC_PERP",
  "data": {
    "symbol": "PAXG_USDC_PERP",
    "bestBid": "2875.50",
    "bestBidQty": "10.5",
    "bestAsk": "2875.60",
    "bestAskQty": "8.2",
    "time": 1768490299726
  }
}
```

### Order Update
```json
{
  "stream": "account.orderUpdate.SOL_USDC",
  "data": {
    "orderId": "12345",
    "symbol": "SOL_USDC",
    "status": "Filled",
    "side": "Buy",
    "price": "100.00",
    "quantity": "1.0",
    "filledQuantity": "1.0",
    "timestamp": 1768490299726
  }
}
```

---

## Integration Checklist

- [ ] Configure Ed25519 authentication
- [ ] Verify symbol format (underscores, _PERP suffix)
- [ ] Test WebSocket reconnection handling
- [ ] Monitor price differences if hedging with other exchanges
- [ ] Handle non-standard error responses
- [ ] Implement proper signature window validation

---

## References

- Implementation: `exchanges/backpack.py`
- WebSocket: `exchanges/ws/backpack.py`
- Authentication: `exchanges/auth/backpack.py`
- Abstract API: `exchanges/endpoints/backpack.py`
