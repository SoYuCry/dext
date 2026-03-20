"""Example 1: Single Exchange BBO Monitoring.

Demonstrates basic usage of the unified WebSocket architecture to monitor
best bid/offer prices from a single exchange (Lighter).
"""
import asyncio
from decimal import Decimal

from exchanges.ws import create_dispatcher, LighterWS


async def main():
    """Monitor Lighter ETH/USDC BBO updates."""
    # Create dispatcher with market mapping
    dispatcher = create_dispatcher(
        lighter_market_mapping={
            0: "ETH/USDC",  # Market index 0 = ETH/USDC
        }
    )

    # Create Lighter WebSocket client in BBO-only mode
    ws = LighterWS(
        market_index=0,
        on_event=dispatcher.on_raw_event,
        bbo_only=True,  # Fast BBO-only mode (no full orderbook)
    )

    # Start WebSocket connection
    ws_task = asyncio.create_task(ws.run_forever())

    # Monitor BBO updates
    try:
        for i in range(10):  # Get 10 updates then exit
            bbo = await dispatcher.get_market_data()

            print(f"[{i+1}] {bbo.exchange} {bbo.symbol}")
            print(f"    Bid: {bbo.data.bid} x {bbo.data.bid_size}")
            print(f"    Ask: {bbo.data.ask} x {bbo.data.ask_size}")
            print(f"    Spread: {bbo.data.spread} ({bbo.data.spread_bps:.2f} bps)")
            print(f"    Latency: {bbo.metadata.latency_ms}ms")
            print()
    finally:
        # Clean shutdown
        await ws.stop()
        await ws_task


if __name__ == "__main__":
    asyncio.run(main())
