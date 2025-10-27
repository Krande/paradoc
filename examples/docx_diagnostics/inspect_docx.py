from paradoc import MY_DOCX_TMPL, OneDoc
from paradoc.io.word.com_api import WordApplication
from paradoc.io.word.inspect import DocxInspector
import pathlib

ROOT_DIR = pathlib.Path(__file__).parent.parent

def functional_doc(dest_doc):
    with WordApplication(visible=False) as word_app:
        doc = word_app.create_document(template=MY_DOCX_TMPL)
        doc.add_page_break()
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
                    use_chapter_numbers=True,
                    image_path="pdoc/00-main/images/31343C.png"
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

def non_functional_doc(source_doc_dir, dest_doc):
    """This uses paradoc to create the exact same docx"""
    from paradoc import OneDoc

    od = OneDoc(source_doc_dir)
    od.compile(dest_doc, export_format="docx")

def main():
    this_dir = pathlib.Path(__file__).parent
    tmp_path = this_dir / "temp"
    pdoc_dir = this_dir / 'pdoc'
    # Ensure directory exists
    tmp_path.mkdir(parents=True, exist_ok=True)
    working_doc_path = tmp_path / "working_reference.docx"
    non_func_path = tmp_path / "non_functional_reference.docx"

    od = OneDoc(pdoc_dir)
    ast = od.get_ast()

    if not working_doc_path.exists():
        functional_doc(working_doc_path.as_posix())

    if not non_func_path.exists():
        non_functional_doc(pdoc_dir, non_func_path.as_posix())

    # Inspect working doc
    print("="*80)
    print("WORKING DOCUMENT ANALYSIS")
    print("="*80)
    di = DocxInspector(working_doc_path)

    print("\n--- BOOKMARKS ---")
    bookmarks = di.bookmarks()
    for bm in bookmarks:
        print(f"  {bm.name} (id={bm.id}) in {bm.part}")
        print(f"    Context: {bm.context[:100]}")

    print(f"\nTotal bookmarks: {len(bookmarks)}")

    print("\n--- FIELDS ---")
    fields = di.fields()
    for field in fields:
        print(f"  {field.kind}: {field.instr}")
        print(f"    Context: {field.context[:100]}")

    print(f"\nTotal fields: {len(fields)}")

    print("\n--- CROSS REFERENCES ---")
    cross_refs = di.cross_refs()
    for cr in cross_refs:
        print(f"  {cr.ref_type} -> {cr.target_or_label} (switches: {cr.switches})")

    print(f"\nTotal cross-refs: {len(cross_refs)}")

    print("\n--- SEQ LABELS ---")
    seq_labels = di.seq_labels()
    print(f"  {seq_labels}")

    print("\n--- MISSING REF TARGETS ---")
    missing = di.missing_ref_targets()
    for m in missing:
        print(f"  {m.ref_type} -> {m.target_or_label} (NOT FOUND)")

    print(f"\nTotal missing targets: {len(missing)}")

    # Inspect Non-working doc
    print("\n" + "="*80)
    print("NON-FUNCTIONAL DOCUMENT ANALYSIS")
    print("="*80)
    di_n = DocxInspector(non_func_path)

    print("\n--- BOOKMARKS ---")
    bookmarks_n = di_n.bookmarks()
    for bm in bookmarks_n:
        print(f"  {bm.name} (id={bm.id}) in {bm.part}")
        print(f"    Context: {bm.context[:100]}")

    print(f"\nTotal bookmarks: {len(bookmarks_n)}")

    print("\n--- FIELDS ---")
    fields_n = di_n.fields()
    for field in fields_n:
        print(f"  {field.kind}: {field.instr}")
        print(f"    Context: {field.context[:100]}")

    print(f"\nTotal fields: {len(fields_n)}")

    print("\n--- CROSS REFERENCES ---")
    cross_refs_n = di_n.cross_refs()
    for cr in cross_refs_n:
        print(f"  {cr.ref_type} -> {cr.target_or_label} (switches: {cr.switches})")

    print(f"\nTotal cross-refs: {len(cross_refs_n)}")

    print("\n--- SEQ LABELS ---")
    seq_labels_n = di_n.seq_labels()
    print(f"  {seq_labels_n}")

    print("\n--- MISSING REF TARGETS ---")
    missing_n = di_n.missing_ref_targets()
    for m in missing_n:
        print(f"  {m.ref_type} -> {m.target_or_label} (NOT FOUND)")

    print(f"\nTotal missing targets: {len(missing_n)}")

    # COMPARISON
    print("\n" + "="*80)
    print("COMPARISON SUMMARY")
    print("="*80)
    print(f"\nBookmarks:")
    print(f"  Working: {len(bookmarks)}")
    print(f"  Non-functional: {len(bookmarks_n)}")

    print(f"\nFields:")
    print(f"  Working: {len(fields)}")
    print(f"  Non-functional: {len(fields_n)}")

    print(f"\nCross-references:")
    print(f"  Working: {len(cross_refs)}")
    print(f"  Non-functional: {len(cross_refs_n)}")

    print(f"\nMissing REF targets:")
    print(f"  Working: {len(missing)}")
    print(f"  Non-functional: {len(missing_n)}")

    # Detailed bookmark comparison
    working_bm_names = {bm.name for bm in bookmarks if bm.name}
    nonfunc_bm_names = {bm.name for bm in bookmarks_n if bm.name}

    print(f"\nBookmark names in working but not in non-functional:")
    for name in sorted(working_bm_names - nonfunc_bm_names):
        print(f"  - {name}")

    print(f"\nBookmark names in non-functional but not in working:")
    for name in sorted(nonfunc_bm_names - working_bm_names):
        print(f"  - {name}")

    # Detailed field instruction comparison
    print(f"\n" + "="*80)
    print("DETAILED FIELD INSTRUCTION ANALYSIS")
    print("="*80)

    working_ref_targets = [cr.target_or_label for cr in cross_refs if cr.ref_type == 'REF']
    nonfunc_ref_targets = [cr.target_or_label for cr in cross_refs_n if cr.ref_type == 'REF']

    print(f"\nWorking document REF targets ({len(working_ref_targets)}):")
    for target in working_ref_targets:
        print(f"  - {target}")

    print(f"\nNon-functional document REF targets ({len(nonfunc_ref_targets)}):")
    for target in nonfunc_ref_targets:
        print(f"  - {target}")

    # Check which bookmarks are referenced vs unreferenced
    working_ref_set = set(working_ref_targets)
    nonfunc_ref_set = set(nonfunc_ref_targets)

    print(f"\nWorking: Figure-related bookmarks vs REF targets:")
    for bm in bookmarks:
        if bm.name and ('fig' in bm.name.lower() or 'Ref2' in bm.name or 'Ref551' in bm.name):
            is_referenced = bm.name in working_ref_set
            print(f"  {bm.name:30s} {'[X] REFERENCED' if is_referenced else '[ ] NOT REFERENCED'}")

    print(f"\nNon-functional: Figure-related bookmarks vs REF targets:")
    for bm in bookmarks_n:
        if bm.name and 'fig' in bm.name.lower():
            is_referenced = bm.name in nonfunc_ref_set
            print(f"  {bm.name:30s} {'[X] REFERENCED' if is_referenced else '[ ] NOT REFERENCED'}")


if __name__ == "__main__":
    main()
