"""Example 4: Combined Market Data + Order Updates.

Demonstrates consuming both market data and order updates simultaneously
from separate queues.
"""
import asyncio
import os
from typing import Optional

from exchanges.ws import create_dispatcher, BackpackWS, BackpackUserWS
from exchanges.ws.types import BBOUpdate, OrderUpdate


class TradingMonitor:
    """Monitor market data and order updates together."""

    def __init__(self):
        self.latest_bbo: Optional[BBOUpdate] = None

    async def on_market_data(self, bbo: BBOUpdate) -> None:
        """Handle market data update."""
        self.latest_bbo = bbo
        print(f"📊 Market: {bbo.exchange} {bbo.symbol} | "
              f"Bid: {bbo.data.bid} | Ask: {bbo.data.ask} | "
              f"Spread: {bbo.data.spread_bps:.2f}bps")

    async def on_order_update(self, order: OrderUpdate) -> None:
        """Handle order update."""
        print(f"📝 Order: {order.data.order_id} | "
              f"Status: {order.data.status.value} | "
              f"Filled: {order.data.filled}/{order.data.amount}")

        # Compare fill price with current market
        if self.latest_bbo and order.data.fill_price:
            mid = (self.latest_bbo.data.bid + self.latest_bbo.data.ask) / 2
            diff = order.data.fill_price - mid
            print(f"   Fill price vs mid: {diff:+.4f}")


async def market_data_consumer(dispatcher, monitor):
    """Consume market data from queue."""
    while True:
        bbo = await dispatcher.get_market_data()
        await monitor.on_market_data(bbo)


async def order_update_consumer(dispatcher, monitor):
    """Consume order updates from queue."""
    while True:
        order = await dispatcher.get_order_update()
        await monitor.on_order_update(order)


async def main():
    """Run combined monitoring."""
    api_key = os.getenv("BACKPACK_API_KEY")
    secret = os.getenv("BACKPACK_SECRET_KEY")

    if not api_key or not secret:
        print("ERROR: Set BACKPACK_API_KEY and BACKPACK_SECRET_KEY")
        return

    # Create dispatcher
    dispatcher = create_dispatcher()

    # Filter to specific symbol
    dispatcher.set_filters(symbols=["SOL/USDC"])

    # Create monitor
    monitor = TradingMonitor()

    # Connect market data stream
    market_ws = BackpackWS(
        symbols=["SOL_USDC"],
        on_event=dispatcher.on_raw_event,
        include_depth=False,
    )

    # Connect user data stream
    user_ws = BackpackUserWS(
        api_key=api_key,
        secret_key=secret,
        on_event=dispatcher.on_raw_event,
    )

    # Start both WebSocket connections
    market_task = asyncio.create_task(market_ws.run_forever())
    user_task = asyncio.create_task(user_ws.run_forever())

    # Start both consumers (separate tasks for each queue)
    market_consumer_task = asyncio.create_task(
        market_data_consumer(dispatcher, monitor)
    )
    order_consumer_task = asyncio.create_task(
        order_update_consumer(dispatcher, monitor)
    )

    try:
        print("Monitoring market data and orders... (Ctrl+C to exit)")
        print()
        # Run forever
        await asyncio.gather(
            market_consumer_task,
            order_consumer_task,
        )
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await market_ws.stop()
        await user_ws.stop()
        await asyncio.gather(market_task, user_task)


if __name__ == "__main__":
    asyncio.run(main())
