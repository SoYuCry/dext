# WebSocket Unified Architecture Examples

This directory contains comprehensive examples demonstrating the unified WebSocket architecture for crypto exchange APIs.

## Examples Overview

### 01_single_exchange_bbo.py
**Basic BBO Monitoring**

Monitor best bid/offer prices from a single exchange (Lighter). Demonstrates:
- Creating a dispatcher with market mappings
- Connecting a WebSocket client
- Consuming normalized BBO updates
- Calculating spreads in basis points

**Usage:**
```bash
python examples/01_single_exchange_bbo.py
```

### 02_multi_exchange_arbitrage.py
**Multi-Exchange Arbitrage Detection**

Monitor price differences across multiple exchanges to detect arbitrage opportunities. Demonstrates:
- Connecting multiple exchanges simultaneously
- Using symbol filters
- Comparing prices across exchanges
- Detecting arbitrage when spread exceeds threshold

**Usage:**
```bash
python examples/02_multi_exchange_arbitrage.py
```

### 03_order_updates.py
**Order Status Monitoring**

Monitor order status changes and fills from user data streams. Demonstrates:
- Connecting to user data WebSocket
- Consuming order updates from the queue
- Handling different event types (ORDER_UPDATE, FILL_UPDATE)
- Environment variable configuration

**Requirements:**
- Set `BACKPACK_API_KEY` and `BACKPACK_SECRET_KEY` environment variables

**Usage:**
```bash
export BACKPACK_API_KEY="your_key"
export BACKPACK_SECRET_KEY="your_secret"
python examples/03_order_updates.py
```

### 04_combined_market_orders.py
**Combined Market Data + Order Updates**

Consume both market data and order updates simultaneously from separate queues. Demonstrates:
- Dual-queue pattern (market_data + order_update queues)
- Running multiple consumers concurrently
- Comparing fill prices with current market prices
- Non-blocking queue consumption

**Requirements:**
- Set `BACKPACK_API_KEY` and `BACKPACK_SECRET_KEY` environment variables

**Usage:**
```bash
export BACKPACK_API_KEY="your_key"
export BACKPACK_SECRET_KEY="your_secret"
python examples/04_combined_market_orders.py
```

### 05_statistics_monitoring.py
**Statistics and Performance Monitoring**

Use dispatcher statistics to monitor event throughput and queue health. Demonstrates:
- Accessing dispatcher statistics
- Periodic stats logging
- Monitoring queue sizes
- Detecting normalization errors and queue drops

**Usage:**
```bash
python examples/05_statistics_monitoring.py
```

### 06_variational_rfq.py
**Variational RFQ Quote Polling**

Poll Variational (Omni) RFQ quotes through the unified dispatcher. Demonstrates:
- Creating a Variational client
- Setting up RFQ polling
- Processing quote updates
- Accessing quote metadata (quote_id, latency)

**Requirements:**
- Set `VARIATIONAL_CONNECTED_ADDRESS` and `VARIATIONAL_COOKIE` environment variables

**Usage:**
```bash
export VARIATIONAL_CONNECTED_ADDRESS="0x..."
export VARIATIONAL_COOKIE="your_cookie"
python examples/06_variational_rfq.py
```

### 07_error_handling.py
**Error Handling and Reconnection**

Robust error handling patterns including reconnection and graceful shutdown. Demonstrates:
- Automatic reconnection with exponential backoff
- Queue overflow detection and handling
- Timeout handling for consumers
- Graceful shutdown procedure
- Error counting and circuit breaking

**Usage:**
```bash
python examples/07_error_handling.py
```

## Architecture Pattern

All examples follow the same three-stage pipeline:

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│ WebSocket   │────▶│ Normalizer   │────▶│ Dispatcher │
│ Connection  │     │              │     │  (Queues)  │
└─────────────┘     └──────────────┘     └────────────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │   Strategy   │
                                         │   Consumer   │
                                         └──────────────┘
```

### Key Components

**Dispatcher**: Routes raw events to normalized queues
```python
from exchanges.ws import create_dispatcher

dispatcher = create_dispatcher(
    lighter_market_mapping={0: "ETH/USDC"}
)
```

**WebSocket Clients**: Exchange-specific connections
```python
from exchanges.ws import LighterWS, BackpackWS

ws = LighterWS(
    market_index=0,
    on_event=dispatcher.on_raw_event,
    bbo_only=True,
)
```

**Consumers**: Strategy code consuming normalized events
```python
# Market data consumer
bbo = await dispatcher.get_market_data()  # Returns BBOUpdate

# Order update consumer
order = await dispatcher.get_order_update()  # Returns OrderUpdate
```

## Common Patterns

### Single Exchange
```python
dispatcher = create_dispatcher(lighter_market_mapping={0: "ETH/USDC"})
ws = LighterWS(market_index=0, on_event=dispatcher.on_raw_event)
ws_task = asyncio.create_task(ws.run_forever())

while True:
    bbo = await dispatcher.get_market_data()
    # Process BBO update
```

### Multiple Exchanges
```python
dispatcher = create_dispatcher(lighter_market_mapping={0: "ETH/USDC"})

lighter_ws = LighterWS(market_index=0, on_event=dispatcher.on_raw_event)
backpack_ws = BackpackWS(symbols=["ETH_USDC"], on_event=dispatcher.on_raw_event)

tasks = [
    asyncio.create_task(lighter_ws.run_forever()),
    asyncio.create_task(backpack_ws.run_forever()),
]

while True:
    bbo = await dispatcher.get_market_data()
    # Process BBO from either exchange
```

### Dual Queues
```python
async def market_consumer(dispatcher):
    while True:
        bbo = await dispatcher.get_market_data()
        # Process market data

async def order_consumer(dispatcher):
    while True:
        order = await dispatcher.get_order_update()
        # Process order update

await asyncio.gather(
    market_consumer(dispatcher),
    order_consumer(dispatcher),
)
```

## Environment Variables

Set these in `.env` or export them:

```bash
# Backpack
BACKPACK_API_KEY=your_key
BACKPACK_SECRET_KEY=your_base64_secret

# Variational
VARIATIONAL_CONNECTED_ADDRESS=0x...
VARIATIONAL_COOKIE=your_cookie

# Lighter
LIGHTER_PRIVATE_KEY=0x...
```

## Testing Examples

All examples can be tested without live credentials by modifying them to use mock data (see test files in `tests/` for mock patterns).

## Running Examples

所有示例都可以直接运行：

```bash
# 基础 BBO 监控
python examples/01_single_exchange_bbo.py

# 多交易所套利
python examples/02_multi_exchange_arbitrage.py

# 订单更新（需要 API 凭证）
export BACKPACK_API_KEY="your_key"
export BACKPACK_SECRET_KEY="your_secret"
python examples/03_order_updates.py
```

## Testing Examples

所有示例可通过修改为使用模拟数据来测试（参考 `tests/` 中的 mock 模式）。

## Further Reading

- `../docs/plans/2026-01-24-ws-unified-architecture-design.md`: Detailed architecture design
- `../docs/websocket/README.md`: WebSocket usage guide
- `../ARCHITECTURE.md`: Overall project architecture
- `../CLAUDE.md`: Project guide for AI assistants
- `../tests/README.md`: Testing guide
