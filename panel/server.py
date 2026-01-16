"""WebSocket server to broadcast real-time data to frontend clients."""
import asyncio
import json
import websockets
from typing import Set
from websockets.server import WebSocketServerProtocol

from .collector import DataCollector
from .config import HOST, PORT


class PanelServer:
    """WebSocket server that broadcasts exchange data to connected clients."""

    def __init__(self):
        self.clients: Set[WebSocketServerProtocol] = set()
        self.collector = DataCollector(on_update_callback=self._on_data_update)

    async def start(self):
        """Start the WebSocket server and data collector."""
        # Start data collector
        await self.collector.start()

        # Start WebSocket server
        async with websockets.serve(self._handle_client, HOST, PORT):
            print(f"[PanelServer] WebSocket server running on ws://{HOST}:{PORT}")
            print(f"[PanelServer] Open http://{HOST}:{PORT}/index.html in your browser")
            await asyncio.Future()  # Run forever

    async def _handle_client(self, websocket: WebSocketServerProtocol):
        """Handle a new WebSocket client connection."""
        self.clients.add(websocket)
        print(f"[PanelServer] Client connected: {websocket.remote_address}")

        try:
            # Send initial state immediately
            await websocket.send(json.dumps(self.collector.get_state()))

            # Keep connection alive and handle messages
            async for message in websocket:
                # Client messages (if any) - currently not used
                pass

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            print(f"[PanelServer] Client disconnected: {websocket.remote_address}")

    async def _on_data_update(self, state: dict):
        """Broadcast updated state to all connected clients."""
        if not self.clients:
            return

        message = json.dumps(state)
        # Broadcast to all clients concurrently
        await asyncio.gather(
            *[self._send_to_client(client, message) for client in self.clients],
            return_exceptions=True
        )

    async def _send_to_client(self, client: WebSocketServerProtocol, message: str):
        """Send message to a single client."""
        try:
            await client.send(message)
        except Exception as e:
            print(f"[PanelServer] Error sending to client: {e}")


async def main():
    """Main entry point."""
    server = PanelServer()
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
