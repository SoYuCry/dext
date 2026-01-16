"""Entry point for the panel server.

Run with: python -m panel
"""
import asyncio
from .server import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Panel] Server stopped by user")
