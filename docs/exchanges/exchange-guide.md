# Exchange API Documentation Index

Comprehensive guides for each supported exchange.

## Exchange Guides

### Production Exchanges

- **[Variational (Omni)](./variational.md)** - RFQ-based derivatives exchange
  - Cookie-based authentication
  - RFQ quote flow
  - Polling-based market data
  - Common issues and solutions

- **[Common Pitfalls](./common-pitfalls.md)** - Troubleshooting guide
  - 7 common integration errors
  - Solutions and preventive measures
  - Applicable to all exchanges

### Coming Soon

- **Aster** - Binance-style futures DEX (consolidating from `docs/aster_websocket_technical.md`)
- **Backpack** - Solana-based exchange (consolidating from `docs/backpack_websocket_technical.md`)
- **Lighter** - zkSync order book DEX (consolidating from `docs/lighter_websocket_technical.md`)
- **WebSocket Guide** - Comprehensive WebSocket patterns (consolidating from `docs/README_WebSocket.md` and `docs/websocket_订阅方式对比.md`)

## Quick Links

- [Main API README](../README.md) - Quick start and common patterns
- [Common Pitfalls](./common-pitfalls.md) - Troubleshooting guide
- [Variational Guide](./variational.md) - RFQ exchange documentation

## Documentation Status

| Exchange | REST API | WebSocket | User Stream | Status |
|----------|----------|-----------|-------------|--------|
| Variational | ✅ Complete | ✅ Complete | ✅ Complete | Done |
| Common Pitfalls | ✅ Complete | ✅ Complete | ✅ Complete | Done |
| Aster | 🚧 Pending | 🚧 Pending | 🚧 Pending | In Progress |
| Backpack | 🚧 Pending | 🚧 Pending | 🚧 Pending | In Progress |
| Lighter | 🚧 Pending | 🚧 Pending | ❌ N/A | In Progress |
| WebSocket Guide | 🚧 Pending | - | - | In Progress |

---

**Note**: Exchange-specific documentation is being consolidated from scattered technical docs into comprehensive guides. Check back soon for complete Aster, Backpack, and Lighter documentation.

**Last Updated**: 2026-01-18
