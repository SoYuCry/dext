# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**dext** is a unified cryptocurrency exchange API library providing CCXT-style REST clients and WebSocket connections for multiple exchanges (Aster, Backpack, Binance, Lighter, Variational). It serves trading strategies and automated trading scripts with normalized interfaces.

### Terminology

Use **exchange** consistently in docs and comments (avoid mixing with "API" as a module name). The module directory is `exchanges/`.

## Common Commands

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_ws_clients.py

# Run with verbose output
pytest -v

# Run specific test function
pytest tests/test_ws_clients.py::test_backpack_bookticker_parsing
```

### Installation
```bash
# Install in development mode
pip install -e .

# Install with dependencies
pip install -r requirements.txt
```

### Linting / Formatting

No linting or formatting tools are configured. Quality is enforced through tests only.

### Python Version

Requires Python >= 3.9.

### Key Dependencies

- `PyNaCl`: Ed25519 cryptographic signatures (Backpack)
- `websockets>=11.0.0`: WebSocket connections
- `curl_cffi`: Browser-impersonation HTTP client (Variational)
- `python-dotenv`: Environment variable loading from `.env`

## Architecture

### Core Module Structure

The codebase follows a layered architecture with exchange-specific implementations inheriting from common base classes:

```
exchanges/
├── base/              # Foundation layer
│   ├── exchange.py    # Base class with unified _request() method
│   ├── types.py       # Unified data structures (Entry, etc.)
│   ├── errors.py      # Exception hierarchy
│   └── precise.py     # Precision utilities
├── endpoints/         # API endpoint configurations (NEW)
│   ├── backpack.py    # BackpackEndpoints class (112 endpoints)
│   ├── lighter.py     # LighterEndpoints class (30 endpoints)
│   ├── aster.py       # AsterEndpoints class (41 endpoints)
│   └── variational.py # VariationalEndpoints class (18 endpoints)
├── ws/                # WebSocket layer (unified architecture)
│   ├── base.py        # WebSocket connection base
│   ├── types.py       # BBOUpdate, OrderUpdate (standardized events)
│   ├── normalizer.py  # Raw events → normalized events
│   ├── dispatcher.py  # Queue-based event distribution
│   └── {exchange}.py  # Exchange-specific WS implementations
├── auth/              # Per-exchange authentication modules
│   ├── backpack.py    # Ed25519 signature helpers
│   ├── lighter.py     # zkSync signer
│   ├── aster.py       # HMAC-SHA256 authentication
│   └── variational.py # Cookie-based auth helpers
└── {exchange}.py      # REST client implementations
```

### REST API Unified Architecture

**Critical Design Pattern**: The REST API layer uses a unified request-response lifecycle to standardize all exchange interactions:

**Request-Response Lifecycle**:
```
1. Public API Method (e.g., fetch_ticker, create_order)
   ↓
2. _request(endpoint, params)  # Unified request handler
   ↓
3. sign() [if private endpoint]  # Exchange-specific signing
   ↓
4. fetch() → HTTP request
   ↓
5. handle_http_status_code()  # HTTP error handling via httpExceptions mapping
   ↓
6. parse_error()  # Exchange-specific error handling
   ↓
7. parse_ticker/parse_order/etc.  # Response normalization
   ↓
8. Return standardized data
```

**Key Components**:
- **Endpoint Configuration** (`endpoints/{exchange}.py`): Defines all API endpoints with Entry objects containing path, visibility (public/private), HTTP method, and cost
- **Unified Request Method** (`_request()`): Handles the complete request lifecycle including signing, error handling, and response parsing
- **Two-Layer Error Handling**:
  - Layer 1: `handle_http_status_code()` - Maps HTTP status codes to CCXT exceptions via `httpExceptions` dict
  - Layer 2: `parse_error()` - Handles exchange-specific error codes
- **Signing Methods** (`sign()`): Exchange-specific authentication (Ed25519, HMAC-SHA256, zkSync, Cookie)

**Standard usage pattern**:
```python
from exchanges.backpack import backpack

# Initialize exchange
exchange = backpack({'apiKey': 'xxx', 'secret': 'yyy'})

# All methods use unified _request() internally
ticker = await exchange.fetch_ticker('SOL/USDC')
order = await exchange.create_order('ETH/USDC', 'limit', 'buy', 1.0, 2000)

# Errors are automatically handled:
# - HTTP errors → BadRequest, AuthenticationError, RateLimitExceeded, etc.
# - Exchange errors → InvalidOrder, InsufficientFunds, OrderNotFound, etc.
```

### WebSocket Unified Architecture

**Critical Design Pattern**: The WebSocket layer uses a three-stage pipeline to decouple data sources from strategy consumers:

1. **Connection Layer** (`exchanges/ws/{exchange}.py`): Exchange-specific WebSocket clients emit raw events
2. **Normalization Layer** (`exchanges/ws/normalizer.py`): Converts raw events to standardized `BBOUpdate` and `OrderUpdate` structures
3. **Dispatcher Layer** (`exchanges/ws/dispatcher.py`): Routes normalized events to two queues:
   - `market_data_queue`: BBO updates, L2 orderbook
   - `order_update_queue`: Order status changes, fills

**Why this matters**: Strategies consume from queues using `dispatcher.get_market_data()` and `dispatcher.get_order_updates()`, which prevents blocking the WebSocket receive loop. Adding a new exchange requires implementing a normalizer, not modifying strategy code.

### Market Data Manager: Real-Time Position Tracking

**Critical Feature**: `MarketDataManager` (`exchanges/market_data.py`) maintains local position cache from WebSocket `account_orders` stream:

**Data Flow**:
```
1. WebSocket `account_orders` stream → Raw order updates
2. MarketDataManager._update_position_from_orders() → Update local position cache
3. Strategy calls market_data.get_position() → Instant (microsecond-level) retrieval
4. Background verification loop → Periodic API sync (every 30s)
```

**Key Methods**:
- `get_position(key=...)`: Get real-time position from local cache (no API call, <1μs)
- `set_position(position, key=...)`: Manually set position (used for API sync)
- `get_position_snapshot(key=...)`: Get full snapshot including timestamp and source

**Performance Impact**:
- Position retrieval: **200-500ms (API) → <1μs (cache)** = 100,000x improvement
- Strategy latency: Eliminates blocking on position API calls
- API load: Reduced from every tick to every 30 seconds

**Implementation Pattern** (see `strategies/eth_spread_arbitrage/strategy.py`):
```python
# Fast path: Get position from local cache
positions = self._get_positions_fast()  # Returns (lg_pos, var_pos) or None
if positions is None:
    # Fallback: Initialize from API (only on first run)
    positions = await self._fetch_positions(force=True)

# Independent verification loop (runs in background)
async def _position_verify_loop(self):
    while True:
        await asyncio.sleep(30)  # Non-blocking to main strategy
        await self._verify_positions()  # Compare local vs API, alert on mismatch
```

**Design Rationale**:
- WebSocket `account_orders` already provides order fill data; this feature eliminates waste
- Strategies can make position-based decisions without latency
- API is used only for verification, not primary data source
- Mismatches trigger alerts but don't block strategy execution

**Standard usage pattern**:
```python
from exchanges.ws import create_dispatcher
from exchanges.ws.lighter import LighterWS

# Create dispatcher with market mappings
dispatcher = create_dispatcher(lighter_market_mapping={0: "ETH/USDC"})

# Connect WebSocket to dispatcher
ws = LighterWS(market_index=0, on_event=dispatcher.on_raw_event, bbo_only=True)

# Strategy consumes normalized events
bbo = await dispatcher.get_market_data()  # Returns BBOUpdate
```

### Exchange-Specific Notes

**Lighter**:
- Uses native zkSync signer (not HMAC)
- Market indices (0, 1, 2...) map to symbols via `lighter_market_mapping`
- WS only provides market data (no user data stream yet)

**Backpack**:
- Ed25519 signatures (base64 secret key)
- Supports both market data WS and user data WS
- Symbol format: `SOL_USDC` (underscore separator)

**Variational** (**EXPERIMENTAL**):
- RFQ-based (request-for-quote) derivatives exchange
- Cookie-based authentication via browser impersonation (curl_cffi) — no official API-key auth
- Uses polling for market data (no native WebSocket)
- Quote IDs are single-use; must request new quote for each trade
- **Special**: Uses custom `make_request()` instead of base `_request()` due to curl_cffi dependency
- **Risk**: Any change to cookie format or CloudFlare policy can break this client without warning

**Aster**:
- Binance-style futures DEX
- HMAC-SHA256 authentication
- Full WebSocket support for market and user data

### Configuration System

Environment variables are loaded from `.env` via `config.py`. Each exchange has its own credential namespace:

- `BACKPACK_API_KEY`, `BACKPACK_SECRET_KEY`
- `ASTER_API_KEY`, `ASTER_SECRET_KEY`
- `LIGHTER_PRIVATE_KEY`
- `VARIATIONAL_COOKIE`, `VARIATIONAL_CONNECTED_ADDRESS`

Proxy settings: `HTTP_PROXY`, `HTTPS_PROXY`

### Strategy Pattern

Strategies live in `strategies/` and typically:
1. Inherit from `strategies/strategy_base.py`
2. Use the unified WebSocket dispatcher pattern
3. Have their own `config.py` for strategy-specific parameters (dataclasses with `exchange_a_kwargs()` / `exchange_b_kwargs()` builders)
4. Include a `runner.py` for execution
5. Follow async lifecycle: `start()` → `_run_loop()` → `_tick()` → `stop()`

**Shared Infrastructure** in `strategies/`:
- `base_exceptions.py`: `StrategyException`, `ConfigurationError`, `ExecutionError`, `DataError`, `RiskError`
- `base_alerts.py`: `AlertManager` with severity levels (CRITICAL/HIGH/MEDIUM/LOW) and channel support (logging, webhook)
- `strategy_base.py`: Base class with `log_config()` helper that redacts secrets at startup

Example strategies:
- `eth_spread_arbitrage/`: ETH spread trading between Lighter and Variational
- `xau_arbitrage/`: Gold (XAU) delta-neutral market making between Aster and Backpack

### Logging

`logger.py` provides `setup_logger(name)` which outputs to both console and file (configured via `LOG_FILE` env var). UTF-8 encoded.

### Testing Conventions

- Test files in `tests/` use naming pattern `test_*.py`
- WebSocket tests use `DummyWS` mock for connection testing
- Tests verify both raw event parsing and normalized event output
- Run tests before committing changes to WS clients or normalizers

### Key Files for Context

When working on features, these files provide critical context:

- `ARCHITECTURE.md`: Chinese documentation of module layering and design decisions
- `STRUCTURE.md`: File structure and recommended usage patterns
- `exchanges/README.md`: Comprehensive API usage guide with examples
- `docs/exchanges/`: Per-exchange documentation (aster.md, backpack.md, lighter.md, variational.md)
- `docs/exchanges/common-pitfalls.md`: Known integration pitfalls (URL duplication, precision bugs, USD-vs-contracts confusion)
- `strategies/README.md`: Strategy patterns and shared infrastructure

### Precision Handling

The codebase uses `Decimal` for price/amount calculations to avoid floating-point errors:

- `exchanges/base/precise.py`: Decimal utilities
- `exchanges/base/decimal_to_precision.py`: Exchange-specific precision formatting
- WebSocket layer preserves `Decimal` precision; conversion to float happens at strategy level if needed

### Adding New Exchanges

To add a new exchange:

**REST API Setup**:
1. Create endpoint configuration in `exchanges/endpoints/{exchange}.py`:
   - Define class `{Exchange}Endpoints` with Entry objects for each API endpoint
   - Include path, visibility (public/private), HTTP method, and cost
2. Create REST client in `exchanges/{exchange}.py` inheriting from `exchanges/base/exchange.py`:
   - Set `endpoints = {Exchange}Endpoints()`
   - Implement `describe()` method with exchange metadata
   - Implement `sign(request, endpoint, params)` for authentication
   - Implement `parse_error(response)` for exchange-specific error handling
   - Implement CCXT-style methods using `_request()`: `fetch_ticker()`, `create_order()`, etc.
   - Implement `parse_*()` methods for response normalization: `parse_ticker()`, `parse_order()`, etc.
3. Add authentication helpers in `exchanges/auth/{exchange}.py` (Ed25519, HMAC, zkSync, etc.)

**WebSocket Setup** (if supported):
4. Add WebSocket client in `exchanges/ws/{exchange}.py`
5. Create normalizer in `exchanges/ws/normalizer.py` for the exchange
6. Update `exchanges/ws/__init__.py` factory functions

**Testing & Documentation**:
7. Add configuration variables to `config.py`
8. Write tests in `tests/test_{exchange}.py`
9. Create documentation in `docs/exchanges/{exchange}.md` with API response samples and interface types
10. Update `CLAUDE.md` to record any new exchange-specific patterns or caveats

**Reference Implementations**:
- **Backpack**: Full implementation with Ed25519 signing (28 API methods)
- **Lighter**: DEX with zkSync native signer + auth token private REST access
- **Aster**: Binance-style futures with HMAC-SHA256 (13 API methods)
- **Binance**: Spot exchange with HMAC-SHA256 + listenKey user streams
- **Variational**: RFQ mode with Cookie auth (custom implementation)

**Key Design Principles**:
- All exchanges use unified `_request()` for consistency (except special cases like Variational)
- Endpoint configuration separates API definitions from business logic
- Two-layer error handling ensures both HTTP and business errors are handled
- `parse_*()` methods standardize responses to CCXT format

## Integration Testing Guide

### Core Policy: Perpetuals Only

This project focuses on derivatives trading. **Only test perpetual contracts** unless spot is explicitly required.

**Symbol Naming by Exchange:**
- **Backpack**: `SOL_USDC_PERP` (perpetual), `SOL_USDC` (spot)
- **Aster**: `SOL/USDC:USDC` (perpetual), `SOL/USDC` (spot)
- **Lighter**: `ETH` (all markets are perpetual by default)
- **Binance**: `BTCUSDT` (perpetual via futures API), `BTC/USDT` (spot)

**Default strategy**: Test LONG only (SHORT is symmetric). WebSocket verification in same test as trades. All positions MUST be closed before test completion.

### Critical Testing Rules

1. **Always close positions after testing** using `reduceOnly: True` for futures to prevent accidental position reversal. Use amounts that are multiples of minimum order size.
2. **Verify position/balance before closing** — don't blindly send close orders.
3. **Test WebSocket order events** alongside REST — many bugs only appear in WS layer.
4. **Use conservative pricing**: 20% below market for non-fill tests, 5% above for execution tests.
5. **Respect minimum order sizes**: Check `market['limits']['amount']['min']` before trading.

**Lesson learned**: Backpack spot test left 0.00999 SOL that couldn't be sold (min order 0.01). Always close fully.

**Position closing pattern:**
```python
close_order = exchange.create_order(
    symbol='SOL_USDC_PERP', type='limit', side='sell',
    amount=position_size, price=close_price,
    params={'reduceOnly': True}
)
```

### Integration Test Template

See `tests/integration/test_comprehensive_template.py` for a complete template that includes:
- Spot market testing with balance verification
- Futures market testing with position verification
- WebSocket order flow testing
- Automatic position cleanup
- Detailed logging and error handling

### Running Integration Tests

```bash
# Test single exchange (no real trading)
pytest tests/integration/test_backpack.py -v

# Test with real trading enabled (requires --enable-trading flag)
pytest tests/integration/test_backpack.py -v --enable-trading

# Comprehensive test (spot + futures + WebSocket + cleanup)
python tests/integration/test_comprehensive_template.py --exchange backpack
```

### Cost Estimates

Typical testing costs per exchange:
- Query API tests: $0 (no trades)
- Spot order lifecycle: ~$0.50-2.00 (if closed properly)
- Futures order lifecycle: ~$0.10-0.50 (lower fees, easier to close)
- WebSocket tests: $0 (can use unfilled orders)

**Total per exchange**: ~$1-3 if all positions are properly closed.

**WARNING**: Improper testing (leaving positions) can waste $5-20 per exchange in stuck capital.
