<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/_static/logo.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/_static/logo-light.svg">
    <img alt="dext" src="docs/_static/logo-light.svg" width="280">
  </picture>

  <p><b>Decentralized EXchange Trading Library</b></p>

  [![PyPI](https://img.shields.io/pypi/v/dext)](https://pypi.org/project/dext/)
  [![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://github.com/SoYuCry/dext)
  [![License](https://img.shields.io/github/license/SoYuCry/dext)](https://github.com/SoYuCry/dext/blob/main/LICENSE)
  [![GitHub stars](https://img.shields.io/github/stars/SoYuCry/dext?style=social)](https://github.com/SoYuCry/dext/stargazers)
  [![GitHub issues](https://img.shields.io/github/issues/SoYuCry/dext)](https://github.com/SoYuCry/dext/issues)
</div>

---

**dext** is a lightweight, unified exchange library built for DeFi trading. Write one set of trading logic, run it on any supported DEX.

> **AI-Friendly Library**: dext is designed with clean, self-documenting APIs and structured error handling — ideal for AI agents, LLM-powered trading bots, and automated code generation. Every exchange method follows the same signature, making it easy for AI to reason about, generate, and debug trading code.

## Features

1. **Standardized API** across all exchanges — `fetch_ticker`, `create_order`, `cancel_order` work the same everywhere.
2. **DEX-native auth** — built-in support for zkSync signers, Ed25519, HMAC-SHA256, and cookie-based authentication.
3. **Real-time data pipeline** — WebSocket with three-stage pipeline (connection → normalization → dispatch) delivering unified `BBOUpdate` and `OrderUpdate` events.
4. **Minimal footprint** — focused dependency set, no bloat. Install and start trading in seconds.
5. **Type-safe** — PEP 561 compliant with `py.typed` marker. Full IDE auto-completion support.

## Installation

```bash
pip install dext
```

## Quick Start

```python
import dext

# List supported exchanges
print(dext.exchanges)
# ['aster', 'backpack', 'binance', 'lighter', 'variational']

# Instantiate an exchange
exchange = dext.lighter({'privateKey': '...'})

# Fetch market data
ticker = exchange.fetch_ticker('ETH/USDC')
book   = exchange.fetch_order_book('ETH/USDC')

# Place and cancel orders
order = exchange.create_order('ETH/USDC', 'limit', 'buy', 1.0, 2000)
exchange.cancel_order(order['id'], 'ETH/USDC')
```

## Supported Exchanges

| Exchange | Type | Auth | Market Data | Trading |
|---|---|---|:---:|:---:|
| **Aster** | Futures DEX | HMAC-SHA256 | REST, WS | REST |
| **Backpack** | Spot / Perps | Ed25519 | REST, WS | REST |
| **Binance** | Spot | HMAC-SHA256 | REST, WS | REST |
| **Lighter** | DEX | zkSync signer | REST, WS | REST |
| **Variational** | RFQ Perps | Cookie | Polling, WS | REST |

## API Reference

### REST Methods

| Method | Description |
|---|---|
| `fetch_markets` | List available trading pairs |
| `fetch_ticker` / `fetch_tickers` | Get latest price data |
| `fetch_order_book` | Get L2 order book |
| `fetch_ohlcv` | Get candlestick data |
| `create_order` / `create_orders` | Place new orders |
| `cancel_order` / `cancel_all_orders` | Cancel orders |
| `fetch_open_orders` / `fetch_orders` | Query order status |
| `fetch_balance` | Get account balances |
| `fetch_positions` | Get open positions |
| `fetch_my_trades` | Get trade history |

Not all methods are available on every exchange. Check `exchange.has['fetchPositions']` or the [per-exchange docs](docs/exchanges/).

### WebSocket

```python
import asyncio
from exchanges.ws import create_dispatcher, LighterWS

dispatcher = create_dispatcher(lighter_market_mapping={0: "ETH/USDC"})
ws = LighterWS(market_index=0, on_event=dispatcher.on_raw_event, bbo_only=True)

async def main():
    asyncio.create_task(ws.run_forever())
    while True:
        bbo = await dispatcher.get_market_data()  # BBOUpdate
        print(f"{bbo.symbol} bid={bbo.data.bid} ask={bbo.data.ask}")

asyncio.run(main())
```

### Error Handling

All exchanges raise from a shared exception hierarchy:

```
BaseError
├── ExchangeError
│   ├── AuthenticationError
│   ├── BadRequest
│   ├── InvalidOrder
│   │   └── OrderNotFound
│   ├── InsufficientFunds
│   ├── RateLimitExceeded
│   └── NotSupported
└── NetworkError
    ├── RequestTimeout
    └── ExchangeNotAvailable
```

```python
from dext import ExchangeError, InvalidOrder

try:
    exchange.create_order('ETH/USDC', 'limit', 'buy', 1.0, 2000)
except InvalidOrder as e:
    print(f"Bad order: {e}")
except ExchangeError as e:
    print(f"Exchange error: {e}")
```

## For AI Agents & LLMs

dext is built to work well with AI-powered development tools and autonomous trading agents:

- **Uniform interface** — every exchange has the same method signatures, making it trivial for LLMs to generate correct trading code without hallucinating exchange-specific APIs.
- **Structured errors** — exception hierarchy with clear error types (`InvalidOrder`, `InsufficientFunds`, `RateLimitExceeded`) enables AI agents to implement robust error recovery.
- **Capability discovery** — `exchange.has['fetchPositions']` lets agents introspect what an exchange supports at runtime.
- **Type hints** — PEP 561 compliant, so AI coding tools get full autocomplete and type checking.

## Star History

<div align="center">
  <a href="https://star-history.com/#SoYuCry/dext&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=SoYuCry/dext&type=Date&theme=dark">
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=SoYuCry/dext&type=Date">
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=SoYuCry/dext&type=Date" width="600">
    </picture>
  </a>
</div>

## Contributing

Contributions are welcome. Please open an issue first to discuss what you would like to change.

## License

[MIT](LICENSE)
