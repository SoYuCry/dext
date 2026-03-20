"""Example 2: Multi-Exchange Arbitrage Monitoring.

Demonstrates monitoring price differences across multiple exchanges
to detect arbitrage opportunities.
"""
import asyncio
from decimal import Decimal
from typing import Dict

from exchanges.ws import create_dispatcher, LighterWS, BackpackWS


class ArbitrageMonitor:
    """Monitor price differences between exchanges."""

    def __init__(self, symbol: str, threshold_bps: Decimal):
        self.symbol = symbol
        self.threshold_bps = threshold_bps
        self.latest_prices: Dict[str, Decimal] = {}

    def update_price(self, exchange: str, mid_price: Decimal) -> None:
        """Update latest mid price and check for arbitrage."""
        self.latest_prices[exchange] = mid_price

        if len(self.latest_prices) >= 2:
            self._check_arbitrage()

    def _check_arbitrage(self) -> None:
        """Check if price difference exceeds threshold."""
        exchanges = list(self.latest_prices.keys())
        prices = list(self.latest_prices.values())

        for i in range(len(exchanges)):
            for j in range(i + 1, len(exchanges)):
                ex1, ex2 = exchanges[i], exchanges[j]
                p1, p2 = prices[i], prices[j]

                # Calculate spread in basis points
                mid = (p1 + p2) / 2
                spread_bps = abs(p1 - p2) / mid * 10000

                if spread_bps > self.threshold_bps:
                    if p1 > p2:
                        print(f"🚨 ARBITRAGE OPPORTUNITY!")
                        print(f"   Buy {ex2} @ {p2}, Sell {ex1} @ {p1}")
                    else:
                        print(f"🚨 ARBITRAGE OPPORTUNITY!")
                        print(f"   Buy {ex1} @ {p1}, Sell {ex2} @ {p2}")
                    print(f"   Spread: {spread_bps:.2f} bps")
                    print()


async def main():
    """Monitor SOL/USDC on Lighter and Backpack."""
    # Create dispatcher with mappings
    dispatcher = create_dispatcher(
        lighter_market_mapping={
            1: "SOL/USDC",  # Lighter market 1 = SOL/USDC
        }
    )

    # Filter to only process SOL/USDC
    dispatcher.set_filters(symbols=["SOL/USDC"])

    # Create arbitrage monitor (10 bps threshold)
    monitor = ArbitrageMonitor("SOL/USDC", Decimal("10"))

    # Connect to Lighter
    lighter_ws = LighterWS(
        market_index=1,
        on_event=dispatcher.on_raw_event,
        bbo_only=True,
    )

    # Connect to Backpack
    backpack_ws = BackpackWS(
        symbols=["SOL_USDC"],
        on_event=dispatcher.on_raw_event,
        include_depth=False,  # BBO only
    )

    # Start both connections
    lighter_task = asyncio.create_task(lighter_ws.run_forever())
    backpack_task = asyncio.create_task(backpack_ws.run_forever())

    # Monitor price updates
    try:
        while True:
            bbo = await dispatcher.get_market_data()

            # Calculate mid price
            mid = (bbo.data.bid + bbo.data.ask) / 2

            # Update monitor
            monitor.update_price(bbo.exchange, mid)

            # Print update
            print(f"{bbo.exchange:10} {bbo.symbol:10} mid={mid:8} spread={bbo.data.spread_bps:6.2f}bps")

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await lighter_ws.stop()
        await backpack_ws.stop()
        await asyncio.gather(lighter_task, backpack_task)


if __name__ == "__main__":
    asyncio.run(main())
