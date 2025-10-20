import pathlib
import shutil
import time
import argparse
import paradoc as pa


def main():
    """Send a Paradoc document to the Reader app."""
    chrome_exe = shutil.which("chrome.exe")
    if chrome_exe is None:
        from plotly.io._kaleido import plotly_get_chrome
        plotly_get_chrome()

    parser = argparse.ArgumentParser(description="Send a Paradoc document to the Reader app.")
    parser.add_argument("--doc", default="doc_lorum", help="Path to Paradoc document dir to send.")
    parser.add_argument(
        "--serve-images", action="store_true", help="Embed images in IndexedDB instead of using HTTP server."
    )
    parser.add_argument(
        "--use-static-html",
        action="store_true",
        help="Extract frontend.zip and open in browser instead of expecting separate Reader app.",
    )
    args = parser.parse_args()
    doc_dir = args.doc
    files_dir = pathlib.Path(__file__).resolve().absolute().parent / ".." / "files"
    doc_names = [d.name for d in files_dir.iterdir()]
    print(doc_names)
    if doc_dir in doc_names:
        od = pa.OneDoc(files_dir / doc_dir)
    else:
        od = pa.OneDoc(doc_dir)

    od.send_to_frontend(embed_images=not args.serve_images, use_static_html=args.use_static_html)

    if args.use_static_html and args.serve_images:
        print("Keep this terminal open to serve assets. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("\nStopping servers.")

    if not args.serve_images:
        print("✓ Sent document to Reader over WebSocket with embedded images.")
        print("✓ Images stored in browser IndexedDB - no HTTP server needed!")
        print("✓ You can close this script now - the document is fully cached in the browser.")
    else:
        print("Sent document to Reader over WebSocket.")
        print("Serving JSON and assets via Paradoc HTTP server at http://localhost:13580/")
        print("Open the Reader app and ensure it connects; press Ctrl+C here to stop.")
        # Keep the process alive so the background HTTP server thread keeps running
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("\nStopping example.")


if __name__ == "__main__":
    main()
