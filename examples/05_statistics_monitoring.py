"""Example 5: Statistics Monitoring.

Demonstrates using the dispatcher's built-in statistics to monitor
event throughput and queue health.
"""
import asyncio
from decimal import Decimal

from exchanges.ws import create_dispatcher, LighterWS, BackpackWS


async def stats_logger(dispatcher):
    """Periodically log dispatcher statistics."""
    while True:
        await asyncio.sleep(5.0)  # Log every 5 seconds
        dispatcher.log_stats()


async def main():
    """Monitor multiple exchanges with statistics logging."""
    # Create dispatcher with custom queue sizes
    dispatcher = create_dispatcher(
        lighter_market_mapping={0: "ETH/USDC", 1: "SOL/USDC"}
    )

    # Connect to multiple exchanges
    lighter_eth = LighterWS(
        market_index=0,
        on_event=dispatcher.on_raw_event,
        bbo_only=True,
    )

    lighter_sol = LighterWS(
        market_index=1,
        on_event=dispatcher.on_raw_event,
        bbo_only=True,
    )

    backpack = BackpackWS(
        symbols=["SOL_USDC", "BTC_USDC"],
        on_event=dispatcher.on_raw_event,
        include_depth=False,
    )

    # Start all connections
    tasks = [
        asyncio.create_task(lighter_eth.run_forever()),
        asyncio.create_task(lighter_sol.run_forever()),
        asyncio.create_task(backpack.run_forever()),
    ]

    # Start stats logger
    stats_task = asyncio.create_task(stats_logger(dispatcher))

    # Consume market data
    try:
        count = 0
        while True:
            bbo = await dispatcher.get_market_data()
            count += 1

            if count % 10 == 0:  # Print every 10th update
                print(f"[{count}] {bbo.exchange:10} {bbo.symbol:10} "
                      f"bid={bbo.data.bid} ask={bbo.data.ask} "
                      f"spread={bbo.data.spread_bps:.2f}bps")

                # Manual stats check
                stats = dispatcher.get_stats()
                print(f"      Queue sizes: market={stats['market_data_queue_size']} "
                      f"orders={stats['order_update_queue_size']}")
                print(f"      Normalized: {stats['market_data_normalized']} "
                      f"Errors: {stats['normalization_errors']} "
                      f"Drops: {stats['queue_full_drops']}")

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await lighter_eth.stop()
        await lighter_sol.stop()
        await backpack.stop()
        stats_task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
