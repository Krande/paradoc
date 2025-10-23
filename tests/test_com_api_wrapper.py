"""Test the Word COM API wrapper."""

import os
import platform
import tempfile
from pathlib import Path

import pytest

from paradoc import MY_DOCX_TMPL


@pytest.mark.skipif(platform.system() != "Windows", reason="COM automation only available on Windows")
def test_word_com_api_wrapper(tmp_path):
    """Test the simplified Word COM API wrapper."""
    from paradoc.io.word.com_api import WordApplication
    
    output_file = Path(tmp_path) / "test_wrapper.docx"

    # Create a document using the wrapper
    with WordApplication(visible=False) as word_app:
        doc = word_app.create_document()

        # Add heading
        doc.add_heading("Test Document with COM API Wrapper", level=1)

        # Add some content
        doc.add_paragraph("This document was created using the simplified COM API wrapper.")
        doc.add_paragraph()

        # Add a figure with caption
        fig_bookmark = doc.add_figure_with_caption(
            caption_text="Example Figure",
            create_bookmark=True
        )

        doc.add_paragraph()

        # Add a table with caption
        table_bookmark = doc.add_table_with_caption(
            caption_text="Example Table",
            rows=3,
            cols=3,
            create_bookmark=True
        )

        doc.add_paragraph()

        # Add cross-references
        doc.add_cross_reference(
            bookmark_name="figure_0",
            reference_type="figure",
            prefix_text="See "
        )
        doc.add_paragraph(" for the figure.")

        doc.add_paragraph()
        doc.add_cross_reference(
            bookmark_name="table_0",
            reference_type="table",
            prefix_text="Refer to "
        )
        doc.add_paragraph(" for the table data.")

        # Update all fields
        doc.update_fields()

        # Save the document
        doc.save(output_file)

    # Verify the file was created
    assert output_file.exists(), "Document should be created"
    assert output_file.stat().st_size > 0, "Document should not be empty"

    print(f"\nTest document created successfully: {output_file}")

    # Optionally open the file for manual inspection
    if os.getenv("AUTO_OPEN"):
        os.startfile(output_file)


@pytest.mark.skipif(platform.system() != "Windows", reason="COM automation only available on Windows")
def test_word_sections_and_breaks():
    """Test section breaks and page breaks."""
    from paradoc.io.word.com_api import WordApplication
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_file = Path(tmp_dir) / "test_sections.docx"
        
        with WordApplication(visible=False) as word_app:
            doc = word_app.create_document()
            
            doc.add_heading("Section 1", level=1)
            doc.add_paragraph("Content in section 1.")
            
            doc.add_section_break("next_page")
            
            doc.add_heading("Section 2", level=1)
            doc.add_paragraph("Content in section 2.")
            
            doc.add_page_break()
            
            doc.add_heading("Same Section, New Page", level=2)
            doc.add_paragraph("Still in section 2 but on a new page.")
            
            doc.save(output_file)
            
        assert output_file.exists()
        print(f"\nSections test document created: {output_file}")


@pytest.mark.skipif(platform.system() != "Windows", reason="COM automation only available on Windows")
def test_word_heading_levels():
    """Test different heading levels."""
    from paradoc.io.word.com_api import WordApplication
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_file = Path(tmp_dir) / "test_headings.docx"
        
        with WordApplication(visible=False) as word_app:
            doc = word_app.create_document()
            
            for level in range(1, 4):
                doc.add_heading(f"Heading Level {level}", level=level)
                doc.add_paragraph(f"Content under heading level {level}.")
                doc.add_paragraph()
            
            doc.save(output_file)
            
        assert output_file.exists()
        print(f"\nHeadings test document created: {output_file}")


@pytest.mark.skipif(platform.system() != "Windows", reason="COM automation only available on Windows")
def test_word_with_template(tmp_path):
    """Test creating a document from a template."""
    from paradoc.io.word.com_api import WordApplication
    
    # First, create a simple template
    template_file = MY_DOCX_TMPL

    # Now create a new document based on the template
    output_file = Path(tmp_path) / "from_template.docx"
    
    with WordApplication(visible=False) as word_app:
        doc = word_app.create_document(template=template_file)

        doc.add_page_break()
        # Add content to the template-based document
        doc.add_heading("New Document", level=1)

        doc.add_paragraph("This document uses styles from the template.")
        
        doc.add_figure_with_caption("Figure in templated doc")
        doc.add_table_with_caption("Table in templated doc", rows=2, cols=2)
        
        doc.update_fields()
        doc.save(output_file)
    
    # Verify both files were created
    assert template_file.exists(), "Template should be created"
    assert output_file.exists(), "Document from template should be created"
    assert output_file.stat().st_size > 0, "Template-based document should not be empty"
    
    print(f"\nTemplate: {template_file}")
    print(f"Document from template: {output_file}")
    
    if os.getenv("AUTO_OPEN"):
        os.startfile(output_file)


if __name__ == "__main__":
    # Run tests directly
    test_word_com_api_wrapper()
    test_word_sections_and_breaks()
    test_word_heading_levels()
    test_word_with_template()
    print("\nAll tests passed!")
