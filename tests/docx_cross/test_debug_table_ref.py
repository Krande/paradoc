"""Debug test to examine table reference structure."""

from pathlib import Path

from docx import Document

from paradoc import OneDoc


def test_debug_table_reference():
    """Debug test to see what pandoc-crossref outputs for table references."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        source_dir = tmp_path / "test_doc"
        main_dir = source_dir / "00-main"
        main_dir.mkdir(parents=True)

        # Create markdown with table reference
        md_content = """# Test Document

This is a reference to [@tbl:test_table] in the text.

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |

Table: Test Table Caption {#tbl:test_table}
"""

        md_file = main_dir / "test.md"
        md_file.write_text(md_content, encoding="utf-8")

        # Compile
        work_dir = tmp_path / "work"
        one = OneDoc(source_dir, work_dir=work_dir)
        one.compile("test_output", auto_open=False, export_format="docx")

        output_file = work_dir / "_dist" / "test_output.docx"
        doc = Document(str(output_file))

        print("\n" + "=" * 80)
        print("DOCUMENT PARAGRAPHS - Looking for table references")
        print("=" * 80)

        for i, para in enumerate(doc.paragraphs):
            if "reference" in para.text.lower() or "table" in para.text.lower():
                print(f"\nParagraph {i}:")
                print(f"  Style: {para.style.name}")
                print(f"  Text: '{para.text}'")

                # Check for hyperlinks
                xml_str = para._element.xml
                if isinstance(xml_str, bytes):
                    xml_str = xml_str.decode("utf-8")

                if "hyperlink" in xml_str.lower():
                    print("  Contains hyperlink")
                if "REF" in xml_str:
                    print("  Contains REF field")


if __name__ == "__main__":
    test_debug_table_reference()
