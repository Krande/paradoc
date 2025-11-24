"""Diagnose bookmark structure in Paradoc-generated documents."""

import base64
import re
import zipfile
from pathlib import Path

import pytest

from paradoc import OneDoc
from paradoc.io.word.com_api.com_utils import docx_update, is_word_com_available


@pytest.mark.skipif(not is_word_com_available(), reason="COM automation only if Word COM is available")
def test_diagnose_paradoc_bookmarks(tmp_path):
    """Create a simple Paradoc document and analyze bookmark structure."""
    print("\n" + "=" * 80)
    print("DIAGNOSE PARADOC BOOKMARKS")
    print("=" * 80)

    # Create source directory
    source_dir = tmp_path / "source"
    main_dir = source_dir / "00-main"
    main_dir.mkdir(parents=True)

    # Create test image
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    images_dir = main_dir / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "fig1.png").write_bytes(png_data)
    (images_dir / "fig2.png").write_bytes(png_data)

    # Create simple markdown with 2 sections and 2 figures
    md_content = """# Section 1

![Figure in section 1](images/fig1.png){#fig:fig1}

Reference to [@fig:fig1].

# Section 2

![Figure in section 2](images/fig2.png){#fig:fig2}

Reference to [@fig:fig2] and [@fig:fig1].
"""

    md_file = main_dir / "document.md"
    md_file.write_text(md_content, encoding="utf-8")

    # Compile document
    work_dir = tmp_path / "work"
    one = OneDoc(source_dir, work_dir=work_dir)
    one.compile("output", auto_open=False, export_format="docx", update_docx_with_com=False)

    output_file = work_dir / "_dist" / "output.docx"

    # Analyze BEFORE field update
    print("\n[BEFORE FIELD UPDATE]")
    analyze_bookmarks_and_refs(output_file)

    # Update fields
    print("\n[Updating fields...]")
    docx_update(str(output_file))

    # Analyze AFTER field update
    print("\n[AFTER FIELD UPDATE]")
    analyze_bookmarks_and_refs(output_file)


def analyze_bookmarks_and_refs(docx_path: Path):
    """Analyze bookmark structure and cross-references."""
    # Extract XML
    with zipfile.ZipFile(docx_path, "r") as zip_ref:
        xml_content = zip_ref.read("word/document.xml").decode("utf-8")

    # Find all bookmarks
    print("\n  === BOOKMARKS ===")
    bookmark_pattern = r'<w:bookmarkStart[^>]*w:name="([^"]*)"[^>]*w:id="(\d+)"[^>]*/>'
    bookmarks = re.findall(bookmark_pattern, xml_content)

    for name, bm_id in bookmarks:
        if name.startswith("_Ref") or "fig" in name.lower():
            # Find bookmark content
            start_pattern = f'<w:bookmarkStart[^>]*w:id="{bm_id}"[^>]*/>'
            end_pattern = f'<w:bookmarkEnd[^>]*w:id="{bm_id}"[^>]*/>'

            start_match = re.search(start_pattern, xml_content)
            end_match = re.search(end_pattern, xml_content)

            if start_match and end_match:
                content = xml_content[start_match.end() : end_match.start()]
                # Extract text
                text_parts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", content)
                text = "".join(text_parts)

                # Extract field instructions
                field_parts = re.findall(r"<w:instrText[^>]*>(.*?)</w:instrText>", content)

                print(f"\n  Bookmark: {name} (ID: {bm_id})")
                print(f"    Text: {text[:100]}")
                if field_parts:
                    print(f"    Fields: {field_parts}")

    # Find all REF fields
    print("\n  === REF FIELDS ===")
    ref_pattern = r"<w:instrText[^>]*>(.*?REF[^<]*)</w:instrText>"
    refs = re.findall(ref_pattern, xml_content)

    for i, ref in enumerate(refs, 1):
        # Find the field result (text after separate, before end)
        # This is complex, so let's find the context
        ref_pos = xml_content.find(f">{ref}<")
        if ref_pos > 0:
            # Find next separate and end
            after_ref = xml_content[ref_pos + len(ref) + 2 :]
            sep_match = re.search(r'<w:fldChar[^>]*w:fldCharType="separate"[^>]*/>', after_ref)
            if sep_match:
                after_sep = after_ref[sep_match.end() :]
                end_match = re.search(r'<w:fldChar[^>]*w:fldCharType="end"[^>]*/>', after_sep)
                if end_match:
                    result_content = after_sep[: end_match.start()]
                    result_text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", result_content))
                    print(f"\n  REF {i}: {ref}")
                    print(f"    Result: '{result_text}'")


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        test_diagnose_paradoc_bookmarks(Path(tmp))
