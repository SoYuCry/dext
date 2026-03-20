# Variational (Omni) Exchange Integration Guide

## Overview

Variational (branded as "Omni") is an RFQ-based (Request-for-Quote) derivatives exchange specializing in perpetual futures.

**Key Characteristics:**
- **Authentication:** Cookie-based (browser-style)
- **Trading Model:** RFQ (must request quote before order)
- **Quote Lifecycle:** Single-use quote IDs with expiration
- **WebSocket:** No native WebSocket (uses polling)
- **API Base URL:** `https://omni.variational.io/api`
- **Browser Fingerprinting:** Requires `curl_cffi` with Chrome impersonation

---

## Authentication

Variational uses **cookie-based authentication** unlike typical API key/secret exchanges.

### Implementation

Located in `exchanges/auth/variational.py`:

```python
from exchanges.auth.variational import create_headers

headers = create_headers(
    cookie="vr-token=...; other=...",
    connected_address="0xYourWalletAddress"
)
```

### How to Obtain Credentials

**Method 1: Browser DevTools (Recommended)**

1. Open https://omni.variational.io in browser and login
2. Open DevTools → Network tab, check "Preserve log"
3. Refresh page, find any XHR request (e.g., `/api/status`)
4. Copy complete `Cookie` header (must include `vr-token=...`)
5. Copy `vr-connected-address` header value

**Method 2: Console (if cookie not HttpOnly)**

```javascript
// In browser console
document.cookie
```

If `vr-token` is HttpOnly, use Application → Cookies → copy manually.

### Requirements

**Critical Headers:**
- `Cookie`: Contains `vr-token` JWT
- `vr-connected-address`: Wallet address (extracted from vr-token or request headers)
- `counterparty` / `counterparty_id`: Found in API responses or request payloads

**Library Dependency:**
```bash
pip install curl_cffi
```

**Browser Impersonation:**
- Must use `curl_cffi` with Chrome fingerprint
- Default: `impersonate="chrome120"`
- Required to bypass anti-bot detection

---

## REST API Client

### Basic Usage

```python
from exchanges import get_client

config = {
    "cookie": "vr-token=...; other=...",
    "vr_connected_address": "0xYourWallet",
    "counterparty": "your_cp_id",
    "instrument": {
        "underlying": "ETH",
        "funding_interval_s": 3600,
        "settlement_asset": "USDC",
        "instrument_type": "perpetual_future"
    }
}

client = get_client("variational", config)

# Request indicative quote
quote = client.request_indicative_quote("0.1")
# Returns: {"quote_id": "...", "bid": "3004.72", "ask": "3004.86"}

# Create market order (must use recent quote_id)
order = client.create_order(
    symbol="IGNORED",  # Symbol ignored, uses instrument from config
    order_type="market",
    side="buy",
    amount="0.1",
    params={"max_slippage": 0.05}
)

# Fetch positions
positions = client.fetch_positions()

# Cancel order
client.cancel_order(order["id"])
```

### Instrument Configuration

**Required Fields:**
```python
instrument = {
    "underlying": "ETH",           # Base asset
    "funding_interval_s": 3600,    # Funding period in seconds
    "settlement_asset": "USDC",    # Quote asset
    "instrument_type": "perpetual_future"
}
```

---

## RFQ Trading Workflow

### 1. Request Indicative Quote

**Endpoint:** `POST /quotes/indicative`

```python
quote = client.request_indicative_quote(qty="0.1")
```

**Response:**
```json
{
  "quote_id": "cf1c7b68-8fb0-4959-94c1-3c4590f7c089",
  "bid": "3004.72",
  "ask": "3004.86",
  "mark_price": "3004.863768417404",
  "index_price": "3004.702195418654",
  "margin_requirements": {
    "initial_margin": "3.605436",
    "maintenance_margin": "1.802718"
  }
}
```

**Important:** Quote ID expires within seconds (typically 5-10s).

### 2. Create Market Order

**Endpoint:** `POST /orders/new/market`

```python
order = client.create_order(
    symbol="IGNORED",
    order_type="market",
    side="buy",  # or "sell"
    amount="0.1",
    params={
        "max_slippage": 0.05  # 5% max slippage
    }
)
```

**Payload:**
```json
{
  "quote_id": "cf1c7b68-8fb0-4959-94c1-3c4590f7c089",
  "side": "buy",
  "max_slippage": 0.05
}
```

**Timing Critical:** Must submit order within seconds of quote request.

### 3. Create Limit Order

**Endpoint:** `POST /orders/new/limit`

```python
order = client.create_order(
    symbol="IGNORED",
    order_type="limit",
    side="buy",
    amount="0.1",
    price=3000.0,
    params={
        "trigger_price": 3050.0,  # For stop orders
        "is_auto_resize": False,
        "use_mark_price": False
    }
)
```

**Order Types:**
- `limit` - Standard limit order
- `stop_limit` - Stop-loss with limit price
- `take_profit` - Take-profit limit order
- `stop_loss` - Stop-loss market order

### 4. Cancel Order

**Endpoint:** `POST /orders/cancel`

```python
client.cancel_order(rfq_id="order_id_here")
```

---

## Market Data (Polling-Based)

### VariationalPricePoller

Since Variational has no native WebSocket, we poll `/quotes/indicative`:

```python
from exchanges.ws import VariationalPricePoller

poller = VariationalPricePoller(
    client=client,
    instrument={
        "underlying": "ETH",
        "funding_interval_s": 3600,
        "settlement_asset": "USDC",
        "instrument_type": "perpetual_future"
    },
    qty="0.01",
    interval=1.0,  # Poll every 1 second
    on_event=on_event
)

await poller.run_forever()
```

**Emitted Event Format:**
```json
{
  "exchange": "variational",
  "stream": "quote",
  "quote_id": "...",
  "bid": 3004.72,
  "ask": 3004.86,
  "instrument": {...},
  "ts_local": 1768490299726
}
```

### VariationalFillPoller

Poll for order fills and updates:

```python
from exchanges.ws import VariationalFillPoller

fill_poller = VariationalFillPoller(
    client=client,
    interval=2.0,  # Poll every 2 seconds
    limit=50,      # Max orders to fetch
    on_event=on_event
)

await fill_poller.run_forever()
```

### VariationalEventsWS (Experimental)

WebSocket events stream (if available):

```python
from exchanges.ws import VariationalEventsWS

ws = VariationalEventsWS(
    ws_url="wss://omni-ws-server.prod.ap-northeast-1.variational.io/events",
    auth_token="your_auth_token",
    cookie="vr-token=...",
    on_event=on_event
)

await ws.run_forever()
```

---

## Unified Dispatcher Integration

```python
from exchanges.ws import create_dispatcher, VariationalPricePoller
from exchanges import get_client

# Create client
client = get_client("variational", config)

# Create dispatcher
dispatcher = create_dispatcher()

# Create poller
poller = VariationalPricePoller(
    client=client,
    instrument=config["instrument"],
    qty="0.01",
    interval=1.0,
    on_event=dispatcher.on_raw_event
)

# Strategy consumes normalized BBO updates
async def strategy():
    while True:
        bbo = await dispatcher.get_market_data()
        print(f"Quote: {bbo.best_bid} / {bbo.best_ask}")
```

---

## Known Issues & Considerations

### ⚠️ Critical Considerations

**1. Quote Expiration**
- Quote IDs expire within 5-10 seconds
- Must request new quote for each order
- Can't reuse old quote IDs
- Recommended: Request quote → immediately submit order

**2. Browser Fingerprinting**
- **Must use `curl_cffi`** with Chrome impersonation
- Regular `requests` library will fail
- Anti-bot detection requires proper headers

**3. Cookie Management**
- Cookies may expire after inactivity
- Need to refresh from browser periodically
- No programmatic cookie refresh available

**4. No Native WebSocket**
- Relies on polling for market data
- Higher latency than true WebSocket exchanges
- Increased API rate limit usage

**5. Single-Use Quotes**
- Cannot use one quote for multiple orders
- Must request fresh quote each time
- Polling generates many quote IDs

### ✅ Strengths
- RFQ model provides guaranteed execution prices
- Low slippage for larger orders
- Derivatives focus with advanced order types
- Clean API design

---

## Polling vs WebSocket Comparison

| Feature | Variational (Polling) | Other Exchanges (WebSocket) |
|---------|----------------------|----------------------------|
| Latency | ~1000ms (1s interval) | <50ms |
| Server Load | Higher (repeated HTTP) | Lower (persistent connection) |
| Quote Freshness | Depends on interval | Real-time |
| Implementation | Simple | Moderate complexity |
| Rate Limits | More restrictive | Less restrictive |

**Recommendation:** Use 1-2 second polling interval to balance freshness and API usage.

---

## Integration Checklist

- [ ] Install `curl_cffi` library
- [ ] Obtain Cookie and vr-connected-address from browser
- [ ] Find counterparty ID from API responses
- [ ] Configure instrument details correctly
- [ ] Implement quote → order timing (within 5s)
- [ ] Set up polling interval (recommended: 1-2s)
- [ ] Handle cookie expiration/refresh
- [ ] Test order types (market, limit, stop)
- [ ] Monitor quote ID expiration errors

---

## Error Handling

**Common Errors:**

1. **"Quote expired"**
   - Solution: Request new quote immediately before order

2. **"Invalid cookie"**
   - Solution: Re-extract cookie from browser

3. **"Browser fingerprint mismatch"**
   - Solution: Ensure `curl_cffi` with `impersonate="chrome120"`

4. **"Counterparty not found"**
   - Solution: Check counterparty ID in API responses

---

## References

- Implementation: `exchanges/variational.py` (VariationalClient)
- WebSocket/Pollers: `exchanges/ws/variational.py`
- Authentication: `exchanges/auth/variational.py`
- Abstract API: `exchanges/endpoints/variational.py`
