"""Test the DocumentStructureExtractor on the doc_lorum example document."""

from paradoc import OneDoc


def test_document_structure_basic(files_dir, tmp_path):
    """Test basic document structure extraction on doc_lorum document."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_doc_structure")

    # Get document structure
    structure = one.get_document_structure()

    # Validate the extracted data
    stats = structure.validate()

    # doc_lorum should have multiple sections
    assert stats["total_sections"] > 0, f"Expected sections, found {stats['total_sections']}"
    assert stats["root_sections"] > 0, f"Expected root sections, found {stats['root_sections']}"

    # Should have figures, tables, and equations
    assert stats["total_figures"] == 16, f"Expected 16 figures, found {stats['total_figures']}"
    assert stats["total_tables"] == 11, f"Expected 11 tables, found {stats['total_tables']}"
    assert stats["total_equations"] == 2, f"Expected 2 equations, found {stats['total_equations']}"

    # Should have cross-references
    assert (
        stats["total_cross_references"] == 29
    ), f"Expected 29 cross-references, found {stats['total_cross_references']}"

    # Should have both main and appendix sections
    assert stats["main_sections"] > 0, "Expected main sections"
    assert stats["appendix_sections"] > 0, "Expected appendix sections"

    print("\n[OK] Basic structure test passed!")
    print(f"  Total sections: {stats['total_sections']}")
    print(f"  Root sections: {stats['root_sections']}")
    print(f"  Figures: {stats['total_figures']}")
    print(f"  Tables: {stats['total_tables']}")
    print(f"  Equations: {stats['total_equations']}")
    print(f"  Cross-references: {stats['total_cross_references']}")


def test_section_hierarchy(files_dir, tmp_path):
    """Test section hierarchy and navigation."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_section_hierarchy")

    # Get document structure
    structure = one.get_document_structure()

    # Test root sections
    assert len(structure.root_sections) > 0, "Expected root sections"

    # Test hierarchy
    for root in structure.root_sections:
        assert root.parent is None, f"Root section {root.title} should have no parent"
        assert root.level == 1, f"Root section {root.title} should be level 1"

        # Test children
        for child in root.children:
            assert child.parent == root, f"Child {child.title} should have parent {root.title}"
            assert child.level > root.level, f"Child {child.title} should have higher level than parent"

    # Test sibling navigation
    if len(structure.root_sections) > 1:
        first_root = structure.root_sections[0]
        second_root = structure.root_sections[1]

        assert first_root.next_sibling == second_root, "First root should link to second as next sibling"
        assert second_root.previous_sibling == first_root, "Second root should link to first as previous sibling"

    # Test section numbering
    for section in structure.sections:
        if not section.is_appendix:
            # Main sections should have numeric numbering: 1, 1.1, 1.2, 2, etc.
            assert section.number, f"Section {section.title} should have a number"
            # Check that number contains only digits and dots
            assert all(
                c.isdigit() or c == "." for c in section.number
            ), f"Main section number {section.number} should contain only digits and dots"
        else:
            # Appendix sections should have letter numbering: A, A.1, B, etc.
            assert section.number, f"Appendix section {section.title} should have a number"
            # First character should be a letter
            assert section.number[0].isalpha(), f"Appendix section number {section.number} should start with a letter"

    print("\n[OK] Section hierarchy test passed!")
    print(f"  Root sections: {len(structure.root_sections)}")
    for root in structure.root_sections:
        print(f"  Section {root.number}: {root.title} ({len(root.children)} children)")


def test_section_content(files_dir, tmp_path):
    """Test that sections contain paragraphs, figures, tables, and equations."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_section_content")

    # Get document structure
    structure = one.get_document_structure()

    # Count content across all sections
    total_paragraphs = sum(len(s.paragraphs) for s in structure.sections)
    total_figures_in_sections = sum(len(s.figures) for s in structure.sections)
    total_tables_in_sections = sum(len(s.tables) for s in structure.sections)
    total_equations_in_sections = sum(len(s.equations) for s in structure.sections)
    total_crossrefs_in_sections = sum(len(s.cross_references) for s in structure.sections)

    # Should have paragraphs
    assert total_paragraphs > 0, "Expected paragraphs in sections"

    # Figures, tables, and equations should match the totals
    assert total_figures_in_sections == 16, f"Expected 16 figures in sections, found {total_figures_in_sections}"
    assert total_tables_in_sections == 11, f"Expected 11 tables in sections, found {total_tables_in_sections}"
    assert total_equations_in_sections == 2, f"Expected 2 equations in sections, found {total_equations_in_sections}"

    # Cross-references should match the total
    assert (
        total_crossrefs_in_sections == 29
    ), f"Expected 29 cross-references in sections, found {total_crossrefs_in_sections}"

    # Find a section with content
    content_section = None
    for section in structure.sections:
        if section.paragraphs or section.figures or section.tables or section.equations:
            content_section = section
            break

    assert content_section is not None, "Expected at least one section with content"

    print("\n[OK] Section content test passed!")
    print(f"  Total paragraphs: {total_paragraphs}")
    print(f"  Figures in sections: {total_figures_in_sections}")
    print(f"  Tables in sections: {total_tables_in_sections}")
    print(f"  Equations in sections: {total_equations_in_sections}")
    print(f"  Cross-references in sections: {total_crossrefs_in_sections}")


def test_section_navigation_methods(files_dir, tmp_path):
    """Test section navigation helper methods."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_section_navigation")

    # Get document structure
    structure = one.get_document_structure()

    # Test get_all_descendants
    if structure.root_sections:
        root = structure.root_sections[0]
        descendants = root.get_all_descendants()

        # All descendants should be children or grandchildren etc.
        for descendant in descendants:
            path = descendant.get_path()
            assert root in path, "Root should be in descendant's path"

    # Test get_path
    if len(structure.sections) > 1:
        # Find a non-root section
        non_root = None
        for section in structure.sections:
            if section.parent is not None:
                non_root = section
                break

        if non_root:
            path = non_root.get_path()
            assert len(path) > 0, "Path should not be empty"
            assert path[-1] == non_root, "Last element in path should be the section itself"
            if non_root.parent:
                assert non_root.parent in path, "Parent should be in path"

    # Test get_depth
    for section in structure.sections:
        depth = section.get_depth()
        if section.parent is None:
            assert depth == 0, f"Root section {section.title} should have depth 0"
        else:
            parent_depth = section.parent.get_depth()
            assert depth == parent_depth + 1, f"Section {section.title} depth should be parent depth + 1"

    print("\n[OK] Section navigation methods test passed!")


def test_cross_references_in_sections(files_dir, tmp_path):
    """Test that cross-references are properly assigned to sections."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_crossrefs_in_sections")

    # Get document structure
    structure = one.get_document_structure()

    # Find sections with cross-references
    sections_with_crossrefs = [s for s in structure.sections if s.cross_references]

    assert len(sections_with_crossrefs) > 0, "Expected sections with cross-references"

    # Check that cross-references have valid target types
    for section in sections_with_crossrefs:
        for crossref in section.cross_references:
            assert crossref.target_type in [
                "fig",
                "tbl",
                "eq",
            ], f"Invalid cross-reference target type: {crossref.target_type}"
            assert crossref.target_id, "Cross-reference should have a target ID"

    # Check that cross-reference targets exist in the structure
    dangling_refs = []
    for crossref in structure.cross_references:
        target_id = crossref.target_id
        found = False
        if target_id in structure.figures:
            found = True
        elif target_id in structure.tables:
            found = True
        elif target_id in structure.equations:
            found = True

        if not found:
            dangling_refs.append(target_id)

    assert len(dangling_refs) == 0, f"Found dangling cross-references: {dangling_refs}"

    print("\n[OK] Cross-references in sections test passed!")
    print(f"  Sections with cross-references: {len(sections_with_crossrefs)}")


def test_structure_lookup_methods(files_dir, tmp_path):
    """Test DocumentStructure lookup methods."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_structure_lookup")

    # Get document structure
    structure = one.get_document_structure()

    # Test get_section_by_id
    if structure.sections:
        first_section = structure.sections[0]
        found = structure.get_section_by_id(first_section.id)
        assert found == first_section, "Should find section by ID"

    # Test get_section_by_number
    if structure.sections:
        first_section = structure.sections[0]
        found = structure.get_section_by_number(first_section.number)
        assert found == first_section, "Should find section by number"

    # Test get_sections_by_level
    level_1_sections = structure.get_sections_by_level(1)
    assert len(level_1_sections) > 0, "Expected level 1 sections"
    for section in level_1_sections:
        assert section.level == 1, "All returned sections should be level 1"

    # Test get_appendix_sections
    appendix_sections = structure.get_appendix_sections()
    assert len(appendix_sections) > 0, "Expected appendix sections"
    for section in appendix_sections:
        assert section.is_appendix, "All returned sections should be appendix sections"

    # Test get_main_sections
    main_sections = structure.get_main_sections()
    assert len(main_sections) > 0, "Expected main sections"
    for section in main_sections:
        assert not section.is_appendix, "All returned sections should be main sections"

    print("\n[OK] Structure lookup methods test passed!")
    print(f"  Level 1 sections: {len(level_1_sections)}")
    print(f"  Appendix sections: {len(appendix_sections)}")
    print(f"  Main sections: {len(main_sections)}")


def test_specific_figures_tables_equations(files_dir, tmp_path):
    """Test that specific known figures, tables, and equations are found."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_specific_items")

    # Get document structure
    structure = one.get_document_structure()

    # Test specific figures
    assert "fig:historical_trends" in structure.figures, "Expected 'historical_trends' figure"
    assert "fig:primary_results" in structure.figures, "Expected 'primary_results' figure"
    assert "fig:qc-workflow" in structure.figures, "Expected 'qc-workflow' figure (from markdown)"

    # Test specific tables
    assert "tbl:current_metrics" in structure.tables, "Expected 'current_metrics' table"
    assert "tbl:validation-criteria" in structure.tables, "Expected 'validation-criteria' table (from markdown)"

    # Test specific equations
    assert "eq:energy" in structure.equations, "Expected 'energy' equation"
    assert "eq:diffusion" in structure.equations, "Expected 'diffusion' equation"

    # Test equation content
    energy_eq = structure.equations.get("eq:energy")
    if energy_eq:
        assert energy_eq.latex is not None, "Expected energy equation to have LaTeX content"
        assert (
            "mc^2" in energy_eq.latex or "E" in energy_eq.latex
        ), f"Expected energy equation LaTeX, got: {energy_eq.latex}"

    print("\n[OK] Specific items test passed!")
    print("  Found specific figures, tables, and equations")


def test_section_source_tracking(files_dir, tmp_path):
    """Test that sections track their source files."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_source_tracking")

    # Get document structure
    structure = one.get_document_structure()

    # Check that sections have source file information
    sections_with_source = [s for s in structure.sections if s.source_file]

    # Most sections should have source file information
    # (some might not if they're at the very beginning before any marker)
    assert len(sections_with_source) > 0, "Expected sections with source file information"

    # Check that figures, tables, and equations have source file info
    figures_with_source = [f for f in structure.figures.values() if f.source_file]
    tables_with_source = [t for t in structure.tables.values() if t.source_file]
    equations_with_source = [e for e in structure.equations.values() if e.source_file]

    assert len(figures_with_source) > 0, "Expected figures with source file information"
    assert len(tables_with_source) > 0, "Expected tables with source file information"

    print("\n[OK] Source tracking test passed!")
    print(f"  Sections with source: {len(sections_with_source)}/{len(structure.sections)}")
    print(f"  Figures with source: {len(figures_with_source)}/{len(structure.figures)}")
    print(f"  Tables with source: {len(tables_with_source)}/{len(structure.tables)}")
    print(f"  Equations with source: {len(equations_with_source)}/{len(structure.equations)}")
