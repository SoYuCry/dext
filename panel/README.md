# Real-Time Trading Panel

A simple, standalone real-time monitoring panel for Aster and Backpack exchanges.

## Features

- **Real-time positions**: Monitor your balances and positions on both exchanges
- **Open orders**: Track all active orders with live updates
- **Recent fills**: View execution history (last 10 fills per exchange)
- **Auto-reconnect**: Robust WebSocket connection with automatic reconnection
- **Self-contained**: Single HTML file frontend, no external dependencies

## Quick Start

### 1. Set Environment Variables

Create or update your `.env` file with:

```bash
# Aster credentials
ASTER_API_KEY=your_aster_api_key
ASTER_SECRET_KEY=your_aster_secret

# Backpack credentials
BACKPACK_API_KEY=your_backpack_api_key
BACKPACK_SECRET=your_backpack_secret

# Trading symbols (optional)
ASTER_SYMBOL=XAUUSDT
BACKPACK_SYMBOL=PAXG_USDC_PERP

# Server configuration (optional)
PANEL_HOST=127.0.0.1
PANEL_PORT=8765
```

### 2. Run the Server

From the project root directory:

```bash
python -m panel
```

The server will start on `http://127.0.0.1:8765`

### 3. Open the Frontend

Open your browser to:

```
http://127.0.0.1:8765/
```

You should see real-time updates of your positions, orders, and fills.

## Architecture

```
┌─────────────────────────────────────────┐
│           Browser Frontend              │
│         (panel/static/index.html)       │
└──────────────┬──────────────────────────┘
               │ WebSocket
               │ (ws://127.0.0.1:8765)
┌──────────────┴──────────────────────────┐
│         WebSocket Server                │
│          (panel/server.py)              │
└──────────────┬──────────────────────────┘
               │
┌──────────────┴──────────────────────────┐
│         Data Collector                  │
│        (panel/collector.py)             │
└─────┬────────────────────────┬──────────┘
      │                        │
      │ WebSocket              │ WebSocket
      │ (User Streams)         │ (User Streams)
      │                        │
┌─────▼──────┐          ┌──────▼─────┐
│   Aster    │          │  Backpack  │
│  Exchange  │          │  Exchange  │
└────────────┘          └────────────┘
```

## Components

### Backend

- **`collector.py`**: Subscribes to user WebSocket streams from both exchanges, receives real-time order and fill updates, polls positions via REST API every 5 seconds
- **`server.py`**: WebSocket server that broadcasts state updates to connected frontend clients
- **`config.py`**: Environment-based configuration for API credentials

### Frontend

- **`static/index.html`**: Self-contained single-page application with vanilla JavaScript
  - Dark theme optimized for monitoring
  - Auto-reconnecting WebSocket client
  - Real-time data updates with flash animations
  - Responsive layout

## Data Flow

1. **Collector** connects to Aster and Backpack user WebSocket streams
2. Receives real-time updates for:
   - Order creation, updates, fills, cancellations
   - Trade executions
3. Polls position data every 5 seconds via REST API
4. **Server** broadcasts updates to all connected browser clients
5. **Frontend** displays data in clean, organized tables

## Moving to Separate Project

The panel is designed to be easily moved to a standalone project:

1. Copy the `panel/` folder
2. Copy the `api/` folder (or rewrite to use REST/WS directly)
3. Update imports in `collector.py` if needed
4. Install dependencies: `pip install websockets python-dotenv pynacl requests`
5. Run with `python -m panel`

## Troubleshooting

### WebSocket won't connect

- Ensure the server is running (`python -m panel`)
- Check the browser console for errors
- Verify port 8765 is not blocked by firewall

### No data showing

- Verify your API credentials are set correctly in `.env`
- Check that you have open orders or positions on the exchanges
- Look at the server console output for error messages

### Auto-reconnect not working

- The frontend will automatically reconnect with exponential backoff (1s, 2s, 4s, 8s)
- Check browser console for WebSocket connection errors

## Next Steps

Before running in production:

1. Test with small orders first
2. Verify all fills and orders appear correctly
3. Monitor for any WebSocket disconnections
4. Consider adding SSL/TLS for production deployment

## License

Part of the dext trading system.
