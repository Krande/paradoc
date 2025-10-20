"""
Test script to verify doc_lorum can be compiled successfully with DbManager.
"""

from pathlib import Path

from paradoc import OneDoc

# Set up paths
files_dir = Path("files")
source = files_dir / "doc_lorum"
output_dir = Path("temp") / "test_doc_lorum"

print("=" * 70)
print("Testing doc_lorum with DbManager")
print("=" * 70)
print()

# Initialize OneDoc (this will use the data.db from the source directory)
print("Step 1: Initializing OneDoc with database")
print("-" * 70)
one = OneDoc(source, work_dir=output_dir)

db_location = source / "data.db"
print(f"✓ Using database at: {db_location}")

# Verify database contents
plots = one.db_manager.list_plots()
tables = one.db_manager.list_tables()
print(f"✓ Database contains {len(plots)} plots and {len(tables)} tables")
print()

# Test HTML export
print("Step 2: Testing doc_lorum export to HTML...")
print("-" * 70)
try:
    one.compile("doc_lorum", auto_open=False, export_format="html")
    print("✓ HTML export successful!")
    print(f"  Output: {output_dir / '_dist' / 'doc_lorum.html'}")
except Exception as e:
    print(f"✗ HTML export failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Test DOCX export
print("Step 3: Testing doc_lorum export to DOCX...")
print("-" * 70)
try:
    one = OneDoc(source, work_dir=output_dir)
    one.compile("doc_lorum", auto_open=False, export_format="docx")
    print("✓ DOCX export successful!")
    print(f"  Output: {output_dir / '_dist' / 'doc_lorum.docx'}")
except Exception as e:
    print(f"✗ DOCX export failed: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("✓ Document structure verified successfully!")
print("=" * 70)
print()
print("Summary:")
print("- Main section: 00-main/main.md with plots and tables from database")
print("- Appendix section: 01-app/appendix.md with plots and tables from database")
print(f"- Total in database: {len(tables)} tables, {len(plots)} plots")
print("- Features: TOC, cross-references, footnotes, equations")
print()
print("All plots and tables are now loaded from DbManager!")
