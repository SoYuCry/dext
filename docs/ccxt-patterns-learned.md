# CCXT Patterns Learned

## Overview

This document summarizes the key design patterns learned from CCXT (100+ exchange support, 40k+ GitHub stars) during the refactoring of Aster and Backpack exchange implementations.

## 1. Comprehensive Error Handling

**Pattern:**
- Map ALL exchange error codes to typed exceptions
- Use both exact matching (error codes) and broad matching (error messages)
- Group errors by category (network, validation, business logic)

**Implementation:**
```python
"exceptions": {
    "exact": {
        # 10xx - General Server or Network issues
        "-1000": OperationFailed,
        "-1001": NetworkError,
        "-1003": RateLimitExceeded,
        # ... 40+ more mappings
    },
    "broad": {
        # Pattern matching for error messages
        "has no position": InvalidOrder,
        "Invalid symbol": BadSymbol,
    },
}
```

**Benefits:**
- Granular error diagnosis (instead of generic ExchangeError)
- Enables proper retry logic (retry on NetworkError, don't retry on AuthenticationError)
- Better debugging experience for developers

**Before:** 8 error codes mapped
**After:** 40+ error codes with category grouping

---

## 2. Declarative API Definitions

**Pattern:**
- Declare all endpoints in `describe()['api']`
- Enables auto-documentation and future auto-generation
- Centralized endpoint management

**Implementation:**
```python
"api": {
    "public": {
        "get": [
            "fapi/v1/exchangeInfo",
            "fapi/v1/depth",
            "fapi/v1/ticker/24hr",
        ],
    },
    "private": {
        "get": ["fapi/v1/order"],
        "post": ["fapi/v1/order"],
        "delete": ["fapi/v1/order"],
    },
}
```

**Benefits:**
- Single source of truth for all endpoints
- Easy to see what APIs are available
- Enables tooling (auto-generate method stubs, API docs)
- Prevents endpoint URL typos

---

## 3. ImplicitAPI Pattern (Advanced)

**Pattern:**
- Define API endpoints as class attributes using Entry objects
- Auto-generate method names (camelCase and snake_case)
- Include rate limit cost information per endpoint

**Implementation:**
```python
# api/abstract/aster.py
class ImplicitAPI:
    public_get_fapi_v1_ping = publicGetFapiV1Ping = Entry(
        'fapi/v1/ping', 'public', 'GET', {'cost': 1}
    )
    private_post_fapi_v1_order = privatePostFapiV1Order = Entry(
        'fapi/v1/order', 'private', 'POST', {'cost': 1}
    )
```

**Benefits:**
- Reduces boilerplate code dramatically
- Automatic method generation: `exchange.publicGetFapiV1Ping()`
- Dual naming support: `publicGetFapiV1Ping` == `public_get_fapi_v1_ping`
- Rate limit information embedded in definition

---

## 4. Rich Metadata in describe()

**Pattern:**
- 80+ capability flags in `has` object
- Precise rate limits, precision modes
- URLs for docs, fees, referrals
- Network mappings for multi-chain assets

**Implementation:**
```python
{
    "id": "aster",
    "name": "Aster Futures",
    "countries": ["SG"],
    "rateLimit": 333,  # 3 req/s
    "hostname": "asterdex.com",
    "certified": False,
    "pro": True,  # WebSocket support
    "dex": True,  # Decentralized exchange
    "has": {
        "CORS": None,
        "spot": False,
        "swap": True,
        "fetchMarkets": True,
        "fetchTicker": True,
        # ... 30+ more capabilities
    },
    "urls": {
        "logo": "https://...",
        "www": "https://...",
        "doc": "https://...",
        "referral": {"url": "...", "discount": 0.1},
    },
    "fees": {
        "trading": {
            "maker": 0.0001,
            "taker": 0.00035,
        },
    },
    "precisionMode": TICK_SIZE,
}
```

**Benefits:**
- Self-documenting code
- Runtime feature detection: `if exchange.has['fetchOHLCV']:`
- Production-ready configuration out of the box
- Consistent structure across all exchanges

---

## 5. Safe Data Access Pattern

**Pattern:**
- Never access dicts directly - use `safe_*` methods
- Graceful handling of missing/null data
- Built-in type conversion

**Available Methods:**
- `safe_string(dict, 'key', default=None)` - returns string or None
- `safe_integer(dict, 'key')` - converts to int safely
- `safe_number(dict, 'key')` - converts to float safely
- `safe_string_2(dict, 'key1', 'key2')` - tries key1, then key2
- 55+ safe_* methods in base Exchange class

**Example:**
```python
# Bad (will crash if key missing)
price = ticker["lastPrice"]

# Good (returns None if missing)
price = self.safe_string(ticker, "lastPrice")

# Better (tries multiple keys)
price = self.safe_string_2(ticker, "lastPrice", "price")
```

**Benefits:**
- Prevents null pointer exceptions
- Handles API changes gracefully
- Consistent data type handling

---

## 6. Runtime Configuration via options

**Pattern:**
- Allow users to override defaults
- Network mappings, timeInForce defaults, etc.
- Backward compatible

**Implementation:**
```python
"options": {
    "recvWindow": 10 * 1000,  # 10 sec
    "defaultTimeInForce": "GTC",
    "defaultType": "swap",
    "accountsByType": {
        "spot": "SPOT",
        "swap": "FUTURE",
    },
    "networks": {
        "ERC20": "ETH",
        "BEP20": "BSC",
    },
}
```

**Usage:**
```python
# Use in methods
time_in_force = self.safe_string(params, "timeInForce")
if not time_in_force:
    time_in_force = self.safe_string(self.options, "defaultTimeInForce", "GTC")
```

**Benefits:**
- Users can customize behavior without code changes
- Supports multi-chain assets
- Maintains backward compatibility

---

## 7. Enhanced Data Parsing

**Pattern:**
- Include all available fields in parsed data
- Calculate derived fields (VWAP)
- Consistent field ordering across exchanges

**Example - parse_ticker:**
```python
def parse_ticker(self, ticker, market=None):
    # Extract all fields
    bid = self.safe_string(ticker, "bidPrice")
    ask = self.safe_string(ticker, "askPrice")

    # Calculate derived fields
    base_volume = self.safe_string(ticker, "volume")
    quote_volume = self.safe_string(ticker, "quoteVolume")
    vwap = None
    if quote_volume and base_volume:
        vwap = Precise.string_div(quote_volume, base_volume)

    return {
        "symbol": symbol,
        "timestamp": timestamp,
        "bid": bid,
        "ask": ask,
        "vwap": vwap,
        # ... all standard fields
    }
```

**Benefits:**
- Consistent data structure across exchanges
- No information loss
- Easier integration and comparison

---

## Key Success Factors

Why CCXT has 40k+ stars and supports 100+ exchanges:

1. **Unified API** - Write once, run on any exchange
2. **Comprehensive error handling** - Better debugging
3. **Declarative design** - Less boilerplate, more clarity
4. **Rich metadata** - Self-documenting, production-ready
5. **Safe access patterns** - Robust against API changes
6. **Runtime configuration** - Flexible without code changes
7. **Multi-language support** - JavaScript, Python, PHP, C#, Go

---

## What We Didn't Adopt (Yet)

- **Auto-generating methods from API declarations** - Requires more infrastructure
- **Rate limiter implementation** - Leaky bucket algorithm (future Phase 6)
- **WebSocket patterns from CCXT Pro** - Already have custom WS implementation

---

## Next Steps (Future Phases)

1. **Rate Limiting** - Implement leaky bucket algorithm
2. **Method Auto-generation** - Generate fetch methods from API declarations
3. **WebSocket Integration** - Adopt CCXT Pro patterns for `watch*` methods
4. **Multi-language Support** - Transpile to TypeScript/JavaScript
5. **Sandbox Support** - Add testnet/sandbox environment support

---

## References

- [CCXT GitHub](https://github.com/ccxt/ccxt)
- [CCXT Documentation](https://docs.ccxt.com/)
- [CCXT Manual](https://github.com/ccxt/ccxt/wiki/Manual)
