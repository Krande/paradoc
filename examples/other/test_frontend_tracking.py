"""
Test script to demonstrate frontend connection tracking and frontend_id support.
"""
from paradoc.frontend.ws_server import (
    ensure_ws_server,
    has_active_frontends,
    get_connected_frontends,
    ping_ws_server,
)

def main():
    print("=== Paradoc Frontend Connection Tracking Demo ===\n")
    
    # 1. Start the WebSocket server
    print("1. Starting WebSocket server...")
    server_started = ensure_ws_server(host="localhost", port=13579)
    if server_started:
        print("   ✓ Server is running")
    else:
        print("   ✗ Failed to start server")
        return
    
    # 2. Check if server is responsive
    print("\n2. Pinging WebSocket server...")
    if ping_ws_server(host="localhost", port=13579):
        print("   ✓ Server is responsive")
    else:
        print("   ✗ Server not responding")
        return
    
    # 3. Check for active frontends
    print("\n3. Checking for active frontends...")
    if has_active_frontends(host="localhost", port=13579):
        print("   ✓ Frontends are connected")
        
        # 4. Get list of connected frontend IDs
        frontend_ids = get_connected_frontends(host="localhost", port=13579)
        print(f"\n4. Connected frontends ({len(frontend_ids)}):")
        for frontend_id in frontend_ids:
            print(f"   - {frontend_id}")
    else:
        print("   ℹ No frontends currently connected")
        print("   → Please open a Paradoc Reader frontend first")
        print("   → You can open it by running: pixi run -e frontend wdev")
        print("   → Or by opening the standalone HTML file")
    
    print("\n=== Demo Complete ===")

if __name__ == "__main__":
    main()

