# Real-Time Monitoring Panel Design

**Date:** 2026-01-17
**Status:** Approved
**Purpose:** Build a standalone real-time monitoring panel for Aster and Backpack trading activity

## Overview

A simple, self-contained web-based monitoring panel that displays real-time positions, open orders, and recent fills from Aster and Backpack exchanges. The panel is designed to be moved to a separate project later, ensuring full independence from the main codebase.

## Architecture

### Backend (Already Implemented)

**Components:**
- `panel/collector.py`: Subscribes to Aster and Backpack user WebSocket streams for real-time order and fill updates. Polls positions via REST API every 5 seconds as backup.
- `panel/server.py`: WebSocket server on `127.0.0.1:8765` that broadcasts state updates to connected frontend clients
- `panel/config.py`: Environment-based configuration for API credentials and symbols

**Data Flow:**
```
Aster WS → Collector → Server → Frontend
Backpack WS → Collector → Server → Frontend
REST APIs → Collector → Server → Frontend (positions polling)
```

**State Structure:**
```json
{
  "timestamp": "2026-01-17T...",
  "aster": {
    "orders": [...],
    "fills": [...],
    "position": {...}
  },
  "backpack": {
    "orders": [...],
    "fills": [...],
    "position": {...}
  }
}
```

### Frontend (To Implement)

**Technology Stack:**
- Single HTML file: `panel/static/index.html`
- Vanilla JavaScript (no frameworks)
- Self-contained CSS (no external dependencies)
- WebSocket client for real-time updates

**Connection Management:**
- Connect to `ws://127.0.0.1:8765`
- Auto-reconnect with exponential backoff: 1s → 2s → 4s → 8s (max)
- Connection status indicator
- Initial state snapshot on connect

## UI Layout

```
┌─────────────────────────────────────────────┐
│ Trading Panel - Aster & Backpack            │
│ Status: 🟢 Connected | Last Update: HH:MM:SS│
├─────────────────────────────────────────────┤
│                                             │
│ POSITIONS                                   │
│ ┌──────────────────┬──────────────────────┐│
│ │ Aster (XAU/USDT) │ Backpack (PAXG_USDC) ││
│ │ Total: ...       │ Total: ...           ││
│ │ Free: ...        │ Free: ...            ││
│ │ Used: ...        │ Used: ...            ││
│ └──────────────────┴──────────────────────┘│
│                                             │
│ OPEN ORDERS                                 │
│ ┌──────────────────┬──────────────────────┐│
│ │ Aster Orders     │ Backpack Orders      ││
│ │ [Table]          │ [Table]              ││
│ └──────────────────┴──────────────────────┘│
│                                             │
│ RECENT FILLS                                │
│ ┌──────────────────┬──────────────────────┐│
│ │ Aster Fills      │ Backpack Fills       ││
│ │ [Table]          │ [Table]              ││
│ └──────────────────┴──────────────────────┘│
└─────────────────────────────────────────────┘
```

## Display Details

### Positions Section
- Display key balances: USDT, XAU for Aster; USDC, PAXG for Backpack
- Show total, free, and used balances
- Flash highlight on balance changes
- Last update timestamp

### Orders Section
Columns: Symbol | Side | Type | Price | Quantity | Filled | Status
- Sort by timestamp (newest first)
- Color coding: Buy=green, Sell=red
- Empty state: "No open orders"

### Fills Section
Columns: Time | Symbol | Side | Price | Quantity | Fee | M/T
- Show last 5-10 fills per exchange
- Newest at top
- Flash animation on new fill
- M/T = Maker/Taker indicator

## Visual Design

**Theme:**
- Dark background for reduced eye strain during monitoring
- Light text with good contrast
- Monospaced font for numerical data

**Colors:**
- Buy/Long: Green (#4caf50)
- Sell/Short: Red (#f44336)
- Neutral: Gray
- Connected: Green, Disconnected: Red

**Animations:**
- Flash effect on data updates (brief yellow highlight)
- Smooth transitions

## Independence Considerations

The panel is designed to be moved to a separate project:
- No dependencies on parent project except for `api` module imports
- Self-contained configuration via environment variables
- Static assets in dedicated `static/` folder
- Clear separation of concerns

When moving to separate project:
1. Copy `panel/` folder
2. Copy `api/` folder (or rewrite to use REST/WS directly)
3. Update imports in `collector.py`
4. Set environment variables
5. Run `python -m panel.server`

## Testing Plan

1. Start the server: `python -m panel.server`
2. Open browser to `http://127.0.0.1:8765/index.html`
3. Verify WebSocket connection
4. Verify positions display correctly
5. Place test orders and verify they appear
6. Execute fills and verify they appear
7. Test reconnection by restarting server
8. Verify auto-reconnect works

## Files to Create

- `panel/static/index.html` - Complete frontend implementation

## Success Criteria

- ✅ Real-time display of positions from both exchanges
- ✅ Real-time display of open orders
- ✅ Real-time display of recent fills
- ✅ Auto-reconnect on disconnect
- ✅ Clean, readable UI
- ✅ No external dependencies
- ✅ Ready for live trading deployment
