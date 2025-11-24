"""
Enhanced test script to demonstrate frontend connection tracking with multiple frontends.
This script shows how to query the number of connected frontends and their IDs.
"""

from paradoc.frontend.ws_server import (
    ensure_ws_server,
    has_active_frontends,
    get_connected_frontends,
    ping_ws_server,
)
import time


def main():
    print("=== Enhanced Paradoc Frontend Tracking Demo ===\n")

    # 1. Start the WebSocket server
    print("1. Starting WebSocket server...")
    server_started = ensure_ws_server(host="localhost", port=13579)
    if server_started:
        print("   ✓ Server is running at ws://localhost:13579")
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

    # 3. Monitor for connected frontends
    print("\n3. Monitoring for frontend connections...")
    print("   (Open a Paradoc Reader frontend to see it appear in the list)")
    print("   (You can open multiple browser tabs to test multiple frontends)")
    print("   (Press Ctrl+C to stop monitoring)\n")

    last_count = -1
    try:
        while True:
            frontend_ids = get_connected_frontends(host="localhost", port=13579)
            current_count = len(frontend_ids)

            # Only print if the count changed
            if current_count != last_count:
                print(f"\n[{time.strftime('%H:%M:%S')}] Connected Frontends: {current_count}")
                if current_count > 0:
                    for i, fid in enumerate(frontend_ids, 1):
                        print(f"   {i}. {fid}")
                else:
                    print("   (No frontends connected)")

                last_count = current_count

            time.sleep(2)  # Check every 2 seconds

    except KeyboardInterrupt:
        print("\n\n✓ Monitoring stopped by user")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
