#!/usr/bin/env python
"""Quick test script to verify panel components work."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_panel():
    """Test panel components."""
    print("Testing panel components...\n")

    # Test 1: Import all modules
    print("✓ Test 1: Importing modules...")
    try:
        from panel.config import HOST, PORT, ASTER_API_KEY, BACKPACK_API_KEY
        from panel.collector import DataCollector
        from panel.server import PanelServer
        from api import get_client
        from api.ws import get_user_ws_client
        print(f"  ✅ All imports successful")
        print(f"  ✅ Server config: {HOST}:{PORT}")
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Check API credentials
    print("\n✓ Test 2: Checking API credentials...")
    if not ASTER_API_KEY or not BACKPACK_API_KEY:
        print(f"  ❌ Missing API credentials in .env file")
        return False
    print(f"  ✅ Aster API Key: {ASTER_API_KEY[:8]}...")
    print(f"  ✅ Backpack API Key: {BACKPACK_API_KEY[:8]}...")

    # Test 3: Initialize REST clients
    print("\n✓ Test 3: Initializing REST clients...")
    try:
        from panel.config import ASTER_SECRET, BACKPACK_SECRET
        aster_client = get_client("aster", {"apiKey": ASTER_API_KEY, "secret": ASTER_SECRET})
        backpack_client = get_client("backpack", {"apiKey": BACKPACK_API_KEY, "secret": BACKPACK_SECRET})
        print(f"  ✅ Aster client initialized: {type(aster_client).__name__}")
        print(f"  ✅ Backpack client initialized: {type(backpack_client).__name__}")
    except Exception as e:
        print(f"  ❌ Client initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 4: Check static files
    print("\n✓ Test 4: Checking static files...")
    static_dir = Path(__file__).parent / 'static'
    index_html = static_dir / 'index.html'
    if not index_html.exists():
        print(f"  ❌ index.html not found at {index_html}")
        return False
    print(f"  ✅ index.html found ({index_html.stat().st_size} bytes)")

    # Test 5: Test server initialization (without starting)
    print("\n✓ Test 5: Testing server initialization...")
    try:
        server = PanelServer()
        print(f"  ✅ Server initialized")
        print(f"  ✅ Routes configured: {len(server.app.router.routes())} routes")
    except Exception as e:
        print(f"  ❌ Server initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "="*50)
    print("✅ ALL TESTS PASSED!")
    print("="*50)
    print("\nTo start the panel, run:")
    print("  python -m panel")
    print("\nThen open in browser:")
    print(f"  http://{HOST}:{PORT}/")
    print("\n")

    return True

if __name__ == "__main__":
    result = asyncio.run(test_panel())
    sys.exit(0 if result else 1)
