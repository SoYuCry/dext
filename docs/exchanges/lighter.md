# Lighter Exchange Integration Guide

## Overview

Lighter is a zkSync-based decentralized exchange for perpetual futures trading.

**Key Characteristics:**
- **Authentication:** zkSync native signer (not HMAC)
- **Market Indices:** Markets identified by numeric indices (0, 1, 2...)
- **Symbol Mapping:** Requires manual market index → symbol mapping
- **WebSocket Protocol:** JSON-based subscription
- **API Base URL:** `https://mainnet.zklighter.elliot.ai`
- **WebSocket URL:** `wss://mainnet.zklighter.elliot.ai/stream`

---

## Authentication

Lighter uses **zkSync native signing** for authentication, completely different from typical HMAC-based exchanges.

### Implementation

Located in `exchanges/auth/lighter.py` (legacy alias: `exchanges/lighter_signer.py`):

```python
from exchanges.auth.lighter import SimpleSignerClient

client = SimpleSignerClient(
    base_url="https://mainnet.zklighter.elliot.ai",
    private_key="0xYourPrivateKey",
    account_index=0,
    api_key_index=0,
    signer_dir="Signer/lighter",  # optional
)

# Create authentication token (valid for 10 minutes by default)
auth_token, err = client.create_auth_token_with_expiry()
```

### Requirements
- **Signer Binary:** Requires `lighter-cpp-signer` library
  - Download from: [https://github.com/elliottech/lighter-python](https://github.com/elliottech/lighter-python)
  - Place in `exchanges/signers/` or `Signer/lighter/`
- **Private Key:** zkSync-compatible private key (not API key/secret)
- **Account Index:** On-chain account index for the wallet

### Token Characteristics
- **Expiry:** 10 minutes
- **Usage:** WebSocket authentication, REST API signatures
- **Renewal:** Must regenerate after expiration

---

## REST API Client

### Basic Usage

```python
from exchanges import get_client

client = get_client("lighter", {
    "privateKey": "0xYourPrivateKey",
    "accountIndex": 0,
    "apiKeyIndex": 0,
    # optional
    "signerDir": "Signer/lighter",
})

# Market data
markets = client.fetch_markets()
ticker = client.fetch_ticker("ETH/USDC")
orderbook = client.fetch_order_book("ETH/USDC", limit=20)
ohlcv = client.fetch_ohlcv("ETH/USDC", timeframe="1h", limit=50)

# Trading (requires signer + account index)
order = client.create_order("ETH/USDC", "limit", "buy", 0.1, 2875.0)
client.cancel_order(order["id"], "ETH/USDC")

# Account
balance = client.fetch_balance()
positions = client.fetch_positions()
my_trades = client.fetch_my_trades("ETH/USDC", limit=50)
```

### Market Index System

Lighter uses **numeric market indices** instead of symbol strings:

```python
# Market mapping (must be maintained by client)
MARKET_MAPPING = {
    0: "ETH/USDC",
    1: "BTC/USDC",
    2: "SOL/USDC"
}
```

**Why mapping needed:**
- Lighter API uses indices (0, 1, 2) for all operations
- Human-readable symbols not used in API calls
- Mapping must be maintained in application config

---

## Data Structure Examples

### Market Metadata (`GET /api/v1/orderBookDetails`)
```json
{
  "order_book_details": [
    {
      "market_id": 0,
      "symbol": "ETH_USDC",
      "base_asset": "ETH",
      "quote_asset": "USDC",
      "supported_size_decimals": 3,
      "supported_price_decimals": 2,
      "min_base_amount": "0.001",
      "status": "TRADING"
    }
  ]
}
```

### Order Book Snapshot (`GET /api/v1/orderBookOrders`)
```json
{
  "bids": [["2875.50", "1.5"], ["2875.40", "2.0"]],
  "asks": [["2875.60", "1.1"], ["2875.70", "3.2"]]
}
```

### Open Orders (`GET /api/v1/accountActiveOrders`)
```json
{
  "orders": [
    {
      "order_index": "12345",
      "client_order_index": 10001,
      "market_id": 0,
      "status": "open",
      "is_ask": false,
      "price": "2875.50",
      "initial_base_amount": "0.10",
      "filled_base_amount": "0.00",
      "remaining_base_amount": "0.10"
    }
  ]
}
```

### Trades (`GET /api/v1/trades`)
```json
{
  "trades": [
    {
      "trade_id": "98765",
      "market_id": 0,
      "price": "2875.50",
      "size": "0.10",
      "timestamp": 1705834567
    }
  ]
}
```

### Candlesticks (`GET /api/v1/candlesticks`)
```json
{
  "candlesticks": [
    {
      "timestamp": 1705830000,
      "open": "2870.00",
      "high": "2880.00",
      "low": "2865.00",
      "close": "2875.50",
      "volume0": "120.5",
      "volume1": "346000"
    }
  ]
}
```

---

## WebSocket Client

### Market Data WebSocket

```python
from exchanges.ws import LighterWS

ws = LighterWS(
    market_index=0,  # ETH/USDC
    on_event=on_event,
    bbo_only=True  # True for BBO, False for full orderbook
)
await ws.run_forever()
```

### WebSocket Subscription Format

**Orderbook Subscription:**
```json
{
  "type": "subscribe",
  "channel": "order_book/0"
}
```

**Account Orders (Requires Auth):**
```json
{
  "type": "subscribe",
  "channel": "account_orders/0/0",
  "auth": "<auth_token>"
}
```

### Message Format

**Initial Snapshot:**
```json
{
  "subscribed": "order_book",
  "market_index": 0,
  "asks": [
    {"price": "2875.60", "size": "10.5"},
    {"price": "2875.70", "8.2"}
  ],
  "bids": [
    {"price": "2875.50", "size": "12.0"},
    {"price": "2875.40", "size": "5.5"}
  ],
  "last_seq_num": 1234567
}
```

**Incremental Update:**
```json
{
  "stream": "order_book",
  "market_index": 0,
  "asks": [{"price": "2875.65", "size": "3.0"}],
  "bids": [],
  "seq_num": 1234568
}
```

---

## Unified Dispatcher Pattern

Lighter integrates with the unified WebSocket dispatcher for normalized events:

```python
from exchanges.ws import create_dispatcher, LighterWS

# Create dispatcher with market mapping
dispatcher = create_dispatcher(
    lighter_market_mapping={
        0: "ETH/USDC",
        1: "BTC/USDC"
    }
)

# Connect WebSocket to dispatcher
ws = LighterWS(
    market_index=0,
    on_event=dispatcher.on_raw_event,
    bbo_only=True
)

# Strategy consumes normalized events
async def strategy():
    while True:
        bbo = await dispatcher.get_market_data()
        print(f"BBO: {bbo.best_bid} / {bbo.best_ask}")
```

---

## Sequence Number Validation

Lighter WebSocket includes automatic sequence validation:

### Features
- Detects gaps in sequence numbers
- Logs warnings for missed updates
- Optional strict mode (raises errors on gaps)

### BBO-Only Mode Benefits
- Ignores sequence gaps (safe for BBO tracking)
- Only updates when better prices arrive
- Reduces unnecessary processing

```python
ws = LighterWS(
    market_index=0,
    on_event=on_event,
    bbo_only=True  # Ignores sequence gaps
)
```

---

## Current Limitations

### ⚠️ User Data Stream Status

**Current Status:** Market data only

- ✅ Public orderbook subscriptions work
- ⚠️ User account orders require authentication token
- ⚠️ User stream not fully integrated yet
- 🔄 Planned: Full user data stream support

**Workaround:** Use REST API polling for order status

---

## Known Issues & Considerations

### 🔧 Signer Library Setup

**Common Issues:**
1. **Binary not found:**
   - Error: `Signer library not found`
   - Solution: Download from official repo, place in `exchanges/signers/`

2. **Platform compatibility:**
   - Requires platform-specific binary (macOS/Linux/Windows)
   - Check binary permissions (`chmod +x`)

3. **Path issues:**
   - Searched paths: `exchanges/signers/`, `Signer/lighter/`
   - Can specify custom path via `signer_dir` parameter

### ✅ Strengths
- Native blockchain integration (zkSync)
- Clean WebSocket protocol
- Automatic sequence validation
- BBO-only mode for efficiency
- Active development

---

## Integration Checklist

- [ ] Download and install lighter-cpp-signer binary
- [ ] Configure zkSync private key (not API key/secret)
- [ ] Set up market index → symbol mapping
- [ ] Implement auth token refresh (10-minute expiry)
- [ ] Choose between BBO-only or full orderbook mode
- [ ] Handle sequence number validation
- [ ] Plan for user data stream (currently limited)
- [ ] Test reconnection handling

---

## References

- Implementation: `exchanges/lighter.py`
- WebSocket: `exchanges/ws/lighter.py`
- Authentication: `exchanges/auth/lighter.py` (SimpleSignerClient)
- Abstract API: `exchanges/endpoints/lighter.py`
- Official Docs: [https://docs.lighter.xyz](https://docs.lighter.xyz)
- Python SDK: [https://github.com/elliottech/lighter-python](https://github.com/elliottech/lighter-python)
