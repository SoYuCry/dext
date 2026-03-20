"""Example 3: Order Updates Monitoring.

Demonstrates monitoring order status changes and fills from user data streams.
"""
import asyncio
import os

from exchanges.ws import create_dispatcher, BackpackUserWS
from exchanges.ws.types import OrderStatus, EventType


async def main():
    """Monitor Backpack user order updates."""
    # Get credentials from environment
    api_key = os.getenv("BACKPACK_API_KEY")
    secret = os.getenv("BACKPACK_SECRET_KEY")

    if not api_key or not secret:
        print("ERROR: Set BACKPACK_API_KEY and BACKPACK_SECRET_KEY environment variables")
        return

    # Create dispatcher
    dispatcher = create_dispatcher()

    # Connect to Backpack user stream
    user_ws = BackpackUserWS(
        api_key=api_key,
        secret_key=secret,
        on_event=dispatcher.on_raw_event,
    )

    # Start connection
    ws_task = asyncio.create_task(user_ws.run_forever())

    # Monitor order updates
    try:
        print("Listening for order updates... (Ctrl+C to exit)")
        print()

        while True:
            order = await dispatcher.get_order_update()

            print(f"[{order.metadata.event_type.value}] {order.exchange} {order.symbol}")
            print(f"  Order ID: {order.data.order_id}")
            print(f"  Client ID: {order.data.client_order_id}")
            print(f"  Side: {order.data.side.value}")
            print(f"  Status: {order.data.status.value}")
            print(f"  Price: {order.data.price}")
            print(f"  Amount: {order.data.amount}")
            print(f"  Filled: {order.data.filled}")
            print(f"  Remaining: {order.data.remaining}")

            # Check for fills
            if order.metadata.event_type == EventType.FILL_UPDATE:
                print(f"  ✅ FILL: {order.data.filled_amount} @ {order.data.fill_price}")

            # Check for complete fills
            if order.data.status == OrderStatus.FILLED:
                print(f"  ✅ ORDER COMPLETELY FILLED!")

            print()

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await user_ws.stop()
        await ws_task


if __name__ == "__main__":
    asyncio.run(main())
