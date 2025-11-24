"""
Package the frontend build into frontend.zip for the backend to serve.
Run this after building the frontend with `npm run build`.
"""

import hashlib
import pathlib
import zipfile

# Paths
project_root = pathlib.Path(__file__).parent.parent
frontend_dist = project_root / "frontend" / "dist"
resources_dir = project_root / "src" / "paradoc" / "frontend" / "resources"
zip_path = resources_dir / "frontend.zip"
hash_path = resources_dir / "frontend.hash"


def get_md5_hash_for_file(file_path):
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5


def main():
    print(f"Packaging frontend from: {frontend_dist}")
    print(f"Output zip: {zip_path}")

    # Ensure resources directory exists
    resources_dir.mkdir(parents=True, exist_ok=True)

    # Create zip file
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add all files from dist directory
        for file_path in frontend_dist.rglob("*"):
            if file_path.is_file():
                # Calculate relative path from dist
                arcname = file_path.relative_to(frontend_dist)
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")

    # Calculate and save hash
    hash_content = get_md5_hash_for_file(zip_path).hexdigest()
    with open(hash_path, "w") as f:
        f.write(hash_content)

    print("\n✓ Frontend packaged successfully!")
    print(f"  Zip file: {zip_path}")
    print(f"  Hash: {hash_content}")
    print(f"  Size: {zip_path.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
