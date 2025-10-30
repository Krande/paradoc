from paradoc import OneDoc
from paradoc.io.ast.exporter import ASTExporter


def test_doc1_subsection_in_manifest(files_dir, tmp_path):
    """
    Test that subsections (H2, H3, etc.) are included in the manifest sections array.

    doc1/00-main/main.md contains:
    - # A title (H1)
    - ## A subtitle (H2) <-- This should appear in the manifest
    - # Is this an appendix (H1)

    The frontend expects ALL headers to be in the manifest.sections array
    so it can build a complete outline/TOC with proper nesting.
    """
    source = files_dir / "doc1"
    one = OneDoc(source, work_dir=tmp_path / "test_subsections")

    # Prepare compilation artifacts
    exporter = one.get_ast()
    ast = exporter.build_ast()
    manifest, sections = exporter.slice_sections(ast)

    # Verify manifest shape
    assert isinstance(manifest, dict)
    assert "docId" in manifest
    assert "sections" in manifest
    assert isinstance(manifest["sections"], list)

    # Expected sections based on doc1 structure:
    # 1. H1: "A title" (level=1)
    # 2. H2: "A subtitle" (level=2) <-- THIS IS THE KEY TEST
    # 3. H1: "Is this an appendix" (level=1)
    section_metas = manifest["sections"]

    # Print for debugging
    print(f"\nFound {len(section_metas)} sections in manifest:")
    for i, sec in enumerate(section_metas):
        print(f"  {i}: level={sec.get('level')}, title='{sec.get('title')}', id={sec.get('id')}")

    # Assert we have at least 3 sections (2 H1s + 1 H2)
    assert len(section_metas) >= 3, f"Expected at least 3 sections (including subsections), got {len(section_metas)}"

    # Find the subsection "A subtitle"
    subtitle_sections = [s for s in section_metas if "subtitle" in s.get("title", "").lower()]
    assert (
        len(subtitle_sections) == 1
    ), f"Expected to find exactly one section with 'subtitle' in title, got {len(subtitle_sections)}"

    subtitle_section = subtitle_sections[0]

    # Verify the subsection metadata matches frontend expectations
    assert subtitle_section["level"] == 2, f"Expected level 2 for '## A subtitle', got {subtitle_section['level']}"
    assert subtitle_section["title"] == "A subtitle", f"Expected title 'A subtitle', got '{subtitle_section['title']}'"
    assert "id" in subtitle_section
    assert "index" in subtitle_section

    # Verify the subsection has proper ordering (should come after "A title")
    title_idx = next((i for i, s in enumerate(section_metas) if "A title" in s.get("title", "")), -1)
    subtitle_idx = next((i for i, s in enumerate(section_metas) if "subtitle" in s.get("title", "").lower()), -1)

    assert title_idx >= 0, "Could not find 'A title' section"
    assert subtitle_idx > title_idx, "Subsection 'A subtitle' should come after 'A title' in manifest order"

    # Verify section indices are sequential
    for i, sec in enumerate(section_metas):
        assert sec["index"] == i, f"Section {i} has wrong index: {sec['index']}"


def test_all_header_levels_exported(files_dir, tmp_path):
    """
    Test that all header levels (H1-H6) are exported to the manifest.
    This ensures the frontend can build a complete nested outline.
    """
    source = files_dir / "doc1"
    one = OneDoc(source, work_dir=tmp_path / "test_all_levels")

    exporter = one.get_ast()
    ast = exporter.build_ast()

    # Manually inspect the AST blocks to find all headers
    blocks = ast.get("blocks", [])
    headers_in_ast = []

    for blk in blocks:
        if isinstance(blk, dict) and blk.get("t") == "Header":
            content = blk.get("c", [])
            if isinstance(content, list) and len(content) >= 3:
                level = int(content[0])
                attrs = content[1]
                inlines = content[2]
                title = exporter._header_text(inlines)
                header_id = attrs[0] if isinstance(attrs, list) and attrs else ""
                headers_in_ast.append({"level": level, "title": title, "id": header_id})

    print("\nHeaders found in AST blocks:")
    for h in headers_in_ast:
        print(f"  H{h['level']}: '{h['title']}' (id={h['id']})")

    # Now check the manifest
    manifest, sections = exporter.slice_sections(ast)
    section_metas = manifest["sections"]

    print("\nSections in manifest:")
    for s in section_metas:
        print(f"  level={s['level']}: '{s['title']}' (id={s['id']})")

    # Assert: Every header in the AST should appear in the manifest
    for h in headers_in_ast:
        matching = [s for s in section_metas if s["title"] == h["title"] and s["level"] == h["level"]]
        assert len(matching) == 1, f"Header '{h['title']}' (level {h['level']}) not found in manifest sections"
