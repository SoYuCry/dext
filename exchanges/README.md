# Exchange API Documentation

Unified API clients for cryptocurrency exchanges, supporting both REST and WebSocket connections.

## Supported Exchanges

| Exchange | REST API | Market Data WS | User Data WS | Status |
|----------|----------|----------------|--------------|--------|
| [Aster](../docs/exchanges/aster.md) | ✅ | ✅ | ✅ | Production |
| [Backpack](../docs/exchanges/backpack.md) | ✅ | ✅ | ✅ | Production |
| [Binance](../docs/exchanges/binance.md) | ✅ | ✅ | ✅ | Production |
| [Lighter](../docs/exchanges/lighter.md) | ✅ | ✅ | ❌ | Production |
| [Variational](../docs/exchanges/variational.md) | ✅ | ⚠️ Polling | ⚠️ Polling | Production |

---

## Quick Start

### REST API

```python
from api import get_client

# Initialize client
client = get_client("backpack", {
    "apiKey": "your_api_key",
    "secret": "your_secret"
})

# Fetch market data
ticker = client.fetch_ticker("SOL/USDC")
orderbook = client.fetch_order_book("SOL/USDC")
trades = client.fetch_trades("SOL/USDC")

# Trading
order = client.create_order("SOL/USDC", "limit", "buy", 1.0, 100.0)
client.cancel_order(order["id"], "SOL/USDC")

# Account
balance = client.fetch_balance()
positions = client.fetch_positions()
```

### WebSocket Market Data

```python
import asyncio
from api.ws import get_ws_client

async def handle_event(event):
    print(f"Exchange: {event['exchange']}")
    print(f"Best bid: {event.get('best_bid')}")
    print(f"Best ask: {event.get('best_ask')}")

# Subscribe to market data
ws = get_ws_client("backpack", ["SOL_USDC"], handle_event, include_depth=True)
asyncio.run(ws.run_forever())
```

### WebSocket User Data

```python
import asyncio
from api.ws import get_user_ws_client

async def handle_user_event(event):
    if event.get("type") == "order":
        print(f"Order update: {event}")
    elif event.get("type") == "fill":
        print(f"Fill: {event}")

# Subscribe to user data stream
ws = get_user_ws_client("backpack", handle_user_event, 
                        api_key="...", secret="...")
asyncio.run(ws.run_forever())
```

---

## Exchange-Specific Guides

Detailed documentation for each exchange:

- **[Aster](../docs/exchanges/aster.md)**: Binance-style futures DEX with HMAC authentication
- **[Backpack](../docs/exchanges/backpack.md)**: Solana-based exchange with Ed25519 signatures
- **[Binance](../docs/exchanges/binance.md)**: Spot exchange with HMAC-SHA256 signatures
- **[Lighter](../docs/exchanges/lighter.md)**: zkSync-based order book DEX with native signer
- **[Variational](../docs/exchanges/variational.md)**: RFQ-based derivatives exchange with cookie auth

---

## Common Patterns

### Client Initialization

All exchanges follow the same factory pattern:

```python
from api import get_client

# Exchange-specific config
config = {
    "apiKey": "...",
    "secret": "...",
    # Exchange-specific options
}

client = get_client("exchange_name", config)
```

### Standardized Methods

All clients implement standardized methods:

**Market Data**:
- `fetch_markets()` - Get all trading pairs
- `fetch_ticker(symbol)` - Get 24h ticker
- `fetch_order_book(symbol, limit)` - Get order book
- `fetch_trades(symbol, limit)` - Get recent trades
- `fetch_ohlcv(symbol, timeframe, limit)` - Get candlestick data

**Trading**:
- `create_order(symbol, type, side, amount, price, params)` - Place order
- `cancel_order(id, symbol, params)` - Cancel order
- `fetch_order(id, symbol)` - Get order status
- `fetch_open_orders(symbol)` - Get active orders
- `fetch_closed_orders(symbol, limit)` - Get order history

**Account**:
- `fetch_balance()` - Get account balances
- `fetch_positions(symbol)` - Get open positions
- `fetch_my_trades(symbol, limit)` - Get trade history

**Leverage** (futures only):
- `set_leverage(leverage, symbol)` - Set leverage for symbol

### Error Handling

All clients use standardized exceptions:

```python
from api.base.errors import (
    ExchangeError,          # Base exception
    AuthenticationError,    # Invalid credentials
    InsufficientFunds,      # Not enough balance
    InvalidOrder,           # Order validation failed
    OrderNotFound,          # Order doesn't exist
    RateLimitExceeded,      # Too many requests
    NetworkError,           # Connection issues
)

try:
    order = client.create_order("BTC/USDT", "limit", "buy", 0.01, 50000)
except InsufficientFunds:
    print("Not enough balance")
except InvalidOrder as e:
    print(f"Invalid order: {e}")
except RateLimitExceeded:
    print("Rate limit hit, waiting...")
    time.sleep(60)
```

---

## WebSocket Patterns

### Market Data Subscription

```python
from api.ws import get_ws_client

async def on_event(event):
    # event structure:
    # {
    #     "exchange": "backpack",
    #     "symbol": "SOL_USDC",
    #     "stream": "depth",
    #     "best_bid": 100.5,
    #     "best_ask": 100.6,
    #     "ts_exchange": 1234567890,
    #     "ts_local": 1234567891,
    # }
    pass

# Single symbol
ws = get_ws_client("backpack", ["SOL_USDC"], on_event)

# Multiple symbols
ws = get_ws_client("backpack", ["SOL_USDC", "BTC_USDC"], on_event)

# With full depth
ws = get_ws_client("backpack", ["SOL_USDC"], on_event, include_depth=True)

await ws.run_forever()
```

Type normalization:
- `best_bid` and `best_ask` are normalized to `float` by the market data cache (`api.market_data.PriceSnapshot`).

### User Data Subscription

```python
from api.ws import get_user_ws_client

async def on_user_event(event):
    # Order updates
    if event.get("type") == "order":
        print(f"Order {event['order_id']}: {event['status']}")
    
    # Fill notifications
    elif event.get("type") == "fill":
        print(f"Filled {event['qty']} @ {event['price']}")

ws = get_user_ws_client(
    "backpack",
    on_user_event,
    api_key="your_key",
    secret="your_secret"
)

await ws.run_forever()
```

### Auto-Reconnection

All WebSocket clients have built-in reconnection:

```python
ws = get_ws_client("backpack", ["SOL_USDC"], on_event)

# Reconnects automatically on:
# - Connection loss
# - Ping timeout
# - Server disconnect
# - Network errors

# Exponential backoff: 1s, 2s, 4s, 8s, 16s (max)
```

---

## Advanced Usage

### Custom Precision Handling

```python
# Get market info
market = client.market("BTC/USDT")

# Precision info
print(market["precision"])  # {"amount": 3, "price": 2}
print(market["limits"])     # {"amount": {"min": 0.001, ...}}

# Manual precision formatting
amount_str = client.amount_to_precision("BTC/USDT", 0.123456)  # "0.123"
price_str = client.price_to_precision("BTC/USDT", 50000.789)   # "50000.78"
```

### Proxy Configuration

```python
import os

# Set proxy via environment
os.environ["HTTP_PROXY"] = "http://proxy.example.com:8080"
os.environ["HTTPS_PROXY"] = "http://proxy.example.com:8080"

# Client will automatically use proxy
client = get_client("backpack", config)
```

### Rate Limiting

```python
# Check rate limit info
print(client.rateLimit)  # milliseconds between requests

# Manual rate limit handling
import time

for symbol in symbols:
    try:
        ticker = client.fetch_ticker(symbol)
    except RateLimitExceeded:
        time.sleep(client.rateLimit / 1000)
        ticker = client.fetch_ticker(symbol)
```

---

## Troubleshooting

### Common Issues

**Authentication Errors**:
```python
# Check API key format
# Aster: HMAC-SHA256
# Backpack: Ed25519 (base64 secret)
# Lighter: Private key (no 0x prefix)
# Variational: Cookie-based
```

**Precision Errors**:
```python
# Always use precision helpers
amount = client.amount_to_precision(symbol, raw_amount)
price = client.price_to_precision(symbol, raw_price)
```

**WebSocket Disconnections**:
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check connection
ws = get_ws_client("backpack", ["SOL_USDC"], on_event)
# Logs will show connection status and errors
```

### Debug Mode

```python
# Enable verbose logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# All API calls and responses will be logged
client = get_client("backpack", config)
```

---

## Additional Resources

- **[WebSocket Guide](./docs/websocket-guide.md)**: Comprehensive WebSocket usage patterns
- **[Common Pitfalls](./docs/common-pitfalls.md)**: Troubleshooting guide with 7 common errors
- **Exchange-specific docs**: See `docs/` directory for detailed guides

---

## Architecture

### Module Structure

```
api/
├── __init__.py              # get_client() factory
├── base/                    # Base classes and utilities
│   ├── exchange.py          # Exchange base class
│   ├── types.py             # Type definitions
│   ├── errors.py            # Exception hierarchy
│   ├── precise.py           # Precision utilities
│   └── decimal_to_precision.py
├── endpoints/               # Endpoint definitions
│   ├── aster.py
│   ├── backpack.py
│   ├── lighter.py
│   └── variational.py
├── aster.py                 # Aster implementation
├── backpack.py              # Backpack implementation
├── lighter.py               # Lighter REST client
├── variational.py           # Variational RFQ client
├── auth/                    # Authentication modules
│   ├── backpack.py          # Ed25519 signatures
│   ├── lighter.py           # zkSync native signer
│   ├── aster.py             # HMAC-SHA256 signatures
│   └── variational.py       # Cookie-based auth
├── proxy_utils.py           # Proxy configuration
└── ws/                      # WebSocket clients
    ├── __init__.py          # get_ws_client(), get_user_ws_client()
    ├── base.py              # WebSocket base class
    ├── aster.py             # Aster WS clients
    ├── backpack.py          # Backpack WS clients
    ├── lighter.py           # Lighter WS client
    └── variational.py       # Variational pollers
```

### Design Principles

1. **Unified Interface**: Standard method names and return formats
2. **Type Safety**: Comprehensive type hints throughout
3. **Error Handling**: Consistent exception hierarchy
4. **Async Support**: All WebSocket clients are async
5. **Extensibility**: Easy to add new exchanges

---

**Last Updated**: 2026-01-18  
**Maintainer**: Liuc
