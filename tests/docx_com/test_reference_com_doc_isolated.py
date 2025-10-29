"""Example of using isolated Word COM execution to suppress C stack errors.

This demonstrates how to wrap COM operations in an isolated process.
"""

import platform
from pathlib import Path

import pytest

from paradoc import MY_DOCX_TMPL
from paradoc.io.word.com_api import run_word_operation_isolated, is_word_com_available


def _create_reference_document_worker(output_file: str, template: str):
    """Worker function that runs in isolated process."""
    from paradoc.io.word.com_api import WordApplication

    print("\n" + "=" * 80)
    print("TEST: COM API REFERENCE DOCUMENT (ISOLATED)")
    print("=" * 80)

    with WordApplication(visible=False) as word_app:
        doc = word_app.create_document(template=template)

        # Create 3 sections, each with 2 subsections
        for section_num in range(1, 4):
            print(f"\n[Section {section_num}]")
            doc.add_heading(f"Section {section_num}", level=1)
            doc.add_paragraph(f"This is section {section_num} introduction.")
            doc.add_paragraph()

            for subsection_num in range(1, 3):
                subsection_label = f"{section_num}.{subsection_num}"
                print(f"  [Subsection {subsection_label}]")

                doc.add_heading(f"Section {subsection_label}", level=2)

                # Add paragraph with cross-reference placeholders
                doc.add_text("This subsection discusses ")
                doc.add_paragraph()

                # Add figure
                fig_ref = doc.add_figure_with_caption(
                    caption_text=f"Caption for figure in section {subsection_label}",
                    width=150,
                    height=100,
                    use_chapter_numbers=True,
                )
                print(f"    Added Figure {section_num}-{subsection_num}")

                # Add table
                table_data = [["Header 1", "Header 2"], [f"Data {subsection_label}.1", f"Data {subsection_label}.2"]]
                tbl_ref = doc.add_table_with_caption(
                    caption_text=f"Caption for table in section {subsection_label}",
                    rows=2,
                    cols=2,
                    data=table_data,
                    use_chapter_numbers=True,
                )
                print(f"    Added Table {section_num}-{subsection_num}")

                # Add cross-references
                doc.add_text("As shown in ")
                doc.add_cross_reference(fig_ref, include_hyperlink=True)
                doc.add_text(" and ")
                doc.add_cross_reference(tbl_ref, include_hyperlink=True)
                doc.add_text(", the data is consistent.")
                doc.add_paragraph()
                doc.add_paragraph()

        # Save and update fields
        doc.save(output_file)
        doc.update_fields()
        doc.save(output_file)

    print(f"\n[SAVED] {output_file}")
    return output_file


@pytest.mark.skipif(not is_word_com_available, reason="COM automation only if Word COM is available")
def test_com_api_reference_document_isolated(tmp_path):
    """Create a reference document using COM API in isolated process.

    This version runs the entire operation in a separate process to suppress
    C stack error logs.
    """
    # Ensure directory exists
    tmp_path.mkdir(parents=True, exist_ok=True)
    output_file = tmp_path / "standard_com_reference_isolated.docx"

    # Run the entire operation in an isolated process
    success, result, message = run_word_operation_isolated(
        _create_reference_document_worker,
        str(output_file),
        str(MY_DOCX_TMPL),
        timeout_s=120.0,
        redirect_stdout=False  # Set to True to suppress all output
    )

    assert success, f"Document creation failed: {message}"
    assert Path(result).exists(), f"Output file not created: {result}"
    print(f"\n✅ Document created successfully: {result}")


if __name__ == "__main__":
    # For manual testing
    tmp = Path(__file__).parent.parent.parent / "temp" / "isolated_test"
    tmp.mkdir(parents=True, exist_ok=True)

    success, result, message = run_word_operation_isolated(
        _create_reference_document_worker,
        str(tmp / "test_isolated.docx"),
        str(MY_DOCX_TMPL),
        timeout_s=120.0,
        redirect_stdout=False
    )

    if success:
        print(f"\n✅ Success: {result}")
    else:
        print(f"\n❌ Failed: {message}")

