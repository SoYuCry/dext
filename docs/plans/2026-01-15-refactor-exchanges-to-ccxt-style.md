# Refactor Aster & Backpack to CCXT Style Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Gradually refactor `api/aster.py` and `api/backpack.py` to adopt CCXT's proven design patterns without importing from ccxt library.

**Architecture:** Learn from ccxt's 100+ exchange support by adopting: (1) Comprehensive error code mapping, (2) Declarative API endpoint definitions, (3) Detailed exchange metadata in `describe()`, (4) Consistent data normalization patterns.

**Tech Stack:** Python 3, existing base.exchange.Exchange class, custom error classes

---

## Phase 1: Enhanced Error Handling (CCXT Pattern)

### Task 1: Expand Aster Error Code Mapping

**Files:**
- Modify: `api/aster.py:75-86` (exceptions dictionary)

**Current State Analysis:**
Current error mapping is minimal (only 8 error codes). CCXT's Aster implementation (in `api/exchanges/aster.py`) has 100+ error codes mapped for comprehensive error handling.

**Step 1: Research complete error code list from exchanges/aster.py**

Read the full error mapping from the generated file to understand all possible error scenarios.

**Step 2: Expand the exceptions dictionary in aster.py**

Add comprehensive error code mapping based on CCXT's pattern. Group by category:
- 10xx: General Server/Network issues
- 11xx: Request issues
- 20xx: Processing issues
- 40xx: Filters and validation issues

```python
"exceptions": {
    "exact": {
        # 10xx - General Server or Network issues
        "-1000": OperationFailed,  # UNKNOWN
        "-1001": NetworkError,  # DISCONNECTED
        "-1002": AuthenticationError,  # UNAUTHORIZED
        "-1003": RateLimitExceeded,  # TOO_MANY_REQUESTS
        "-1006": BadResponse,  # UNEXPECTED_RESP
        "-1007": RequestTimeout,  # TIMEOUT
        "-1015": RateLimitExceeded,  # TOO_MANY_ORDERS
        "-1021": InvalidNonce,  # INVALID_TIMESTAMP
        "-1022": AuthenticationError,  # INVALID_SIGNATURE

        # 11xx - Request issues
        "-1100": BadRequest,  # ILLEGAL_CHARS
        "-1102": ArgumentsRequired,  # MANDATORY_PARAM_EMPTY_OR_MALFORMED
        "-1121": BadSymbol,  # BAD_SYMBOL

        # 20xx - Processing Issues
        "-2010": InvalidOrder,  # NEW_ORDER_REJECTED
        "-2011": OrderNotFound,  # CANCEL_REJECTED
        "-2013": OrderNotFound,  # NO_SUCH_ORDER
        "-2014": AuthenticationError,  # BAD_API_KEY_FMT
        "-2018": InsufficientFunds,  # BALANCE_NOT_SUFFICIENT
        "-2019": InsufficientFunds,  # MARGIN_NOT_SUFFICIENT

        # 40xx - Filters and validation
        "-4000": InvalidOrder,  # INVALID_ORDER_STATUS
        "-4001": InvalidOrder,  # PRICE_LESS_THAN_ZERO
        "-4004": InvalidOrder,  # QTY_LESS_THAN_MIN_QTY
        "-4013": InvalidOrder,  # PRICE_LESS_THAN_MIN_PRICE
    },
    "broad": {
        # Pattern matching for error messages
        "has no position": InvalidOrder,
        "does not exist": BadSymbol,
        "Invalid symbol": BadSymbol,
    },
},
```

**Step 3: Add broad pattern matching for error messages**

CCXT uses both exact code matching AND broad pattern matching. Add a `broad` section to handle error messages:

```python
def handle_errors(
    self,
    statusCode: int,
    statusText: str,
    url: str,
    method: str,
    responseHeaders: Dict[str, Any],
    responseBody: str,
    response: Any,
    requestHeaders: Dict[str, Any],
    requestBody: Any,
) -> None:
    if response is None:
        return
    if isinstance(response, str):
        return
    code = self.safe_string(response, "code")
    message = self.safe_string(response, "msg") or self.safe_string(response, "message")
    if code is None and message is None:
        return
    feedback = self.id + " " + responseBody

    # Exact code matching
    self.throw_exactly_matched_exception(self.exceptions["exact"], code, feedback)

    # Broad pattern matching on message
    if "broad" in self.exceptions:
        self.throw_broadly_matched_exception(self.exceptions["broad"], message, feedback)

    # Still throw generic error if not matched
    raise ExchangeError(feedback)
```

**Step 4: Test error handling improvements**

Run: `pytest tests/api/test_aster.py::test_error_handling -v`
Expected: All error codes properly mapped to correct exception types

**Step 5: Commit**

```bash
git add api/aster.py
git commit -m "feat(aster): expand error code mapping following CCXT pattern

- Add 40+ error code mappings grouped by category
- Add broad pattern matching for error messages
- Improve error handling granularity"
```

---

### Task 2: Expand Backpack Error Code Mapping

**Files:**
- Modify: `api/backpack.py:1-100` (need to read current state first)

**Step 1: Read current backpack.py implementation**

Read the file to understand current error handling.

**Step 2: Add comprehensive error mapping from exchanges/backpack.py**

Add error codes based on the generated version:

```python
"exceptions": {
    "exact": {
        "INVALID_CLIENT_REQUEST": BadRequest,
        "INVALID_ORDER": InvalidOrder,
        "ACCOUNT_LIQUIDATING": BadRequest,
        "FORBIDDEN": OperationRejected,
        "INSUFFICIENT_FUNDS": InsufficientFunds,
        "INSUFFICIENT_MARGIN": InsufficientFunds,
        "INVALID_ASSET": BadRequest,
        "INVALID_MARKET": BadSymbol,
        "INVALID_SIGNATURE": AuthenticationError,
        "INVALID_SYMBOL": BadSymbol,
        "NOT_IMPLEMENTED": OperationFailed,
        "ORDER_LIMIT": OperationRejected,
        "RATE_LIMIT_EXCEEDED": RateLimitExceeded,
        "UNAUTHORIZED": AuthenticationError,
    },
},
```

**Step 3: Implement error handler method**

Ensure handle_errors method exists and processes these exceptions.

**Step 4: Test error handling**

Run: `pytest tests/api/test_backpack.py::test_error_handling -v`
Expected: PASS

**Step 5: Commit**

```bash
git add api/backpack.py
git commit -m "feat(backpack): add comprehensive error code mapping

- Add 15+ Backpack-specific error codes
- Follow CCXT error handling pattern"
```

---

## Phase 2: Declarative API Endpoint Definitions

### Task 3: Add API Endpoint Declarations to Aster

**Files:**
- Modify: `api/aster.py:22-88` (describe method)

**Current State:**
Aster uses hardcoded endpoint strings in each fetch method (e.g., `"fapi/v1/exchangeInfo"`). CCXT declares all endpoints in `describe()` for automatic method generation.

**Step 1: Add 'api' section to describe() method**

```python
def describe(self) -> Dict[str, Any]:
    return self.deep_extend(
        super(aster, self).describe(),
        {
            "id": "aster",
            "name": "Aster Futures",
            "countries": ["SG"],
            "rateLimit": 50,
            "version": "v1",
            "pro": False,
            "has": {
                # ... existing has declarations
            },
            "timeframes": {
                # ... existing timeframes
            },
            "urls": {
                # ... existing urls
            },
            "api": {
                "public": {
                    "get": [
                        "fapi/v1/ping",
                        "fapi/v1/time",
                        "fapi/v1/exchangeInfo",
                        "fapi/v1/depth",
                        "fapi/v1/trades",
                        "fapi/v1/klines",
                        "fapi/v1/ticker/24hr",
                        "fapi/v1/ticker/price",
                    ],
                },
                "private": {
                    "get": [
                        "fapi/v1/order",
                        "fapi/v1/openOrders",
                        "fapi/v1/allOrders",
                        "fapi/v2/balance",
                        "fapi/v2/positionRisk",
                        "fapi/v1/userTrades",
                    ],
                    "post": [
                        "fapi/v1/order",
                    ],
                    "delete": [
                        "fapi/v1/order",
                        "fapi/v1/allOpenOrders",
                    ],
                },
            },
            "options": {
                # ... existing options
            },
            "exceptions": {
                # ... expanded exceptions from Task 1
            },
        },
    )
```

**Step 2: Update methods to reference API declarations**

Instead of hardcoded strings, reference the API structure (for documentation purposes - we're not auto-generating yet):

```python
def fetch_markets(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    # Before: response = self.request("fapi/v1/exchangeInfo", "public", "GET", params or {})
    # After (with comment showing it's from api declaration):
    response = self.request("fapi/v1/exchangeInfo", "public", "GET", params or {})  # api['public']['get']
```

**Step 3: Add comments documenting endpoint usage**

Add docstrings to key methods referencing which API endpoint they use.

**Step 4: Verify no functionality broken**

Run: `pytest tests/api/test_aster.py -v`
Expected: All tests PASS (no behavior change, only documentation)

**Step 5: Commit**

```bash
git add api/aster.py
git commit -m "feat(aster): add declarative API endpoint definitions

- Add 'api' section to describe() following CCXT pattern
- Document all public and private endpoints
- No functional changes, improved documentation"
```

---

### Task 4: Add API Endpoint Declarations to Backpack

**Files:**
- Modify: `api/backpack.py` (describe method)

**Step 1: Read exchanges/backpack.py API structure**

Extract the complete API endpoint structure from the generated file.

**Step 2: Add 'api' section to backpack describe()**

Add comprehensive endpoint declarations based on CCXT pattern:

```python
"api": {
    "public": {
        "get": {
            "api/v1/assets": 1,
            "api/v1/markets": 1,
            "api/v1/ticker": 1,
            "api/v1/tickers": 1,
            "api/v1/depth": 1,
            "api/v1/klines": 1,
            "api/v1/trades": 1,
            "api/v1/time": 1,
            "api/v1/status": 1,
        },
    },
    "private": {
        "get": {
            "api/v1/capital": 1,
            "api/v1/order": 1,
            "api/v1/orders": 1,
            "wapi/v1/history/fills": 1,
        },
        "post": {
            "api/v1/order": 1,
            "api/v1/orders": 1,
        },
        "delete": {
            "api/v1/order": 1,
            "api/v1/orders": 1,
        },
    },
},
```

**Step 3: Test no regressions**

Run: `pytest tests/api/test_backpack.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add api/backpack.py
git commit -m "feat(backpack): add declarative API endpoint definitions"
```

---

## Phase 3: Enhanced Metadata & Configuration

### Task 5: Expand Aster's describe() with CCXT-style metadata

**Files:**
- Modify: `api/aster.py:22-88`

**Step 1: Add missing metadata fields**

CCXT includes extensive metadata. Add these fields:

```python
{
    "id": "aster",
    "name": "Aster Futures",
    "countries": ["SG"],
    "rateLimit": 333,  # Update to match exchanges/aster.py (3 req/s = 333ms)
    "hostname": "asterdex.com",  # Add hostname
    "certified": False,  # Add certification status
    "pro": True,  # Update - Aster supports WebSocket
    "version": "v1",
    "dex": True,  # Aster is a DEX
    "has": {
        # Expand has object with all capabilities
        "CORS": None,
        "spot": False,
        "margin": False,
        "swap": True,
        "future": False,
        "option": False,
        "addMargin": True,
        "cancelAllOrders": True,
        "cancelOrder": True,
        "createOrder": True,
        "fetchBalance": True,
        "fetchFundingRate": True,
        "fetchFundingRateHistory": True,
        "fetchLeverage": "emulated",  # Can be derived from other data
        "fetchMarkets": True,
        "fetchMyTrades": True,
        "fetchOHLCV": True,
        "fetchOpenOrders": True,
        "fetchOrder": True,
        "fetchOrderBook": True,
        "fetchPositions": True,
        "fetchTicker": True,
        "fetchTickers": True,
        "fetchTrades": True,
        "setLeverage": True,
        "setMarginMode": True,
        "transfer": True,
    },
    "urls": {
        "logo": "https://github.com/user-attachments/assets/4982201b-73cd-4d7a-8907-e69e239e9609",
        "www": "https://www.asterdex.com/en",
        "api": {
            "fapiPublic": "https://fapi.asterdex.com/fapi",
            "fapiPrivate": "https://fapi.asterdex.com/fapi",
            "sapiPublic": "https://sapi.asterdex.com/api",
            "sapiPrivate": "https://sapi.asterdex.com/api",
        },
        "doc": "https://github.com/asterdex/api-docs",
        "fees": "https://docs.asterdex.com/product/asterex-simple/fees-and-slippage",
        "referral": {
            "url": "https://www.asterdex.com/en/referral/aA1c2B",
            "discount": 0.1,
        },
    },
    "fees": {
        "trading": {
            "tierBased": True,
            "percentage": True,
            "maker": 0.0001,  # 0.01%
            "taker": 0.00035,  # 0.035%
        },
    },
    "precisionMode": TICK_SIZE,  # Need to import from base
}
```

**Step 2: Import required constants**

```python
from .base.decimal_to_precision import TICK_SIZE
```

**Step 3: Test metadata completeness**

Run: `pytest tests/api/test_aster.py::test_describe -v`
Expected: describe() returns comprehensive metadata

**Step 4: Commit**

```bash
git add api/aster.py
git commit -m "feat(aster): expand describe() with comprehensive metadata

- Add hostname, certified, dex flags
- Expand 'has' capabilities to 30+ features
- Add fee structure
- Add referral URLs and documentation links
- Set precisionMode to TICK_SIZE"
```

---

### Task 6: Expand Backpack's describe() with CCXT-style metadata

**Files:**
- Modify: `api/backpack.py`

**Step 1: Add comprehensive metadata**

Based on exchanges/backpack.py:

```python
{
    "id": "backpack",
    "name": "Backpack",
    "countries": ["JP"],
    "rateLimit": 50,
    "version": "v1",
    "certified": False,
    "pro": True,  # WebSocket support
    "has": {
        # Expand to 80+ capability flags from exchanges/backpack.py
        "CORS": None,
        "spot": True,
        "margin": True,
        "swap": True,
        "future": False,
        "option": False,
        # ... add all other capabilities
    },
    "timeframes": {
        # ... existing timeframes
    },
    "urls": {
        "logo": "https://github.com/user-attachments/assets/cc04c278-679f-4554-9f72-930dd632b80f",
        "www": "https://backpack.exchange/",
        "api": {
            "public": "https://api.backpack.exchange",
            "private": "https://api.backpack.exchange",
        },
        "doc": "https://docs.backpack.exchange/",
        "referral": "https://backpack.exchange/join/ccxt",
    },
    "precisionMode": TICK_SIZE,
    "options": {
        "recvWindow": 5000,
        "networks": {
            "ERC20": "Ethereum",
            "SOL": "Solana",
            "ARB": "Arbitrum",
            # ... add network mappings
        },
    },
}
```

**Step 2: Import TICK_SIZE constant**

```python
from .base.decimal_to_precision import TICK_SIZE
```

**Step 3: Test**

Run: `pytest tests/api/test_backpack.py::test_describe -v`
Expected: PASS

**Step 4: Commit**

```bash
git add api/backpack.py
git commit -m "feat(backpack): expand describe() with comprehensive metadata"
```

---

## Phase 4: Improved Data Parsing Patterns

### Task 7: Add parse_ticker improvements to Aster

**Files:**
- Modify: `api/aster.py:188-214`

**Current State:**
Current parse_ticker is basic. CCXT's version includes bid/ask, vwap, and better null handling.

**Step 1: Enhance parse_ticker with additional fields**

```python
def parse_ticker(self, ticker: Dict[str, Any], market: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    market_id = self.safe_string(ticker, "symbol")
    symbol = self.safe_symbol(market_id, market)
    timestamp = self.safe_integer(ticker, "closeTime") or self.safe_integer(ticker, "time")
    last = self.safe_string_2(ticker, "lastPrice", "price")

    # Add bid/ask prices
    bid = self.safe_string(ticker, "bidPrice")
    ask = self.safe_string(ticker, "askPrice")

    # Calculate VWAP if possible
    base_volume = self.safe_string(ticker, "volume")
    quote_volume = self.safe_string(ticker, "quoteVolume")
    vwap = None
    if quote_volume is not None and base_volume is not None:
        vwap = Precise.string_div(quote_volume, base_volume)

    return self.safe_ticker(
        {
            "symbol": symbol,
            "timestamp": timestamp,
            "datetime": self.iso8601(timestamp),
            "high": self.safe_string(ticker, "highPrice"),
            "low": self.safe_string(ticker, "lowPrice"),
            "bid": bid,
            "bidVolume": self.safe_string(ticker, "bidQty"),
            "ask": ask,
            "askVolume": self.safe_string(ticker, "askQty"),
            "vwap": vwap,
            "open": self.safe_string(ticker, "openPrice"),
            "close": last,
            "last": last,
            "previousClose": None,
            "change": self.safe_string(ticker, "priceChange"),
            "percentage": self.safe_string(ticker, "priceChangePercent"),
            "average": None,
            "baseVolume": base_volume,
            "quoteVolume": quote_volume,
            "info": ticker,
        },
        market,
    )
```

**Step 2: Test enhanced ticker parsing**

Run: `pytest tests/api/test_aster.py::test_parse_ticker -v`
Expected: Ticker includes bid/ask/vwap

**Step 3: Commit**

```bash
git add api/aster.py
git commit -m "feat(aster): enhance parse_ticker with bid/ask and vwap

- Add bid, ask, bidVolume, askVolume fields
- Calculate vwap from volume data
- Improve null safety"
```

---

### Task 8: Add safe_* helper methods pattern

**Files:**
- Verify: `api/base/exchange.py` has these methods
- Document: Usage in aster.py and backpack.py

**Step 1: Verify base Exchange class has safe_* helpers**

Read base/exchange.py to confirm it has:
- `safe_string`, `safe_string_2`, `safe_integer`, `safe_number`
- `safe_dict`, `safe_list`, `safe_bool`
- `safe_currency_code`, `safe_symbol`

**Step 2: Document pattern in docstring**

Add comment explaining CCXT's safe access pattern:

```python
# CCXT Pattern: safe_* methods handle null/undefined gracefully
# - safe_string(dict, 'key', default=None) - returns string or None
# - safe_integer(dict, 'key') - converts to int safely
# - safe_number(dict, 'key') - converts to float safely
# - safe_string_2(dict, 'key1', 'key2') - tries key1, then key2
```

**Step 3: Review current usage**

Ensure all dictionary access uses safe_* methods, not direct access.

**Step 4: No commit needed (documentation only)**

---

## Phase 5: Options and Feature Flags

### Task 9: Add options pattern to Aster

**Files:**
- Modify: `api/aster.py:71-74`

**Current State:**
Minimal options. CCXT uses extensive options for runtime configuration.

**Step 1: Expand options dictionary**

```python
"options": {
    "recvWindow": 10 * 1000,  # 10 sec default
    "defaultTimeInForce": "GTC",  # Good Till Cancel
    "defaultType": "swap",  # Default market type
    "accountsByType": {
        "spot": "SPOT",
        "future": "FUTURE",
        "linear": "FUTURE",
        "swap": "FUTURE",
    },
    "networks": {
        "ERC20": "ETH",
        "BEP20": "BSC",
        "ARB": "Arbitrum",
    },
    "networksToChainId": {
        "ETH": 1,
        "BSC": 56,
        "Arbitrum": 42161,
    },
},
```

**Step 2: Use options in methods**

Update methods to respect options:

```python
def create_order(...):
    # Use defaultTimeInForce from options if not specified
    time_in_force = self.safe_string(params, "timeInForce")
    if time_in_force is None:
        time_in_force = self.safe_string(self.options, "defaultTimeInForce", "GTC")
```

**Step 3: Test options usage**

Run: `pytest tests/api/test_aster.py::test_options -v`
Expected: Options properly applied

**Step 4: Commit**

```bash
git add api/aster.py
git commit -m "feat(aster): expand options for runtime configuration

- Add defaultTimeInForce option
- Add network mapping options
- Use options in create_order"
```

---

### Task 10: Add options pattern to Backpack

**Files:**
- Modify: `api/backpack.py`

**Step 1: Add comprehensive options from exchanges/backpack.py**

```python
"options": {
    "recvWindow": 5000,
    "brokerId": "",
    "timeDifference": 0,
    "adjustForTimeDifference": False,
    "networks": {
        "SOL": "Solana",
        "ERC20": "Ethereum",
        "ARB": "Arbitrum",
        "BASE": "Base",
        # ... more networks
    },
},
```

**Step 2: Test**

Run: `pytest tests/api/test_backpack.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add api/backpack.py
git commit -m "feat(backpack): add runtime configuration options"
```

---

## Final Review & Documentation

### Task 11: Document CCXT patterns learned

**Files:**
- Create: `docs/ccxt-patterns-learned.md`

**Step 1: Write documentation**

```markdown
# CCXT Patterns Learned

## 1. Comprehensive Error Handling
- Map ALL exchange error codes to typed exceptions
- Use both exact matching (error codes) and broad matching (error messages)
- Group errors by category (network, validation, business logic)

## 2. Declarative API Definitions
- Declare all endpoints in `describe()['api']`
- Enables auto-documentation and future auto-generation
- Centralized endpoint management

## 3. Rich Metadata in describe()
- 80+ capability flags in `has` object
- Precise rate limits, precision modes
- URLs for docs, fees, referrals
- Network mappings

## 4. Safe Data Access Pattern
- Never access dicts directly: use safe_string(), safe_integer()
- Graceful handling of missing/null data
- Type conversion built-in

## 5. Runtime Configuration via options
- Allow users to override defaults
- Network mappings, timeInForce defaults, etc.
- Backward compatible

## Benefits Observed
- More robust error handling = better debugging
- Consistent data structures = easier integration
- Extensive metadata = self-documenting code
```

**Step 2: Commit documentation**

```bash
git add docs/ccxt-patterns-learned.md
git commit -m "docs: document CCXT patterns learned during refactor"
```

---

### Task 12: Create comparison table

**Files:**
- Create: `docs/before-after-comparison.md`

**Step 1: Write comparison**

```markdown
# Before/After Refactoring Comparison

| Aspect | Before | After | Benefit |
|--------|--------|-------|---------|
| Error Codes | 8 mapped | 40+ mapped | Better error diagnosis |
| API Endpoints | Hardcoded | Declared | Self-documenting |
| has flags | 12 | 30+ | Clear capabilities |
| Metadata | Basic | Comprehensive | Production-ready |
| Options | 2 fields | 10+ fields | Configurable |
| Pattern Match | No | Yes | Catches more errors |
```

**Step 2: Commit**

```bash
git add docs/before-after-comparison.md
git commit -m "docs: add before/after refactoring comparison"
```

---

## Testing & Validation

### Task 13: Run full test suite

**Step 1: Run all Aster tests**

Run: `pytest tests/api/test_aster.py -v`
Expected: All tests PASS

**Step 2: Run all Backpack tests**

Run: `pytest tests/api/test_backpack.py -v`
Expected: All tests PASS

**Step 3: Run integration tests if available**

Run: `pytest tests/integration/ -v`
Expected: No regressions

**Step 4: Manual verification**

Test basic operations:
```python
from api.aster import aster
exchange = aster()
markets = exchange.fetch_markets()
print(f"Loaded {len(markets)} markets")
```

**Step 5: Document test results**

Create test summary in plan completion notes.

---

## Completion Checklist

- [ ] Phase 1: Enhanced error handling (Tasks 1-2)
- [ ] Phase 2: Declarative API definitions (Tasks 3-4)
- [ ] Phase 3: Enhanced metadata (Tasks 5-6)
- [ ] Phase 4: Improved parsing (Tasks 7-8)
- [ ] Phase 5: Options pattern (Tasks 9-10)
- [ ] Documentation (Tasks 11-12)
- [ ] Testing (Task 13)

## Notes

**What we learned from CCXT:**
1. Comprehensive error mapping prevents debugging nightmares
2. Declarative API structure enables tooling and auto-generation
3. Rich metadata makes exchanges self-documenting
4. Safe access patterns prevent null pointer errors
5. Options allow users to customize behavior

**What we didn't adopt (yet):**
- Auto-generating methods from API declarations (future enhancement)
- ImplicitAPI pattern (requires more infrastructure)
- Rate limiter implementation (could be Phase 6)

**Next Steps (Future):**
- Add rate limiting with leaky bucket algorithm
- Implement ImplicitAPI for method auto-generation
- Add WebSocket integration patterns from CCXT Pro
