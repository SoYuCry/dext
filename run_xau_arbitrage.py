#!/usr/bin/env python3
"""XAU/PAXG arbitrage strategy runner.

Strategy: Capture big finger orders on Aster (low liquidity) by placing
staggered limit orders, then hedge immediately on Backpack.

Configuration:
- Three tiers: 30u @ ±0.15%, 30u @ ±0.25%, 40u @ ±0.40%
- Total exposure per side: 100 USD
- Aster (XAU) has poor liquidity, susceptible to large orders
- Backpack (PAXG) has better liquidity for hedging

Fees:
- Aster: Maker 0.005%, Taker 0.04%
- Backpack: Perp Maker 0.02%, Taker 0.05%
- Min profit target: ~10-15 bps (covers fees + slippage + risk premium)

Usage:
    # Dry run (default)
    python run_xau_arbitrage.py

    # Live trading (set DRY_RUN=false in .env)
    DRY_RUN=false python run_xau_arbitrage.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from strategies.xau_arbitrage.runner import main

if __name__ == "__main__":
    print("=" * 80)
    print("XAU/PAXG Arbitrage Strategy")
    print("=" * 80)
    print("Strategy: Multi-tier limit orders on Aster, hedge on Backpack")
    print("Tiers: 30u @ ±0.15%, 30u @ ±0.25%, 40u @ ±0.40%")
    print("Target: Capture big finger orders on low-liquidity Aster")
    print("=" * 80)
    print()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStrategy stopped by user")
    except Exception as e:
        print(f"\nStrategy error: {e}")
        raise
