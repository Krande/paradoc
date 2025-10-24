from paradoc import MY_DOCX_TMPL
from paradoc.io.word.com_api import WordApplication
from paradoc.io.word.inspect import DocxInspector
import pathlib

ROOT_DIR = pathlib.Path(__file__).parent.parent

def functional_doc(dest_doc):
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
                doc.add_text(f"This subsection discusses ")
                doc.add_paragraph()

                # Add figure
                fig_ref = doc.add_figure_with_caption(
                    caption_text=f"Caption for figure in section {subsection_label}",
                    width=150,
                    height=100,
                    use_chapter_numbers=True
                )
                print(f"    Added Figure {section_num}-{subsection_num}")

                # Add table
                table_data = [
                    ["Header 1", "Header 2"],
                    [f"Data {subsection_label}.1", f"Data {subsection_label}.2"]
                ]
                tbl_ref = doc.add_table_with_caption(
                    caption_text=f"Caption for table in section {subsection_label}",
                    rows=2,
                    cols=2,
                    data=table_data,
                    use_chapter_numbers=True
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
        print(f"\n[SAVING] {dest_doc}")
        doc.save(str(dest_doc))
        doc.update_fields()
        doc.save(str(dest_doc))

def non_functional_doc(dest_doc):
    """This uses paradoc to create the exact same docx"""
    from paradoc import OneDoc


def main():
    tmp_path = pathlib.Path(__file__).parent / "temp"

    # Ensure directory exists
    tmp_path.mkdir(parents=True, exist_ok=True)
    working_doc_path = tmp_path / "working_reference.docx"

    functional_doc(working_doc_path.as_posix())
    di = DocxInspector(working_doc_path)

    print(di.fields())


if __name__ == "__main__":
    main()
