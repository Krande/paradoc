"""Test that SEQ fields are created in captions for figures, tables, and equations across sections."""

import base64
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from paradoc import OneDoc


def test_crossref_field_codes_comprehensive(tmp_path):
    r"""Verify that proper Word cross-reference field codes are created for figures, tables, and equations.

    For valid Word cross-references, this test strictly verifies:
    1. Captions have proper structure:
       - Plain text label (e.g., "Figure ")
       - STYLEREF field for chapter/heading number
       - Hyphen separator
       - SEQ field for incremental numbering within chapter
       - Caption text
    2. SEQ fields use correct identifiers and switches:
       - Identifier matches element type (Figure, Table, Equation)
       - ARABIC numbering format
       - \s 1 switch for chapter-based numbering
       - \r 1 switch for first element to restart numbering
    3. STYLEREF fields reference correct heading styles
    4. Fields are properly created across multiple sections

    Note: Bookmarks and REF fields are validated in separate tests as they may require
    Word COM field updates to be fully functional.
    """
    source_dir = tmp_path / "test_doc"
    main_dir = source_dir / "00-main"
    main_dir.mkdir(parents=True)

    # Create test images
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )

    images_dir = main_dir / "images"
    images_dir.mkdir(parents=True)

    for i in range(2):
        img_path = images_dir / f"fig{i+1}.png"
        img_path.write_bytes(png_data)

    # Create markdown with 2 sections containing figures, tables, and equations
    md_content = """# Section 1: Introduction

This section introduces the first figure, table, and equation.

## Subsection 1.1: First Figure

As shown in [@fig:trends], the historical trends demonstrate a clear pattern.

![Historical trends visualization](images/fig1.png){#fig:trends}

## Subsection 1.2: First Table

The metrics in [@tbl:metrics] show baseline performance.

+------------------+-----------+------+-------+
| Metric Name      | Status    | Unit | Value |
+==================+===========+======+=======+
| Accuracy         | Excellent | %    |  94.5 |
+------------------+-----------+------+-------+
| Efficiency       | Good      | %    |  87.2 |
+------------------+-----------+------+-------+

Table: Performance metrics {#tbl:metrics}

## Subsection 1.3: First Equation

The fundamental equation [@eq:basic] defines the relationship:

$$ E = mc^2 $$ {#eq:basic}

# Section 2: Analysis

This section presents additional figures, tables, and equations for detailed analysis.

## Subsection 2.1: Second Figure

As shown in [@fig:analysis], the analysis reveals important insights. Compare this with [@fig:trends] from Section 1.

![Analysis results visualization](images/fig2.png){#fig:analysis}

## Subsection 2.2: Second Table

The performance comparison in [@tbl:comparison] shows improvements relative to [@tbl:metrics].

+--------------+-------------+-------+
| Period       | Metric      | Value |
+==============+=============+=======+
| Q1           | Performance |  85.3 |
+--------------+-------------+-------+
| Q2           | Performance |  91.2 |
+--------------+-------------+-------+

Table: Performance comparison {#tbl:comparison}

## Subsection 2.3: Second Equation

The derived equation [@eq:derived] builds on [@eq:basic]:

$$ F = ma $$ {#eq:derived}

# Section 3: Conclusions

Summary with references to all elements:
- Figures: [@fig:trends] and [@fig:analysis]
- Tables: [@tbl:metrics] and [@tbl:comparison]
- Equations: [@eq:basic] and [@eq:derived]
"""

    md_file = main_dir / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    # Compile the document
    work_dir = tmp_path / "work"
    one = OneDoc(source_dir, work_dir=work_dir)
    docx = one.compile("test_field_codes", auto_open=False, export_format="docx", update_docx_with_com=False)

    ref_helper = docx.ref_helper
    assert len(ref_helper.figures) == 2, "Should find exactly two figures"
    assert len(ref_helper.tables) == 2, "Should find exactly two tables"
    assert len(ref_helper.equations) == 2, "Should find exactly two equations"

    output_file = work_dir / "_dist" / "test_field_codes.docx"
    assert output_file.exists(), "Output file should be created"

    # Extract and analyze XML
    xml_dir = tmp_path / "xml_extract"
    extract_docx_xml(output_file, xml_dir)

    doc_xml = xml_dir / "word" / "document.xml"
    tree = ET.parse(doc_xml)
    root = tree.getroot()

    nsmap = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    }

    # Find all SEQ fields (in captions), STYLEREF fields, and REF fields (cross-references)
    seq_fields = []
    styleref_fields = []
    ref_fields = []
    bookmarks = []

    # Track caption paragraphs and their field structure
    caption_structures = []

    # First, find ALL bookmarks in the document
    all_bookmark_starts = root.findall(".//w:bookmarkStart", nsmap)
    for bm in all_bookmark_starts:
        bm_name = bm.get("{%s}name" % nsmap["w"])
        bm_id = bm.get("{%s}id" % nsmap["w"])
        # Find which paragraph this bookmark is in
        para = bm
        while para is not None and para.tag != "{%s}p" % nsmap["w"]:
            para = para.getparent() if hasattr(para, 'getparent') else None
        if para is not None:
            para_text = "".join([t.text for t in para.findall(".//w:t", nsmap) if t.text])
            para_idx = list(root.findall(".//w:p", nsmap)).index(para)
        else:
            para_text = ""
            para_idx = -1
        bookmarks.append({"name": bm_name, "id": bm_id, "para_idx": para_idx, "para_text": para_text[:60]})

    paragraphs = root.findall(".//w:p", nsmap)

    print("\n" + "=" * 80)
    print("ANALYZING DOCUMENT STRUCTURE")
    print("=" * 80)

    for para_idx, para in enumerate(paragraphs):
        para_text = "".join([t.text for t in para.findall(".//w:t", nsmap) if t.text])

        # Check if this is a caption or cross-reference paragraph
        # Captions have format: "Figure 1-1:" or "Table 2-3:" not "Subsection 1.1:"
        # Equations are inline captions in the math paragraph: "... (Eq. 1-1)"
        is_caption = (
            ((para_text.startswith("Figure ") or para_text.startswith("Table "))
             and "-" in para_text
             and ":" in para_text)
            or ("(Eq." in para_text and "-" in para_text and ")" in para_text)
        )
        is_xref = any(marker in para_text.lower() for marker in ["as shown in", "compare", "relative to", "builds on"])

        if is_caption:
            # Analyze caption structure in detail
            caption_info = {
                "para_idx": para_idx,
                "para_text": para_text[:80],
                "seq_field": None,
                "styleref_field": None,
                "has_hyphen": "-" in para_text,
                "label": None
            }

            runs = para.findall(".//w:r", nsmap)

            for run in runs:
                instr_text = run.find(".//w:instrText", nsmap)
                if instr_text is not None and instr_text.text:
                    if " SEQ " in instr_text.text:
                        caption_info["seq_field"] = instr_text.text.strip()
                    if " STYLEREF " in instr_text.text or "STYLEREF " in instr_text.text:
                        caption_info["styleref_field"] = instr_text.text.strip()

            # Determine caption type
            if "Figure" in para_text:
                caption_info["label"] = "Figure"
            elif "Table" in para_text:
                caption_info["label"] = "Table"
            elif "Equation" in para_text or "Eq" in para_text:
                caption_info["label"] = "Equation"

            caption_structures.append(caption_info)

        # Collect all fields for analysis
        # Changed: Scan ALL paragraphs for REF fields, not just those with specific marker phrases
        # REF fields can appear in any paragraph that references a figure/table/equation
        if is_caption:
            # Only collect SEQ and STYLEREF fields from caption paragraphs
            runs = para.findall(".//w:r", nsmap)

            for run in runs:
                instr_text = run.find(".//w:instrText", nsmap)
                if instr_text is not None and instr_text.text:
                    if " SEQ " in instr_text.text:
                        seq_fields.append({
                            "para_idx": para_idx,
                            "instr": instr_text.text.strip(),
                            "para_text": para_text[:80]
                        })

                    if " STYLEREF " in instr_text.text or "STYLEREF " in instr_text.text:
                        styleref_fields.append({
                            "para_idx": para_idx,
                            "instr": instr_text.text.strip(),
                            "para_text": para_text[:80]
                        })

        # Scan ALL paragraphs for REF fields (cross-references can be anywhere)
        runs = para.findall(".//w:r", nsmap)
        for run in runs:
            instr_text = run.find(".//w:instrText", nsmap)
            if instr_text is not None and instr_text.text:
                if " REF " in instr_text.text:
                    ref_fields.append({
                        "para_idx": para_idx,
                        "instr": instr_text.text.strip(),
                        "para_text": para_text[:80]
                    })

    print("\n" + "=" * 80)
    print("BOOKMARKS FOUND")
    print("=" * 80)
    print(f"Total bookmarks: {len(bookmarks)}\n")

    # Note: Bookmarks may use original IDs (e.g., "fig:trends") or _Ref style depending on context
    fig_bookmarks = [bm for bm in bookmarks if "fig" in bm["name"].lower()]
    tbl_bookmarks = [bm for bm in bookmarks if "tbl" in bm["name"].lower()]
    eq_bookmarks = [bm for bm in bookmarks if "eq" in bm["name"].lower()]

    print(f"Figure bookmarks ({len(fig_bookmarks)}):")
    for bm in fig_bookmarks:
        print(f"  • {bm['name']} (ID: {bm['id']}) - Para {bm['para_idx']}: {bm['para_text']}")

    print(f"\nTable bookmarks ({len(tbl_bookmarks)}):")
    for bm in tbl_bookmarks:
        print(f"  • {bm['name']} (ID: {bm['id']}) - Para {bm['para_idx']}: {bm['para_text']}")

    print(f"\nEquation bookmarks ({len(eq_bookmarks)}):")
    for bm in eq_bookmarks:
        print(f"  • {bm['name']} (ID: {bm['id']}) - Para {bm['para_idx']}: {bm['para_text']}")

    print("\n" + "=" * 80)
    print("CAPTION STRUCTURES (Detailed Analysis)")
    print("=" * 80)
    print(f"Total captions found: {len(caption_structures)}\n")

    for cap in caption_structures:
        print(f"Caption at Para {cap['para_idx']}: {cap['label'] or 'Unknown'}")
        print(f"  Text: {cap['para_text']}")
        print(f"  Has hyphen separator: {cap['has_hyphen']}")
        print(f"  STYLEREF field: {cap['styleref_field'] or 'NOT FOUND ❌'}")
        print(f"  SEQ field: {cap['seq_field'] or 'NOT FOUND ❌'}")
        print()

    print("\n" + "=" * 80)
    print("SEQ FIELDS FOUND (Captions)")
    print("=" * 80)
    print(f"Total SEQ fields: {len(seq_fields)}\n")

    # Group SEQ fields by type
    fig_seq_fields = [sf for sf in seq_fields if "Figure" in sf["instr"]]
    tbl_seq_fields = [sf for sf in seq_fields if "Table" in sf["instr"]]
    eq_seq_fields = [sf for sf in seq_fields if "Equation" in sf["instr"] or "Eq" in sf["instr"]]

    print(f"Figure SEQ fields ({len(fig_seq_fields)}):")
    for sf in fig_seq_fields:
        print(f"  • Para {sf['para_idx']}: {sf['instr']}")

    print(f"\nTable SEQ fields ({len(tbl_seq_fields)}):")
    for sf in tbl_seq_fields:
        print(f"  • Para {sf['para_idx']}: {sf['instr']}")

    print(f"\nEquation SEQ fields ({len(eq_seq_fields)}):")
    for sf in eq_seq_fields:
        print(f"  • Para {sf['para_idx']}: {sf['instr']}")

    print("\n" + "=" * 80)
    print("STYLEREF FIELDS FOUND")
    print("=" * 80)
    print(f"Total STYLEREF fields: {len(styleref_fields)}\n")

    for sf in styleref_fields:
        print(f"  • Para {sf['para_idx']}: {sf['instr']}")
        print(f"    Context: {sf['para_text']}")

    print("\n" + "=" * 80)
    print("REF FIELDS FOUND (Cross-references)")
    print("=" * 80)
    print(f"Total REF fields: {len(ref_fields)}")

    if len(ref_fields) > 0:
        print("\nREF fields found:")
        for rf in ref_fields:
            print(f"  • Para {rf['para_idx']}: {rf['instr']}")
            print(f"    Context: {rf['para_text']}")
    else:
        print("\nWARNING: NO REF FIELDS FOUND!")
        print("Cross-references are NOT being created as proper Word field codes.")
        print("\nLet's examine what IS in the cross-reference paragraphs:")

        # Check paragraphs that should have cross-references
        xref_paragraphs = []
        for para_idx, para in enumerate(paragraphs):
            para_text = "".join([t.text for t in para.findall(".//w:t", nsmap) if t.text])
            if any(marker in para_text.lower() for marker in ["as shown in", "compare", "relative to", "builds on"]):
                xref_paragraphs.append({"para_idx": para_idx, "text": para_text})

        print(f"\nFound {len(xref_paragraphs)} paragraphs with cross-reference text:")
        for xref_para in xref_paragraphs[:5]:  # Show first 5
            print(f"\n  Para {xref_para['para_idx']}: {xref_para['text'][:100]}")

            # Check for hyperlinks
            para = paragraphs[xref_para['para_idx']]
            hyperlinks = para.findall(".//w:hyperlink", nsmap)
            if hyperlinks:
                print(f"    Contains {len(hyperlinks)} hyperlink(s)")
                for hl in hyperlinks:
                    anchor = hl.get("{%s}anchor" % nsmap["w"])
                    hl_text = "".join([t.text for t in hl.findall(".//w:t", nsmap) if t.text])
                    print(f"      - Hyperlink to '{anchor}': '{hl_text}'")
            else:
                print(f"    No hyperlinks found - likely plain text!")

    # STRICT ASSERTIONS FOR VALID WORD CROSS-REFERENCES
    print("\n" + "=" * 80)
    print("STRICT VERIFICATION - VALID WORD CROSS-REFERENCES")
    print("=" * 80)

    # REQUIREMENT 0: Cross-references MUST be REF fields, not hyperlinks or plain text
    # We have cross-references in the markdown ([@fig:trends], [@tbl:metrics], etc.)
    # These MUST be converted to proper Word REF fields
    expected_min_ref_fields = 8  # At minimum: 2 fig refs + 2 tbl refs in conclusions section
    assert len(ref_fields) >= expected_min_ref_fields, (
        f"CRITICAL: Expected at least {expected_min_ref_fields} REF fields for cross-references, "
        f"but found {len(ref_fields)}.\n"
        "Valid Word cross-references MUST use REF fields, not hyperlinks or plain text.\n"
        "The document currently has hyperlinks or plain text instead of proper cross-reference fields.\n"
        "This is NOT a valid Word document with proper cross-references."
    )
    print(f"[OK] Found {len(ref_fields)} REF fields for cross-references")

    # REQUIREMENT 1: Every caption must have both STYLEREF and SEQ fields
    fig_captions = [c for c in caption_structures if c["label"] == "Figure"]
    tbl_captions = [c for c in caption_structures if c["label"] == "Table"]
    eq_captions = [c for c in caption_structures if c["label"] == "Equation"]

    assert len(fig_captions) >= 2, f"Expected at least 2 figure captions, found {len(fig_captions)}"
    assert len(tbl_captions) >= 2, f"Expected at least 2 table captions, found {len(tbl_captions)}"
    assert len(eq_captions) >= 2, f"Expected at least 2 equation captions, found {len(eq_captions)}"
    print(f"[OK] Found {len(fig_captions)} figure captions, {len(tbl_captions)} table captions, and {len(eq_captions)} equation captions")

    # Verify every caption has BOTH STYLEREF and SEQ fields
    # Note: Equations have inline captions so they may not have ":" separator
    for cap in fig_captions + tbl_captions:
        assert cap["styleref_field"] is not None, (
            f"Caption at para {cap['para_idx']} MISSING STYLEREF field. "
            f"Valid Word captions MUST have STYLEREF for chapter number. Caption: {cap['para_text']}"
        )
        assert cap["seq_field"] is not None, (
            f"Caption at para {cap['para_idx']} MISSING SEQ field. "
            f"Valid Word captions MUST have SEQ for numbering. Caption: {cap['para_text']}"
        )
        assert cap["has_hyphen"], (
            f"Caption at para {cap['para_idx']} MISSING hyphen separator. "
            f"Valid Word captions use format 'Label STYLEREF-SEQ: Text'. Caption: {cap['para_text']}"
        )


    # Verify equation captions have STYLEREF and SEQ fields (they use inline format)
    for cap in eq_captions:
        assert cap["styleref_field"] is not None, (
            f"Equation caption at para {cap['para_idx']} MISSING STYLEREF field. "
            f"Valid Word equation captions MUST have STYLEREF for chapter number. Caption: {cap['para_text']}"
        )
        assert cap["seq_field"] is not None, (
            f"Equation caption at para {cap['para_idx']} MISSING SEQ field. "
            f"Valid Word equation captions MUST have SEQ for numbering. Caption: {cap['para_text']}"
        )
        assert cap["has_hyphen"], (
            f"Equation caption at para {cap['para_idx']} MISSING hyphen separator. "
            f"Valid Word equation captions use format '(Eq. STYLEREF-SEQ)'. Caption: {cap['para_text']}"
        )

    print("[OK] All captions have required STYLEREF and SEQ fields with hyphen separator")

    # REQUIREMENT 2: SEQ fields must have correct structure
    assert len(fig_seq_fields) >= 2, (
        f"Expected at least 2 Figure SEQ fields, found {len(fig_seq_fields)}. "
        "SEQ fields MUST be created in figure captions."
    )
    assert len(tbl_seq_fields) >= 2, (
        f"Expected at least 2 Table SEQ fields, found {len(tbl_seq_fields)}. "
        "SEQ fields MUST be created in table captions."
    )
    assert len(eq_seq_fields) >= 2, (
        f"Expected at least 2 Equation SEQ fields, found {len(eq_seq_fields)}. "
        "SEQ fields MUST be created in equation captions."
    )
    print(f"[OK] Found {len(fig_seq_fields)} Figure SEQ fields, {len(tbl_seq_fields)} Table SEQ fields, and {len(eq_seq_fields)} Equation SEQ fields")

    # REQUIREMENT 3: SEQ fields must have ARABIC numbering and \s switch for chapter-based numbering
    for sf in seq_fields:
        assert "ARABIC" in sf["instr"], (
            f"SEQ field MUST use ARABIC numbering format. Found: {sf['instr']}"
        )
        assert "\\s 1" in sf["instr"] or "\\s1" in sf["instr"], (
            f"SEQ field MUST have \\s 1 switch for chapter-based numbering. Found: {sf['instr']}"
        )
    print("[OK] All SEQ fields have ARABIC numbering and \\s 1 switch for chapter-based numbering")

    # REQUIREMENT 4: First SEQ field of each type must have \r 1 to restart numbering
    # Find first figure, table, and equation SEQ fields
    if len(fig_seq_fields) > 0:
        first_fig_seq = min(fig_seq_fields, key=lambda x: x["para_idx"])
        assert "\\r 1" in first_fig_seq["instr"] or "\\r1" in first_fig_seq["instr"], (
            f"First Figure SEQ field MUST have \\r 1 switch to initialize numbering. "
            f"Found: {first_fig_seq['instr']}"
        )
    print(f"[OK] Tested across {len(fig_captions)} figures, {len(tbl_captions)} tables, and {len(eq_captions)} equations in multiple sections")

    if len(tbl_seq_fields) > 0:
        first_tbl_seq = min(tbl_seq_fields, key=lambda x: x["para_idx"])
        assert "\\r 1" in first_tbl_seq["instr"] or "\\r1" in first_tbl_seq["instr"], (
            f"First Table SEQ field MUST have \\r 1 switch to initialize numbering. "
            f"Found: {first_tbl_seq['instr']}"
        )
        print("[OK] First Table SEQ field has \\r 1 switch to initialize numbering")

    # REQUIREMENT 5: SEQ fields use correct identifiers
    for sf in fig_seq_fields:
        assert "Figure" in sf["instr"], (
            f"Figure SEQ field MUST use 'Figure' identifier. Found: {sf['instr']}"
        )
    for sf in tbl_seq_fields:
        assert "Table" in sf["instr"], (
            f"Table SEQ field MUST use 'Table' identifier. Found: {sf['instr']}"
        )
    print("[OK] SEQ fields use correct identifiers (Figure, Table)")

    # REQUIREMENT 6: STYLEREF fields must reference appropriate heading styles
    for sf in styleref_fields:
        # STYLEREF should reference either "Heading 1" or "Appendix"
        has_valid_ref = ('"Heading 1"' in sf["instr"] or
                        '"Appendix"' in sf["instr"] or
                        "'Heading 1'" in sf["instr"] or
                        "'Appendix'" in sf["instr"])
        assert has_valid_ref, (
            f"STYLEREF field MUST reference 'Heading 1' or 'Appendix'. Found: {sf['instr']}"
        )
        # Should have \s switch for suppress extra text
        assert "\\s" in sf["instr"], (
            f"STYLEREF field MUST have \\s switch. Found: {sf['instr']}"
        )
    print(f"[OK] All {len(styleref_fields)} STYLEREF fields reference correct heading styles with \\s switch")

    print("\n" + "=" * 80)
    print("TEST PASSED - ALL STRICT REQUIREMENTS MET")
    print("=" * 80)
    print(f"[OK] Valid Word caption structure with STYLEREF and SEQ fields")
    print(f"[OK] Proper field switches (\\s 1 for chapter numbering, \\r 1 for initialization)")
    print(f"[OK] Correct identifiers and heading style references")
    print(f"[OK] Tested across {len(fig_captions)} figures and {len(tbl_captions)} tables in multiple sections")


def extract_docx_xml(docx_path: Path, output_dir: Path):
    """Extract XML files from .docx file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(docx_path, "r") as zip_ref:
        zip_ref.extractall(output_dir)

