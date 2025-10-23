"""Test 1: Create a complete document using only COM to understand Word's native cross-reference structure."""

import os
import platform
import re
import time
import zipfile
from pathlib import Path

import pytest
from docx import Document


@pytest.mark.skipif(platform.system() != "Windows", reason="COM automation only available on Windows")
def test_com_create_figures_and_tables_with_crossrefs(tmp_path):
    """Create a document with figures and tables in multiple sections using pure COM.

    This test creates:
    - Section 1: 1 figure, 1 table with cross-references
    - Section 2: 1 figure, 1 table with cross-references
    - Cross-references from each section to both sections

    Then we'll analyze the XML before and after field updates.
    """
    print("\n" + "="*80)
    print("TEST 1: PURE COM - FIGURES & TABLES WITH CROSS-REFERENCES")
    print("="*80)

    import win32com.client

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False

    try:
        doc = word.Documents.Add()

        # Configure document for chapter numbering
        print("\n[Step 1] Configuring document for chapter numbering...")
        # Set up heading 1 to restart numbering
        try:
            # This enables chapter numbering for figures and tables
            pass  # Word does this automatically when using SEQ fields with \s switch
        except Exception as e:
            print(f"  [!] Note: {e}")

        # === SECTION 1 ===
        print("\n[Step 2] Creating Section 1...")
        word.Selection.Style = "Heading 1"
        word.Selection.TypeText("SECTION 1")
        word.Selection.TypeParagraph()

        word.Selection.Style = "Normal"
        word.Selection.TypeText("This is the first section with a reference to ")

        # We'll insert the cross-reference after creating the figures
        word.Selection.TypeText("[FIGREF1]")  # Placeholder
        word.Selection.TypeText(".")
        word.Selection.TypeParagraph()
        word.Selection.TypeParagraph()

        # Insert Figure 1-1
        print("  Creating Figure 1-1...")
        shape1 = doc.Shapes.AddShape(1, 100, 100, 150, 100)  # Rectangle
        word.Selection.EndKey(Unit=6)  # Move to end
        word.Selection.TypeParagraph()

        # Insert caption using Word's InsertCaption
        word.Selection.Style = "Caption"
        word.Selection.TypeText("Figure ")

        # Insert SEQ field for figure number
        field1 = word.Selection.Fields.Add(
            Range=word.Selection.Range,
            Type=-1,
            Text="SEQ Figure \\* ARABIC \\s 1",  # \s 1 means restart at each Heading 1
            PreserveFormatting=True
        )
        word.Selection.TypeText(": First Figure Caption")

        # Add bookmark to this caption
        caption1_range = word.Selection.Paragraphs(1).Range
        bookmark1_name = f"_Ref{int(time.time() * 1000) % 1000000000}"
        doc.Bookmarks.Add(bookmark1_name, caption1_range)
        print(f"    Bookmark: {bookmark1_name}")

        word.Selection.TypeParagraph()
        word.Selection.TypeParagraph()

        # Insert Table 1-1
        print("  Creating Table 1-1...")
        table1 = doc.Tables.Add(word.Selection.Range, 2, 2)
        table1.Cell(1, 1).Range.Text = "A1"
        table1.Cell(1, 2).Range.Text = "B1"
        table1.Cell(2, 1).Range.Text = "A2"
        table1.Cell(2, 2).Range.Text = "B2"

        word.Selection.EndKey(Unit=6)
        word.Selection.TypeParagraph()

        # Insert table caption
        word.Selection.Style = "Caption"
        word.Selection.TypeText("Table ")

        field2 = word.Selection.Fields.Add(
            Range=word.Selection.Range,
            Type=-1,
            Text="SEQ Table \\* ARABIC \\s 1",
            PreserveFormatting=True
        )
        word.Selection.TypeText(": First Table Caption")

        caption2_range = word.Selection.Paragraphs(1).Range
        bookmark2_name = f"_Ref{int(time.time() * 1000) % 1000000000 + 1}"
        doc.Bookmarks.Add(bookmark2_name, caption2_range)
        print(f"    Bookmark: {bookmark2_name}")

        word.Selection.TypeParagraph()
        word.Selection.TypeParagraph()

        # === SECTION 2 ===
        print("\n[Step 3] Creating Section 2...")
        word.Selection.Style = "Heading 1"
        word.Selection.TypeText("SECTION 2")
        word.Selection.TypeParagraph()

        word.Selection.Style = "Normal"
        word.Selection.TypeText("This is the second section with a reference to ")
        word.Selection.TypeText("[FIGREF2]")  # Placeholder
        word.Selection.TypeText(".")
        word.Selection.TypeParagraph()
        word.Selection.TypeParagraph()

        # Insert Figure 2-1
        print("  Creating Figure 2-1...")
        shape2 = doc.Shapes.AddShape(1, 100, 100, 150, 100)
        word.Selection.EndKey(Unit=6)
        word.Selection.TypeParagraph()

        word.Selection.Style = "Caption"
        word.Selection.TypeText("Figure ")
        field3 = word.Selection.Fields.Add(
            Range=word.Selection.Range,
            Type=-1,
            Text="SEQ Figure \\* ARABIC \\s 1",
            PreserveFormatting=True
        )
        word.Selection.TypeText(": Second Figure Caption")

        caption3_range = word.Selection.Paragraphs(1).Range
        bookmark3_name = f"_Ref{int(time.time() * 1000) % 1000000000 + 2}"
        doc.Bookmarks.Add(bookmark3_name, caption3_range)
        print(f"    Bookmark: {bookmark3_name}")

        word.Selection.TypeParagraph()
        word.Selection.TypeParagraph()

        # Insert Table 2-1
        print("  Creating Table 2-1...")
        table2 = doc.Tables.Add(word.Selection.Range, 2, 2)
        table2.Cell(1, 1).Range.Text = "C1"
        table2.Cell(1, 2).Range.Text = "D1"
        table2.Cell(2, 1).Range.Text = "C2"
        table2.Cell(2, 2).Range.Text = "D2"

        word.Selection.EndKey(Unit=6)
        word.Selection.TypeParagraph()

        word.Selection.Style = "Caption"
        word.Selection.TypeText("Table ")
        field4 = word.Selection.Fields.Add(
            Range=word.Selection.Range,
            Type=-1,
            Text="SEQ Table \\* ARABIC \\s 1",
            PreserveFormatting=True
        )
        word.Selection.TypeText(": Second Table Caption")

        caption4_range = word.Selection.Paragraphs(1).Range
        bookmark4_name = f"_Ref{int(time.time() * 1000) % 1000000000 + 3}"
        doc.Bookmarks.Add(bookmark4_name, caption4_range)
        print(f"    Bookmark: {bookmark4_name}")

        word.Selection.TypeParagraph()

        # Add cross-section references in Section 2
        word.Selection.Style = "Normal"
        word.Selection.TypeText("Cross-reference to second figure: ")
        word.Selection.TypeText("[FIGREF2B]")
        word.Selection.TypeText(". Also reference the first figure from section 1: ")
        word.Selection.TypeText("[FIGREF1B]")
        word.Selection.TypeText(".")
        word.Selection.TypeParagraph()

        # Save BEFORE adding cross-references
        print("\n[Step 4] Saving document BEFORE cross-references...")
        before_file = tmp_path / "before_crossrefs.docx"
        doc.SaveAs(str(before_file.absolute()))
        print(f"  Saved: {before_file}")

        # Now replace placeholders with actual cross-references
        print("\n[Step 5] Replacing placeholders with cross-references...")

        # Store bookmark info for later
        bookmarks = {
            'fig1': (bookmark1_name, 1),
            'fig2': (bookmark3_name, 2),
            'tbl1': (bookmark2_name, 1),
            'tbl2': (bookmark4_name, 2)
        }

        # Find and replace [FIGREF1]
        word.Selection.HomeKey(Unit=6)  # Go to start of document
        found = word.Selection.Find.Execute(FindText="[FIGREF1]", Forward=True, MatchWholeWord=False)
        if found:
            print(f"  Replacing [FIGREF1] with cross-reference...")
            word.Selection.Delete()
            try:
                # Insert cross-reference using InsertCrossReference
                # ReferenceType can be: "Figure", "Table", etc.
                # ReferenceKind: 2 = wdOnlyLabelAndNumber, 0 = wdEntireCaption, 1 = wdOnlyCaption
                word.Selection.InsertCrossReference(
                    ReferenceType="Figure",
                    ReferenceKind=2,  # Only label and number
                    ReferenceItem=1,  # First figure
                    InsertAsHyperlink=True
                )
                print("    [OK] Cross-reference inserted")
            except Exception as e:
                print(f"    [X] Failed: {e}")

        # Find and replace [FIGREF2]
        word.Selection.HomeKey(Unit=6)
        found = word.Selection.Find.Execute(FindText="[FIGREF2]", Forward=True, MatchWholeWord=False)
        if found:
            print(f"  Replacing [FIGREF2] with cross-reference...")
            word.Selection.Delete()
            try:
                word.Selection.InsertCrossReference(
                    ReferenceType="Figure",
                    ReferenceKind=2,
                    ReferenceItem=2,  # Second figure
                    InsertAsHyperlink=True
                )
                print("    [OK] Cross-reference inserted")
            except Exception as e:
                print(f"    [X] Failed: {e}")

        # Find and replace [FIGREF2B]
        word.Selection.HomeKey(Unit=6)
        found = word.Selection.Find.Execute(FindText="[FIGREF2B]", Forward=True, MatchWholeWord=False)
        if found:
            print(f"  Replacing [FIGREF2B] with cross-reference...")
            word.Selection.Delete()
            try:
                word.Selection.InsertCrossReference(
                    ReferenceType="Figure",
                    ReferenceKind=2,
                    ReferenceItem=2,
                    InsertAsHyperlink=True
                )
                print("    [OK] Cross-reference inserted")
            except Exception as e:
                print(f"    [X] Failed: {e}")

        # Find and replace [FIGREF1B]
        word.Selection.HomeKey(Unit=6)
        found = word.Selection.Find.Execute(FindText="[FIGREF1B]", Forward=True, MatchWholeWord=False)
        if found:
            print(f"  Replacing [FIGREF1B] with cross-reference...")
            word.Selection.Delete()
            try:
                word.Selection.InsertCrossReference(
                    ReferenceType="Figure",
                    ReferenceKind=2,
                    ReferenceItem=1,
                    InsertAsHyperlink=True
                )
                print("    [OK] Cross-reference inserted")
            except Exception as e:
                print(f"    [X] Failed: {e}")

        # Save AFTER adding cross-references (before field update)
        print("\n[Step 6] Saving document AFTER cross-references (before update)...")
        after_file = tmp_path / "after_crossrefs_before_update.docx"
        doc.SaveAs(str(after_file.absolute()))
        print(f"  Saved: {after_file}")

        # Update all fields
        print("\n[Step 7] Updating all fields...")
        doc.Fields.Update()
        time.sleep(1)

        # Save AFTER field update
        print("\n[Step 8] Saving document AFTER field update...")
        final_file = tmp_path / "after_field_update.docx"
        doc.SaveAs(str(final_file.absolute()))
        print(f"  Saved: {final_file}")

        doc.Close(SaveChanges=False)

    finally:
        word.Quit()

    # === ANALYSIS ===
    print("\n" + "="*80)
    print("ANALYSIS: Comparing XML at each stage")
    print("="*80)

    # Analyze each document
    for filename in ["before_crossrefs.docx", "after_crossrefs_before_update.docx", "after_field_update.docx"]:
        filepath = tmp_path / filename
        if filepath.exists():
            print(f"\n### {filename} ###")
            analyze_document_xml(filepath, tmp_path, filename.replace('.docx', ''))

    # Verify the final document
    print("\n" + "="*80)
    print("VERIFICATION: Checking final document text")
    print("="*80)

    doc = Document(str(final_file))
    full_text = "\n".join([p.text for p in doc.paragraphs])
    print(full_text)

    # Check for duplicated labels
    duplicated_figure = re.findall(r'Figure\s+Figure', full_text, re.IGNORECASE)
    duplicated_table = re.findall(r'Table\s+Table', full_text, re.IGNORECASE)

    if duplicated_figure:
        print(f"\n[X] ERROR: Found duplicated 'Figure' labels: {duplicated_figure}")
    else:
        print("\n[✓] No duplicated 'Figure' labels")

    if duplicated_table:
        print(f"[X] ERROR: Found duplicated 'Table' labels: {duplicated_table}")
    else:
        print("[✓] No duplicated 'Table' labels")

    # Check for correct numbering
    fig_refs = re.findall(r'Figure\s+(\d+-\d+)', full_text)
    print(f"\nFigure references found: {fig_refs}")

    assert not duplicated_figure, f"Found duplicated 'Figure' labels: {duplicated_figure}"
    assert not duplicated_table, f"Found duplicated 'Table' labels: {duplicated_table}"

    # Should have at least 4 figure references (4 placeholders we replaced)
    assert len(fig_refs) >= 4, f"Expected at least 4 figure references, found {len(fig_refs)}"

    print("\n[✓] All checks passed!")


def analyze_document_xml(docx_file: Path, output_dir: Path, prefix: str):
    """Analyze and extract key XML patterns from a document."""
    with zipfile.ZipFile(docx_file, 'r') as zip_ref:
        with zip_ref.open('word/document.xml') as xml_file:
            xml_content = xml_file.read().decode('utf-8')

    # Save full XML
    xml_out = output_dir / f"{prefix}_document.xml"
    xml_out.write_text(xml_content, encoding='utf-8')
    print(f"  Full XML saved to: {xml_out.name}")

    # Extract bookmarks
    bookmarks = re.findall(r'<w:bookmarkStart w:id="(\d+)" w:name="([^"]+)"', xml_content)
    print(f"  Bookmarks: {len(bookmarks)}")
    for bm_id, bm_name in bookmarks[:5]:  # Show first 5
        print(f"    - {bm_name} (id={bm_id})")

    # Extract REF fields
    ref_fields = re.findall(r'<w:instrText[^>]*>\s*REF\s+([^<]+)</w:instrText>', xml_content)
    print(f"  REF fields: {len(ref_fields)}")
    for ref in ref_fields[:5]:
        print(f"    - REF {ref.strip()}")

    # Extract SEQ fields
    seq_fields = re.findall(r'<w:instrText[^>]*>\s*SEQ\s+([^<]+)</w:instrText>', xml_content)
    print(f"  SEQ fields: {len(seq_fields)}")
    for seq in seq_fields[:5]:
        print(f"    - SEQ {seq.strip()}")


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_com_create_figures_and_tables_with_crossrefs(Path(tmp))

