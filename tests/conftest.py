"""Ensure local package imports work without installation."""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class MockWebsocket:
    """Mock WebSocket for testing.

    Simulates an async WebSocket connection with send, recv, and close.
    Shared across all integration tests via conftest.
    """

    def __init__(self):
        self.sent_messages = []
        self.closed = False

    async def send(self, message):
        self.sent_messages.append(message)

    async def close(self):
        self.closed = True

    async def recv(self):
        """Mock recv - returns empty string after a short delay."""
        await asyncio.sleep(0.1)
        return ""


@pytest.fixture
def mock_websocket():
    """Pytest fixture that returns a MockWebsocket instance."""
    return MockWebsocket()
