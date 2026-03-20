"""Async utility helpers for exchange clients and strategies."""

import asyncio


async def async_with_timeout(func, *args, timeout_sec=10.0, **kwargs):
    """Run sync function in thread with timeout. Raises asyncio.TimeoutError if exceeded."""
    return await asyncio.wait_for(
        asyncio.to_thread(func, *args, **kwargs),
        timeout=timeout_sec,
    )
