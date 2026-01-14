"""CLI runner for the XAU arbitrage strategy."""
import asyncio
import os

from .config import ExchangeKeys, StrategyConfig
from .strategy import XauArbitrageStrategy


def load_config_from_env() -> StrategyConfig:
    aster = ExchangeKeys(
        api_key=os.getenv("ASTER_API_KEY", ""),
        secret=os.getenv("ASTER_SECRET_KEY"),
    )
    backpack = ExchangeKeys(
        api_key=os.getenv("BACKPACK_KEY", ""),
        secret=os.getenv("BACKPACK_SECRET"),
    )
    return StrategyConfig(
        aster=aster,
        backpack=backpack,
        dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
    )


async def main() -> None:
    config = load_config_from_env()
    strat = XauArbitrageStrategy(config)
    await strat.start()
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await strat.stop()


if __name__ == "__main__":
    asyncio.run(main())
