"""Test to see what pandoc-crossref generates directly."""

import os

import pypandoc


def test_pandoc_crossref_direct_output(tmp_path):
    """See what pandoc-crossref generates for figure references."""
    from docx import Document

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

    # Run pandoc directly
    output_file = tmp_path / "pandoc_direct.docx"

    pypandoc.convert_file(
        str(md_file),
        "docx",
        outputfile=str(output_file),
        format="markdown",
        extra_args=[f"--resource-path={main_dir.absolute()}"],
        filters=["pandoc-crossref"],
        encoding="utf8",
        sandbox=False,
    )

    # Inspect the output
    doc = Document(str(output_file))

    print("\n" + "=" * 80)
    print("PANDOC-CROSSREF DIRECT OUTPUT")
    print("=" * 80)

    import re

    for i, para in enumerate(doc.paragraphs):
        if not para.text.strip():
            continue

        print(f"\nParagraph {i}: Style='{para.style.name}'")
        print(f"  Text: {para.text[:100]}")

        xml_str = para._element.xml.decode("utf-8") if isinstance(para._element.xml, bytes) else para._element.xml

        if "bookmarkStart" in xml_str:
            print("  ✓ Contains bookmarkStart")
            bookmark_matches = re.findall(r'w:name="([^"]+)"', xml_str)
            if bookmark_matches:
                print(f"    Bookmark names: {bookmark_matches}")

        if "SEQ" in xml_str:
            print("  ✓ Contains SEQ field")
            seq_matches = re.findall(r"<w:instrText[^>]*>([^<]*SEQ[^<]*)</w:instrText>", xml_str)
            if seq_matches:
                print(f"    SEQ instruction: {seq_matches}")

        if "REF" in xml_str and "STYLEREF" not in xml_str:
            print("  ✓ Contains REF field")
            ref_matches = re.findall(r"<w:instrText[^>]*>([^<]*REF[^<]*)</w:instrText>", xml_str)
            if ref_matches:
                print(f"    REF instruction: {ref_matches}")

        if "Figure" in para.text or "Reference" in para.text:
            # Show more detailed XML for figure-related paragraphs
            print("\n  Detailed XML excerpt:")
            # Extract just the key parts
            if "fldChar" in xml_str:
                print("    Contains field codes")
            if "instrText" in xml_str:
                instr_matches = re.findall(r"<w:instrText[^>]*>([^<]+)</w:instrText>", xml_str)
                for instr in instr_matches:
                    print(f"    Field instruction: {instr}")

    print("\n" + "=" * 80)

    if os.getenv("AUTO_OPEN", False):
        os.startfile(output_file)
