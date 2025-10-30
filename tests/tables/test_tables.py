import pandas as pd
from docx import Document

from paradoc import OneDoc
from paradoc.common import TableFormat


def test_table(files_dir, tmp_path):
    """Test that tables added via add_table() are properly exported to DOCX."""
    report_dir = files_dir / "doc_table"
    one = OneDoc(report_dir, work_dir=tmp_path / "doc_table")
    df = pd.DataFrame([(0, 0), (1, 2)], columns=["a", "b"])

    one.add_table("my_table", df, "A basic table")
    one.add_table("my_table_2", df, "A slightly smaller table", TableFormat(font_size=8))
    one.add_table("my_table_3", df, "No Space 1")
    one.add_table("my_table_4", df, "No Space 2")
    one.add_table("my_table_5", df, "No Space 3")

    one.compile("TableDoc", export_format="docx", auto_open=False)

    # Verify the DOCX was created
    output_file = tmp_path / "doc_table" / "_dist" / "TableDoc.docx"
    assert output_file.exists(), f"Output DOCX file should exist at {output_file}"

    # Load and verify the document
    doc = Document(str(output_file))

    # Count tables in the document
    # Note: my_table and my_table_3 are referenced in the markdown
    # my_table_2, my_table_4, my_table_5 are defined but not used in the markdown
    tables = doc.tables
    assert len(tables) >= 2, f"Expected at least 2 tables in document, found {len(tables)}"

    # Verify table captions exist
    caption_texts = []
    for para in doc.paragraphs:
        if para.style.name == "Table Caption":
            caption_texts.append(para.text)

    assert len(caption_texts) >= 2, f"Expected at least 2 table captions, found {len(caption_texts)}"
    assert any("A basic table" in text for text in caption_texts), "Should find 'A basic table' caption"
    assert any("No Space 1" in text for text in caption_texts), "Should find 'No Space 1' caption"

    # Verify table content - check that tables have correct structure
    for table in tables[:2]:  # Check first 2 tables
        assert len(table.rows) >= 2, f"Table should have at least 2 rows (header + data)"
        assert len(table.columns) == 2, f"Table should have 2 columns (a, b)"

        # Verify headers
        header_cells = table.rows[0].cells
        assert "a" in header_cells[0].text, "First column header should be 'a'"
        assert "b" in header_cells[1].text, "Second column header should be 'b'"

        # Verify data integrity - first cell should contain actual data, not table name
        # This verifies the bookmark-based identification is working
        first_data_cell = table.rows[1].cells[0].text.strip()
        assert first_data_cell == "0", f"First data cell should be '0', not table name. Got: '{first_data_cell}'"


def test_regular_table(files_dir, tmp_path):
    """Test that markdown tables are properly formatted and exported to DOCX."""
    report_dir = files_dir / "doc_regular_table"
    one = OneDoc(report_dir, work_dir=tmp_path / "doc_regular_table")

    one.compile("TableDoc", export_format="docx", auto_open=False)

    # Verify the DOCX was created
    output_file = tmp_path / "doc_regular_table" / "_dist" / "TableDoc.docx"
    assert output_file.exists(), f"Output DOCX file should exist at {output_file}"

    # Load and verify the document
    doc = Document(str(output_file))

    # Count tables - should have exactly 1 table from the markdown
    tables = doc.tables
    assert len(tables) == 1, f"Expected exactly 1 table in document, found {len(tables)}"

    table = tables[0]

    # Verify table structure
    assert len(table.rows) == 5, f"Table should have 5 rows (1 header + 4 data), found {len(table.rows)}"
    assert len(table.columns) == 4, f"Table should have 4 columns, found {len(table.columns)}"

    # Verify headers
    header_cells = table.rows[0].cells
    expected_headers = ["", "cat A [unit]", "cat 2 [unitB]", "num ex [-]"]
    for i, expected in enumerate(expected_headers):
        actual = header_cells[i].text.strip()
        assert expected in actual, f"Column {i} header should contain '{expected}', got '{actual}'"

    # Verify first row of data
    row1_cells = table.rows[1].cells
    assert "example1" in row1_cells[0].text, "First data row should contain 'example1'"
    assert "4000" in row1_cells[1].text, "First data row cat A should be 4000"
    assert "1.13" in row1_cells[2].text, "First data row cat 2 should be 1.13"
    assert "6" in row1_cells[3].text, "First data row num ex should be 6"

    # Verify caption exists and is properly formatted
    caption_found = False
    for para in doc.paragraphs:
        if para.style.name == "Table Caption" and "A basic table" in para.text:
            caption_found = True
            # Verify caption has numbering (e.g., "Table 1-1:")
            assert "Table" in para.text, "Caption should start with 'Table'"
            # The caption should have a number pattern like "1-1" or just "1"
            import re
            has_number = re.search(r"Table\s+[\d\-]+", para.text)
            assert has_number, f"Caption should have table number, got: '{para.text}'"
            break

    assert caption_found, "Should find 'A basic table' caption with proper formatting"

    # Verify the table reference/bookmark exists in the caption
    # The caption paragraph should have a bookmark for cross-referencing
    for para in doc.paragraphs:
        if para.style.name == "Table Caption":
            # Check for bookmark in the XML
            xml_str = para._element.xml
            if isinstance(xml_str, bytes):
                xml_str = xml_str.decode("utf-8")

            # Should have a bookmark (created by pandoc-crossref and our system)
            has_bookmark = "bookmarkStart" in xml_str or "w:bookmarkStart" in xml_str
            assert has_bookmark, "Table caption should have bookmark for cross-referencing"
            break
