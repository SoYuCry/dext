"""Example 6: Variational RFQ Quote Polling.

Demonstrates using Variational (Omni) RFQ quote polling through
the unified dispatcher architecture.
"""
import asyncio
import os
from decimal import Decimal

from exchanges.variational import VariationalClient
from exchanges.ws import create_dispatcher, VariationalPricePoller


async def main():
    """Monitor Variational RFQ quotes for ETH perpetual."""
    # Get credentials from environment
    connected_address = os.getenv("VARIATIONAL_CONNECTED_ADDRESS")
    cookie = os.getenv("VARIATIONAL_COOKIE")

    if not connected_address or not cookie:
        print("ERROR: Set VARIATIONAL_CONNECTED_ADDRESS and VARIATIONAL_COOKIE")
        return

    # Create Variational client
    config = {
        "connected_address": connected_address,
        "cookie": cookie,
    }
    client = VariationalClient(config)

    # Create dispatcher
    dispatcher = create_dispatcher()

    # Define instrument (ETH USDC perpetual)
    instrument = {
        "underlying": "ETH",
        "settlement_asset": "USDC",
        "instrument_type": "perpetual",
    }

    # Create RFQ price poller
    poller = VariationalPricePoller(
        client=client,
        instrument=instrument,
        qty=Decimal("10.0"),  # Quote size
        on_event=dispatcher.on_raw_event,
        interval=2.0,  # Poll every 2 seconds
    )

    # Start polling
    poller_task = asyncio.create_task(poller.run_forever())

    try:
        print("Polling Variational RFQ quotes... (Ctrl+C to exit)")
        print()

        while True:
            bbo = await dispatcher.get_market_data()

            print(f"[RFQ Quote] {bbo.symbol}")
            print(f"  Bid: {bbo.data.bid}")
            print(f"  Ask: {bbo.data.ask}")
            print(f"  Spread: {bbo.data.spread} ({bbo.data.spread_bps:.2f} bps)")
            print(f"  Quote ID: {bbo.raw.get('quote_id') if bbo.raw else 'N/A'}")
            print(f"  Latency: {bbo.metadata.latency_ms}ms")
            print()

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await poller.stop()
        await poller_task


if __name__ == "__main__":
    asyncio.run(main())
