"""Test cross-reference parity between COM API and Paradoc.

This test creates identical documents using both COM API and Paradoc to ensure
that figure and table numbering and cross-references match exactly.
"""

import platform

import pytest

from paradoc import MY_DOCX_TMPL


@pytest.mark.skipif(platform.system() != "Windows", reason="COM automation only available on Windows")
def test_com_api_reference_document_primary(tmp_path):
    """Create a reference document using pure COM API.

    Structure:
    - Section 1
      - Section 1.1 (with Figure 1-1 and Table 1-1)
      - Section 1.2 (with Figure 1-2 and Table 1-2)
    - Section 2
      - Section 2.1 (with Figure 2-1 and Table 2-1)
      - Section 2.2 (with Figure 2-2 and Table 2-2)
    - Section 3
      - Section 3.1 (with Figure 3-1 and Table 3-1)
      - Section 3.2 (with Figure 3-2 and Table 3-2)

    All figures and tables are cross-referenced within their sections.
    """
    print("\n" + "=" * 80)
    print("TEST: COM API REFERENCE DOCUMENT")
    print("=" * 80)

    from paradoc.io.word.com_api import WordApplication

    # Ensure directory exists
    tmp_path.mkdir(parents=True, exist_ok=True)
    output_file = tmp_path / "standard_com_reference.docx"

    with WordApplication(visible=False) as word_app:
        doc = word_app.create_document(template=MY_DOCX_TMPL)

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
        doc.save(str(output_file))
        doc.update_fields()
        doc.save(str(output_file))

    print(f"\n[SAVED] {output_file}")

    return output_file
