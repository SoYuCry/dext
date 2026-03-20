"""Example 7: Error Handling and Reconnection.

Demonstrates robust error handling patterns including reconnection,
queue overflow handling, and graceful shutdown.
"""
import asyncio

from exchanges.ws import create_dispatcher, LighterWS
from exchanges.logger import setup_logger

logger = setup_logger("example")


class RobustMonitor:
    """Monitor with error handling and recovery."""

    def __init__(self):
        self.running = True
        self.error_count = 0
        self.max_errors = 10

    async def run_websocket(self, ws):
        """Run WebSocket with automatic reconnection."""
        while self.running:
            try:
                logger.info("Starting WebSocket connection...")
                await ws.run_forever()
            except Exception as exc:
                self.error_count += 1
                logger.error(f"WebSocket error ({self.error_count}): {exc}")

                if self.error_count >= self.max_errors:
                    logger.error("Too many errors, giving up")
                    self.running = False
                    break

                # Exponential backoff
                wait_time = min(2 ** self.error_count, 60)
                logger.info(f"Reconnecting in {wait_time}s...")
                await asyncio.sleep(wait_time)

    async def consume_market_data(self, dispatcher):
        """Consume market data with error handling."""
        consecutive_errors = 0
        max_consecutive = 5

        while self.running:
            try:
                # Use timeout to prevent hanging
                bbo = await asyncio.wait_for(
                    dispatcher.get_market_data(),
                    timeout=30.0
                )

                # Reset error counter on success
                consecutive_errors = 0

                # Process update
                logger.info(
                    f"{bbo.exchange} {bbo.symbol} | "
                    f"bid={bbo.data.bid} ask={bbo.data.ask}"
                )

                # Check for queue health
                stats = dispatcher.get_stats()
                if stats["queue_full_drops"] > 0:
                    logger.warning(
                        f"Queue drops detected: {stats['queue_full_drops']}"
                    )

            except asyncio.TimeoutError:
                consecutive_errors += 1
                logger.warning(
                    f"Market data timeout ({consecutive_errors}/{max_consecutive})"
                )

                if consecutive_errors >= max_consecutive:
                    logger.error("Too many consecutive timeouts")
                    self.running = False
                    break

            except Exception as exc:
                consecutive_errors += 1
                logger.error(f"Consumer error: {exc}")

                if consecutive_errors >= max_consecutive:
                    logger.error("Too many consecutive errors")
                    self.running = False
                    break

                await asyncio.sleep(1.0)

    async def shutdown(self, ws, ws_task, consumer_task):
        """Graceful shutdown."""
        logger.info("Shutting down gracefully...")

        # Stop WebSocket
        try:
            await asyncio.wait_for(ws.stop(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("WebSocket stop timeout")

        # Cancel tasks
        ws_task.cancel()
        consumer_task.cancel()

        # Wait for cancellation
        try:
            await asyncio.gather(ws_task, consumer_task, return_exceptions=True)
        except Exception as exc:
            logger.error(f"Shutdown error: {exc}")

        logger.info("Shutdown complete")


async def main():
    """Run robust monitoring with error handling."""
    # Create dispatcher with smaller queue to test overflow handling
    dispatcher = create_dispatcher(
        lighter_market_mapping={0: "ETH/USDC"}
    )

    # Create monitor
    monitor = RobustMonitor()

    # Create WebSocket
    ws = LighterWS(
        market_index=0,
        on_event=dispatcher.on_raw_event,
        bbo_only=True,
    )

    # Start WebSocket and consumer
    ws_task = asyncio.create_task(monitor.run_websocket(ws))
    consumer_task = asyncio.create_task(monitor.consume_market_data(dispatcher))

    try:
        # Wait for tasks
        await asyncio.gather(ws_task, consumer_task)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await monitor.shutdown(ws, ws_task, consumer_task)


if __name__ == "__main__":
    asyncio.run(main())
