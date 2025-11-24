"""Compare XML structure of COM API vs Paradoc generated cross-references."""

import base64
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from paradoc import OneDoc
from paradoc.io.word.com_api import is_word_com_available


@pytest.mark.skipif(not is_word_com_available(), reason="COM automation only if Word COM is available")
def test_compare_com_vs_paradoc_xml(tmp_path):
    """Compare XML structure of COM API document vs Paradoc document."""

    # Step 1: Create COM API reference document
    print("\n" + "=" * 80)
    print("STEP 1: Creating COM API Reference Document")
    print("=" * 80)

    from paradoc.io.word.com_api import WordApplication
    from paradoc import MY_DOCX_TMPL

    com_output = tmp_path / "com_reference.docx"

    with WordApplication(visible=False, run_isolated=True) as word_app:
        doc = word_app.create_document(template=MY_DOCX_TMPL)

        # Section 1
        doc.add_heading("Section 1", level=1)
        doc.add_paragraph("Introduction to section 1.")
        doc.add_paragraph()

        doc.add_heading("Section 1.1", level=2)
        doc.add_text("As shown in ")
        doc.add_paragraph()

        fig1_ref = doc.add_figure_with_caption(
            caption_text="First figure caption", width=150, height=100, use_chapter_numbers=True
        )
        print(f"  Added Figure 1-1 with bookmark: {fig1_ref}")

        doc.add_text("Reference to ")
        doc.add_cross_reference(fig1_ref, include_hyperlink=True)
        doc.add_text(" is shown above.")
        doc.add_paragraph()
        doc.add_paragraph()

        # Section 2
        doc.add_heading("Section 2", level=1)
        doc.add_paragraph("Introduction to section 2.")
        doc.add_paragraph()

        doc.add_heading("Section 2.1", level=2)
        doc.add_text("As shown in ")
        doc.add_paragraph()

        fig2_ref = doc.add_figure_with_caption(
            caption_text="Second figure caption", width=150, height=100, use_chapter_numbers=True
        )
        print(f"  Added Figure 2-1 with bookmark: {fig2_ref}")

        doc.add_text("Reference to ")
        doc.add_cross_reference(fig2_ref, include_hyperlink=True)
        doc.add_text(" and back to ")
        doc.add_cross_reference(fig1_ref, include_hyperlink=True)
        doc.add_text(".")
        doc.add_paragraph()

        # Save and update
        doc.save(str(com_output))
        doc.update_fields()
        doc.save(str(com_output))

    print(f"✓ COM document saved to: {com_output}")

    # Step 2: Create Paradoc document
    print("\n" + "=" * 80)
    print("STEP 2: Creating Paradoc Document")
    print("=" * 80)

    source_dir = tmp_path / "paradoc_test"
    main_dir = source_dir / "00-main"
    main_dir.mkdir(parents=True)

    # Create test image
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )

    images_dir = main_dir / "images"
    images_dir.mkdir(parents=True)

    for i in range(2):
        img_path = images_dir / f"fig{i + 1}.png"
        img_path.write_bytes(png_data)

    md_content = """# Section 1

Introduction to section 1.

## Section 1.1

As shown in [@fig:first]:

![First figure caption](images/fig1.png){#fig:first}

Reference to [@fig:first] is shown above.

# Section 2

Introduction to section 2.

## Section 2.1

As shown in [@fig:second]:

![Second figure caption](images/fig2.png){#fig:second}

Reference to [@fig:second] and back to [@fig:first].
"""

    md_file = main_dir / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    work_dir = tmp_path / "paradoc_work"
    one = OneDoc(source_dir, work_dir=work_dir)
    one.compile("paradoc_test", auto_open=False, export_format="docx", update_docx_with_com=False)

    paradoc_output = work_dir / "_dist" / "paradoc_test.docx"
    print(f"✓ Paradoc document saved to: {paradoc_output}")

    # Step 3: Extract and compare XML
    print("\n" + "=" * 80)
    print("STEP 3: Extracting and Comparing XML")
    print("=" * 80)

    com_xml_dir = tmp_path / "com_xml"
    paradoc_xml_dir = tmp_path / "paradoc_xml"

    extract_docx_xml(com_output, com_xml_dir)
    extract_docx_xml(paradoc_output, paradoc_xml_dir)

    print(f"✓ Extracted COM XML to: {com_xml_dir}")
    print(f"✓ Extracted Paradoc XML to: {paradoc_xml_dir}")

    # Analyze document.xml
    print("\n" + "=" * 80)
    print("ANALYZING DOCUMENT.XML")
    print("=" * 80)

    com_doc_xml = com_xml_dir / "word" / "document.xml"
    paradoc_doc_xml = paradoc_xml_dir / "word" / "document.xml"

    print("\n" + "-" * 80)
    print("COM API DOCUMENT STRUCTURE")
    print("-" * 80)
    analyze_crossref_structure(com_doc_xml, "COM API")

    print("\n" + "-" * 80)
    print("PARADOC DOCUMENT STRUCTURE")
    print("-" * 80)
    analyze_crossref_structure(paradoc_doc_xml, "Paradoc")

    # Generate diagnostic report
    generate_diagnostic_report(com_doc_xml, paradoc_doc_xml, tmp_path)


def extract_docx_xml(docx_path: Path, output_dir: Path):
    """Extract XML files from .docx file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(docx_path, "r") as zip_ref:
        zip_ref.extractall(output_dir)


def analyze_crossref_structure(xml_path: Path, label: str):
    """Analyze cross-reference structure in document.xml."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Namespaces
    nsmap = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }

    print(f"\n[{label}] Analyzing structure...")

    # Find all bookmarks
    bookmarks = []
    for bookmark_start in root.findall(".//w:bookmarkStart", nsmap):
        bm_id = bookmark_start.get("{%s}id" % nsmap["w"])
        bm_name = bookmark_start.get("{%s}name" % nsmap["w"])
        bookmarks.append({"id": bm_id, "name": bm_name})

    print(f"\nBookmarks found: {len(bookmarks)}")
    for bm in bookmarks:
        print(f"  • {bm['name']} (ID: {bm['id']})")

    # Find all REF fields
    ref_fields = []
    paragraphs = root.findall(".//w:p", nsmap)

    for para_idx, para in enumerate(paragraphs):
        # Look for field characters
        runs = para.findall(".//w:r", nsmap)

        in_field = False
        field_instr = ""

        for run in runs:
            # Check for field begin/end
            fld_char = run.find(".//w:fldChar", nsmap)
            if fld_char is not None:
                fld_type = fld_char.get("{%s}fldCharType" % nsmap["w"])
                if fld_type == "begin":
                    in_field = True
                    field_instr = ""
                elif fld_type == "end":
                    if " REF " in field_instr:
                        ref_fields.append({"para_idx": para_idx, "instr": field_instr.strip()})
                    in_field = False

            # Collect instruction text
            if in_field:
                instr_text = run.find(".//w:instrText", nsmap)
                if instr_text is not None and instr_text.text:
                    field_instr += instr_text.text

    print(f"\nREF fields found: {len(ref_fields)}")
    for rf in ref_fields:
        print(f"  • Para {rf['para_idx']}: {rf['instr']}")

    # Find all caption paragraphs (with SEQ fields)
    seq_fields = []
    for para_idx, para in enumerate(paragraphs):
        runs = para.findall(".//w:r", nsmap)

        in_field = False
        field_instr = ""

        for run in runs:
            fld_char = run.find(".//w:fldChar", nsmap)
            if fld_char is not None:
                fld_type = fld_char.get("{%s}fldCharType" % nsmap["w"])
                if fld_type == "begin":
                    in_field = True
                    field_instr = ""
                elif fld_type == "end":
                    if " SEQ " in field_instr:
                        seq_fields.append({"para_idx": para_idx, "instr": field_instr.strip()})
                    in_field = False

            if in_field:
                instr_text = run.find(".//w:instrText", nsmap)
                if instr_text is not None and instr_text.text:
                    field_instr += instr_text.text

    print(f"\nSEQ fields found: {len(seq_fields)}")
    for sf in seq_fields:
        print(f"  • Para {sf['para_idx']}: {sf['instr']}")

    return {"bookmarks": bookmarks, "ref_fields": ref_fields, "seq_fields": seq_fields}


def generate_diagnostic_report(com_xml: Path, paradoc_xml: Path, output_dir: Path):
    """Generate a markdown diagnostic report comparing the two documents."""

    report_path = output_dir / "crossref_comparison_report.md"

    # Parse both XMLs
    com_tree = ET.parse(com_xml)
    paradoc_tree = ET.parse(paradoc_xml)

    nsmap = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    }

    # Extract first figure caption paragraph from each
    def find_first_caption(tree):
        """Find first paragraph containing 'Figure'."""
        for para in tree.findall(".//w:p", nsmap):
            para_text = "".join([t.text for t in para.findall(".//w:t", nsmap) if t.text])
            if "Figure" in para_text and ("caption" in para_text.lower() or "1-1" in para_text):
                return para
        return None

    com_caption_para = find_first_caption(com_tree)
    paradoc_caption_para = find_first_caption(paradoc_tree)

    # Extract first REF field paragraph from each
    def find_first_ref_paragraph(tree):
        """Find first paragraph with REF field."""
        for para in tree.findall(".//w:p", nsmap):
            for run in para.findall(".//w:r", nsmap):
                instr_text = run.find(".//w:instrText", nsmap)
                if instr_text is not None and instr_text.text and " REF " in instr_text.text:
                    return para
        return None

    com_ref_para = find_first_ref_paragraph(com_tree)
    paradoc_ref_para = find_first_ref_paragraph(paradoc_tree)

    # Generate report
    report = f"""# Cross-Reference XML Comparison Report

Generated: {output_dir.name}

## Summary

This report compares the XML structure of a working document created with COM API
versus a document created by Paradoc that has cross-reference issues.

## Key Findings

### Bookmarks

Both documents should have bookmarks around figure captions.

### Caption Structure (First Figure)

#### COM API Caption
```xml
{ET.tostring(com_caption_para, encoding='unicode') if com_caption_para is not None else 'NOT FOUND'}
```

#### Paradoc Caption
```xml
{ET.tostring(paradoc_caption_para, encoding='unicode') if paradoc_caption_para is not None else 'NOT FOUND'}
```

### REF Field Structure (First Reference)

#### COM API REF Field
```xml
{ET.tostring(com_ref_para, encoding='unicode') if com_ref_para is not None else 'NOT FOUND'}
```

#### Paradoc REF Field
```xml
{ET.tostring(paradoc_ref_para, encoding='unicode') if paradoc_ref_para is not None else 'NOT FOUND'}
```

## Analysis

Compare the XML structures above to identify differences in:
1. Bookmark placement and naming
2. SEQ field structure in captions
3. REF field structure in cross-references
4. Field switches and parameters

## Files

- COM API document: {com_xml.parent.parent.name}
- Paradoc document: {paradoc_xml.parent.parent.name}
"""

    report_path.write_text(report, encoding="utf-8")
    print(f"\n✓ Diagnostic report saved to: {report_path}")

    return report_path
