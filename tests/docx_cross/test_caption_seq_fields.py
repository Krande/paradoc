"""Test to verify that rebuild_caption creates proper SEQ fields."""

import base64
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from paradoc import OneDoc
from paradoc.io.word.com_api import is_word_com_available


@pytest.mark.skipif(not is_word_com_available(), reason="COM automation only if Word COM is available")
def test_caption_seq_fields_are_created(tmp_path):
    """Verify that SEQ fields are actually created in captions."""

    source_dir = tmp_path / "test_doc"
    main_dir = source_dir / "00-main"
    main_dir.mkdir(parents=True)

    # Create test image
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )

    images_dir = main_dir / "images"
    images_dir.mkdir(parents=True)

    for i in range(2):
        img_path = images_dir / f"fig{i + 1}.png"
        img_path.write_bytes(png_data)

    # Simple markdown with 2 figures
    md_content = """# Section 1

First section with a figure.

![First figure](images/fig1.png){#fig:first}

# Section 2

Second section with another figure.

![Second figure](images/fig2.png){#fig:second}
"""

    md_file = main_dir / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    # Compile the document
    work_dir = tmp_path / "work"
    one = OneDoc(source_dir, work_dir=work_dir)
    one.compile("test_seq", auto_open=False, export_format="docx", update_docx_with_com=False)

    output_file = work_dir / "_dist" / "test_seq.docx"
    assert output_file.exists(), "Output file should be created"

    # Extract and analyze XML
    xml_dir = tmp_path / "xml_extract"
    extract_docx_xml(output_file, xml_dir)

    doc_xml = xml_dir / "word" / "document.xml"
    tree = ET.parse(doc_xml)
    root = tree.getroot()

    nsmap = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    }

    # Find all SEQ fields
    seq_fields = []
    paragraphs = root.findall(".//w:p", nsmap)

    print("\n" + "=" * 80)
    print("ANALYZING CAPTION PARAGRAPHS")
    print("=" * 80)

    for para_idx, para in enumerate(paragraphs):
        para_text = "".join([t.text for t in para.findall(".//w:t", nsmap) if t.text])

        # Check if this is a caption paragraph
        if "Figure" in para_text or "figure" in para_text.lower():
            print(f"\nParagraph {para_idx}: {para_text[:80]}")

            # Look for field characters in this paragraph
            runs = para.findall(".//w:r", nsmap)

            has_fields = False
            field_instr = ""

            for run in runs:
                fld_char = run.find(".//w:fldChar", nsmap)
                if fld_char is not None:
                    has_fields = True
                    fld_type = fld_char.get("{%s}fldCharType" % nsmap["w"])
                    print(f"  Found fldChar: {fld_type}")

                instr_text = run.find(".//w:instrText", nsmap)
                if instr_text is not None and instr_text.text:
                    field_instr += instr_text.text
                    print(f"  Field instruction: {instr_text.text}")

                    if " SEQ " in instr_text.text:
                        seq_fields.append({"para_idx": para_idx, "instr": instr_text.text.strip()})

            if not has_fields:
                print("  ⚠ NO FIELD CODES FOUND - Caption is static text!")
                # Print the raw XML for this paragraph
                print(f"  Raw XML preview: {ET.tostring(para, encoding='unicode')[:200]}...")

    print("\n" + "=" * 80)
    print("SEQ FIELD SUMMARY")
    print("=" * 80)
    print(f"Total SEQ fields found: {len(seq_fields)}")

    for sf in seq_fields:
        print(f"  • Para {sf['para_idx']}: {sf['instr']}")

    # ASSERTION: We should have at least 2 SEQ fields (one per figure)
    assert len(seq_fields) >= 2, (
        f"Expected at least 2 SEQ fields (one per figure), but found {len(seq_fields)}. "
        "This indicates that rebuild_caption is not creating proper SEQ fields."
    )

    print("\n✓ TEST PASSED - SEQ fields are being created correctly")


def extract_docx_xml(docx_path: Path, output_dir: Path):
    """Extract XML files from .docx file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(docx_path, "r") as zip_ref:
        zip_ref.extractall(output_dir)
