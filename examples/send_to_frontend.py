import time
import paradoc as pa


def main():
    od = pa.OneDoc("../files/doc1")
    ok = od.send_to_frontend()
    print("Sent document to Reader over WebSocket.")
    print("Serving JSON and assets via Paradoc HTTP server at http://localhost:13580/")
    print("Open the Reader app and ensure it connects; press Ctrl+C here to stop.")
    # Keep the process alive so the background HTTP server thread keeps running
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nStopping example.")


if __name__ == '__main__':
    main()