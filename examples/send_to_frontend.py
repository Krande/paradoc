import pathlib
import time
import argparse
import paradoc as pa


def main():
    parser = argparse.ArgumentParser(description="Send a Paradoc document to the Reader app.")
    parser.add_argument("--doc", default="doc_lorum", help="Path to Paradoc document dir to send.")
    args = parser.parse_args()
    doc_dir = args.doc
    files_dir = pathlib.Path(__file__).resolve().absolute().parent / ".." / "files"
    doc_names = [d.name for d in files_dir.iterdir()]
    print(doc_names)
    if doc_dir in doc_names:
        od = pa.OneDoc(files_dir / doc_dir)
    else:
        od = pa.OneDoc(doc_dir)
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