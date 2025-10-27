import argparse
import pathlib

import paradoc as pa


def main():
    """Send a Paradoc document to the Reader app."""
    parser = argparse.ArgumentParser(description="Send a Paradoc document to the Reader app.")
    parser.add_argument("--doc", default="doc_lorum", help="Path to Paradoc document dir to send.")
    parser.add_argument("--docx", action="store_true", help="Export to docx format.")
    args = parser.parse_args()
    doc_dir = args.doc
    files_dir = pathlib.Path(__file__).resolve().absolute().parent / ".." / "files"
    doc_names = [d.name for d in files_dir.iterdir()]

    if doc_dir in doc_names:
        od = pa.OneDoc(files_dir / doc_dir)
    else:
        od = pa.OneDoc(doc_dir)

    od.send_to_frontend()

    if args.docx:
        od.compile("Main", export_format="docx")

if __name__ == "__main__":
    main()
