"""Debug test to check if REF fields are being created."""

import re

import pytest
from docx import Document

from paradoc import OneDoc
from paradoc.io.word.com_api import is_word_com_available


@pytest.mark.skipif(not is_word_com_available(), reason="COM automation only if Word COM is available")
def test_debug_ref_conversion(tmp_path, capsys):
    """Debug test with explicit output."""
    # Create test document
    source_dir = tmp_path / "test_doc"
    main_dir = source_dir / "00-main"
    main_dir.mkdir(parents=True)

    # Create test image
    import base64

    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )

    images_dir = main_dir / "images"
    images_dir.mkdir(parents=True)
    img_path = images_dir / "test.png"
    img_path.write_bytes(png_data)

    # Create markdown
    md_content = """# Test Document

![Test Figure Caption](images/test.png){#fig:test_figure}

Reference to figure: [@fig:test_figure]
"""

    md_file = main_dir / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    # Compile
    work_dir = tmp_path / "work"
    one = OneDoc(source_dir, work_dir=work_dir)
    one.compile("test_output", auto_open=False, export_format="docx")

    output_file = work_dir / "_dist" / "test_output.docx"

    doc = Document(str(output_file))

    # Check results
    has_bookmark = False
    has_ref_field = False
    correct_order = False
    bookmark_id = None

    for para in doc.paragraphs:
        xml_str = para._element.xml.decode("utf-8") if isinstance(para._element.xml, bytes) else para._element.xml

        if "Test Figure Caption" in para.text:
            # Check for Word's native _Ref bookmark (e.g., _Ref695480937)
            has_bookmark = "bookmarkStart" in xml_str and "_Ref" in xml_str
            # Extract the bookmark ID for verification
            bookmark_match = re.search(r'w:name="(_Ref\d+)"', xml_str)
            if bookmark_match:
                bookmark_id = bookmark_match.group(1)
            print(f"Caption bookmark: {has_bookmark}, ID: {bookmark_id}")

        if "Reference to figure" in para.text or "Figure 1" in para.text:
            # Check for REF field with Word's native _Ref bookmark
            has_ref_field = "REF" in xml_str and "_Ref" in xml_str
            print(f"Reference has REF field: {has_ref_field}")
            print(f"Reference text: '{para.text}'")

            # Check if the text order is correct
            # Should be "Reference to figure: Figure 1" not "Figure 1Reference to figure:"
            if "Reference to figure:" in para.text:
                figure_pos = para.text.find("Figure 1")
                reference_pos = para.text.find("Reference to figure:")
                if figure_pos > reference_pos:
                    correct_order = True
                    print(f"Text order: CORRECT (reference at {reference_pos}, figure at {figure_pos})")
                else:
                    print(f"Text order: WRONG (reference at {reference_pos}, figure at {figure_pos})")

            if not has_ref_field and "REF" in xml_str:
                # Extract REF instructions
                ref_matches = re.findall(r"<w:instrText[^>]*>([^<]*)</w:instrText>", xml_str)
                print(f"REF instructions found: {ref_matches}")

    assert has_bookmark, "Caption should have Word's native _Ref bookmark"
    assert has_ref_field, "Reference should have REF field pointing to _Ref bookmark"
    assert correct_order, "Figure reference should appear AFTER 'Reference to figure:', not before"
