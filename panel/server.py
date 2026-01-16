"""WebSocket server with HTTP static file serving."""
import asyncio
import json
from pathlib import Path
from typing import Set

from aiohttp import web, WSMsgType
from aiohttp.web import Request, WebSocketResponse

from .collector import DataCollector
from .config import HOST, PORT


class PanelServer:
    """WebSocket server that broadcasts exchange data to connected clients."""

    def __init__(self):
        self.clients: Set[WebSocketResponse] = set()
        self.collector = DataCollector(on_update_callback=self._on_data_update)
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP and WebSocket routes."""
        self.app.router.add_get('/ws', self._handle_websocket)
        self.app.router.add_get('/', self._handle_index)
        self.app.router.add_get('/index.html', self._handle_index)
        # Serve static files from static/ directory
        static_dir = Path(__file__).parent / 'static'
        self.app.router.add_static('/static/', path=static_dir, name='static')

    async def _handle_index(self, request: Request):
        """Serve the index.html file."""
        static_dir = Path(__file__).parent / 'static'
        index_file = static_dir / 'index.html'

        if not index_file.exists():
            return web.Response(text="index.html not found", status=404)

        return web.FileResponse(index_file)

    async def _handle_websocket(self, request: Request):
        """Handle WebSocket connection."""
        ws = WebSocketResponse()
        await ws.prepare(request)

        self.clients.add(ws)
        print(f"[PanelServer] Client connected: {request.remote}")

        try:
            # Send initial state immediately
            await ws.send_str(json.dumps(self.collector.get_state()))

            # Keep connection alive and handle messages
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Client messages (if any) - currently not used
                    pass
                elif msg.type == WSMsgType.ERROR:
                    print(f'[PanelServer] WebSocket error: {ws.exception()}')

        except Exception as e:
            print(f"[PanelServer] Error: {e}")
        finally:
            self.clients.discard(ws)
            print(f"[PanelServer] Client disconnected: {request.remote}")

        return ws

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

    async def _send_to_client(self, client: WebSocketResponse, message: str):
        """Send message to a single client."""
        try:
            await client.send_str(message)
        except Exception as e:
            print(f"[PanelServer] Error sending to client: {e}")

    async def start(self):
        """Start the HTTP/WebSocket server and data collector."""
        # Start data collector
        await self.collector.start()

        # Start HTTP server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, HOST, PORT)
        await site.start()

        print(f"[PanelServer] Server running on http://{HOST}:{PORT}")
        print(f"[PanelServer] Open http://{HOST}:{PORT}/ in your browser")
        print(f"[PanelServer] WebSocket endpoint: ws://{HOST}:{PORT}/ws")

        # Run forever
        await asyncio.Future()


async def main():
    """Main entry point."""
    server = PanelServer()
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
