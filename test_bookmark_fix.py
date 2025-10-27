"""Quick test to verify bookmark wrapping behavior."""

from docx import Document
from paradoc.io.word.captions import rebuild_caption
from paradoc.io.word.bookmarks import add_bookmark_around_seq_field

# Create a new document
doc = Document()

# Add a paragraph and format it as a caption
caption_para = doc.add_paragraph()
caption_para.style = "Caption"

# Rebuild the caption with proper SEQ fields
rebuild_caption(caption_para, "Figure", "Test caption text here", is_appendix=False, should_restart=True)

# Print paragraph structure before bookmark
print("\n=== BEFORE BOOKMARK ===")
print(f"Paragraph text: {caption_para.text}")
print(f"Number of runs: {len(list(caption_para._p))}")
for i, run in enumerate(caption_para._p):
    if hasattr(run, 'text'):
        print(f"  Run {i}: {run.text[:50] if len(run.text) > 50 else run.text}")

# Add bookmark
bookmark_name = add_bookmark_around_seq_field(caption_para, "fig:test")

print(f"\n=== AFTER BOOKMARK ===")
print(f"Bookmark name: {bookmark_name}")

# Save to temp file
output_path = "temp/test_bookmark.docx"
doc.save(output_path)
print(f"\nSaved to: {output_path}")

# Inspect the bookmark
from paradoc.io.word.inspect import DocxInspector
inspector = DocxInspector(output_path)
bookmarks = inspector.bookmarks()
print(f"\n=== BOOKMARKS ===")
for bm in bookmarks:
    print(f"  {bm.name}: {bm.context}")

