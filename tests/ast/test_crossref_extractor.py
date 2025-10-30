"""Test the CrossRefExtractor on the doc_lorum example document."""

import pytest

from paradoc import OneDoc
from paradoc.io.ast.crossref_extractor import CrossRefExtractor


def test_crossref_extractor_doc_lorum(files_dir, tmp_path):
    """Test CrossRefExtractor on doc_lorum document.

    This test verifies that the extractor correctly identifies all figures, tables,
    equations and their cross-references in the doc_lorum example document.
    """
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_crossref_extractor")

    # Build the AST
    exporter = one.get_ast()
    ast = exporter.build_ast()

    # Extract cross-reference data
    extractor = CrossRefExtractor(ast)
    data = extractor.extract()

    # Validate the extracted data
    stats = data.validate()

    # doc_lorum has 15 figures (from populate_database.py)
    # Figures: historical_trends, data_framework, statistical_workflow, primary_results,
    # comparative_analysis, error_analysis, theory_comparison, system_architecture,
    # performance_benchmarks, time_series, computational_results, correlation_matrix,
    # distributions, surface_plot, box_plots
    # Plus one additional figure defined directly in markdown: qc-workflow
    assert stats['figures'] == 16, f"Expected 16 figures, found {stats['figures']}"

    # doc_lorum has 10 tables (from populate_database.py)
    # Tables: current_metrics, measurement_specs, validation_results, quantitative_metrics,
    # comparison_data, implementation_guide, component_specs, raw_data_set1, raw_data_set2,
    # algorithm_performance
    # Plus one additional table defined directly in markdown: validation-criteria
    assert stats['tables'] == 11, f"Expected 11 tables, found {stats['tables']}"

    # Note: Equations (eq:energy, eq:diffusion) are cited in the document but not currently
    # extracted as targets by the CrossRefExtractor. This is a known limitation.
    # The extractor may need updates to handle display math blocks with {#eq:id} syntax.
    # For now, we just verify that the equation citations exist.

    # Cross-reference citations:
    # From grep search: 17 figure refs, 10 table refs, 2 equation refs
    # Note: some figures are referenced multiple times
    # Figure refs: historical_trends (1), data_framework (1), statistical_workflow (1),
    # primary_results (2), comparative_analysis (1), error_analysis (1), theory_comparison (1),
    # system_architecture (1), performance_benchmarks (1), time_series (1), computational_results (1),
    # correlation_matrix (1), distributions (1), surface_plot (1), box_plots (1), qc-workflow (1)
    # Total figure citations: 17

    # Table refs: current_metrics (1), measurement_specs (1), validation_results (1),
    # quantitative_metrics (1), comparison_data (1), implementation_guide (1),
    # component_specs (1), raw_data_set1 (1), raw_data_set2 (1), algorithm_performance (1)
    # Total table citations: 10

    # Equation refs: energy (1), diffusion (1) - now properly extracted as Span targets
    # Total equation citations: 2

    total_expected_citations = 17 + 10 + 2  # 29 total
    assert stats['total_citations'] == total_expected_citations, \
        f"Expected {total_expected_citations} citations, found {stats['total_citations']}"

    # All citations should now have corresponding targets
    assert stats['dangling_citations'] == 0, \
        f"Expected 0 dangling citations, found {stats['dangling_citations']}: {data.dangling_citations}"


    # Verify specific figures exist
    assert 'historical_trends' in data.figures, "Expected 'historical_trends' figure"
    assert 'primary_results' in data.figures, "Expected 'primary_results' figure"
    assert 'qc-workflow' in data.figures, "Expected 'qc-workflow' figure (from markdown)"

    # Verify specific tables exist
    assert 'current_metrics' in data.tables, "Expected 'current_metrics' table"
    assert 'validation-criteria' in data.tables, "Expected 'validation-criteria' table (from markdown)"

    # Verify specific equations exist (now properly extracted from Span elements)
    assert 'energy' in data.equations, "Expected 'energy' equation"
    assert 'diffusion' in data.equations, "Expected 'diffusion' equation"

    # Verify equation content was extracted
    energy_eq = data.equations.get('energy')
    if energy_eq:
        assert energy_eq.caption_text is not None, "Expected energy equation to have LaTeX content"
        assert 'mc^2' in energy_eq.caption_text or 'E' in energy_eq.caption_text, \
            f"Expected energy equation LaTeX, got: {energy_eq.caption_text}"

    # Verify that primary_results is referenced twice
    primary_results_citations = data.get_citations_for_target('fig:primary_results')
    assert len(primary_results_citations) == 2, \
        f"Expected 2 citations for 'fig:primary_results', found {len(primary_results_citations)}"
    print(f"\n✓ CrossRefExtractor test passed!")
    print(f"  Figures: {stats['figures']}")
    print(f"  Tables: {stats['tables']}")
    print(f"  Equations: {stats['equations']}")
    print(f"  Total citations: {stats['total_citations']}")
    print(f"  Dangling citations: {stats['dangling_citations']}")


def test_crossref_extractor_detailed_analysis(files_dir, tmp_path):
    """Test detailed cross-reference analysis on doc_lorum.

    This test verifies citation counts and unreferenced targets.
    """
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_crossref_detailed")

    # Build the AST
    exporter = one.get_ast()
    ast = exporter.build_ast()

    # Extract cross-reference data
    extractor = CrossRefExtractor(ast)
    data = extractor.extract()

    # Validate the extracted data
    stats = data.validate()

    # Check citation counts for specific targets
    citation_counts = stats['citation_counts']

    # primary_results should be cited twice
    assert citation_counts.get('fig:primary_results', 0) == 2, \
        f"Expected 2 citations for fig:primary_results, found {citation_counts.get('fig:primary_results', 0)}"

    # raw_data_set1 and raw_data_set2 are referenced in the same line
    # so they should each have 1 citation
    assert citation_counts.get('tbl:raw_data_set1', 0) == 1, \
        f"Expected 1 citation for tbl:raw_data_set1, found {citation_counts.get('tbl:raw_data_set1', 0)}"
    assert citation_counts.get('tbl:raw_data_set2', 0) == 1, \
        f"Expected 1 citation for tbl:raw_data_set2, found {citation_counts.get('tbl:raw_data_set2', 0)}"

    # energy and diffusion equations are referenced in the same line
    assert citation_counts.get('eq:energy', 0) == 1, \
        f"Expected 1 citation for eq:energy, found {citation_counts.get('eq:energy', 0)}"
    assert citation_counts.get('eq:diffusion', 0) == 1, \
        f"Expected 1 citation for eq:diffusion, found {citation_counts.get('eq:diffusion', 0)}"

    # Check for unreferenced targets (should be none if document is well-written)
    unreferenced = stats['unreferenced_targets']
    print(f"\n✓ Detailed analysis passed!")
    print(f"  Citation counts: {len(citation_counts)} unique targets cited")
    print(f"  Unreferenced targets: {len(unreferenced)}")
    if unreferenced:
        print(f"  Unreferenced: {unreferenced}")

    # Note: Some targets might be unreferenced if they're defined but not cited
    # This is not necessarily an error, but good to know
    assert isinstance(unreferenced, list), "unreferenced_targets should be a list"


def test_crossref_extractor_caption_extraction(files_dir, tmp_path):
    """Test that captions are properly extracted for figures and tables.

    Note: Currently captions from database-generated figures/tables are not in the AST
    (they're stored in the database), so this test documents that limitation.
    Captions from markdown-defined figures/tables should be extracted.
    """
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_crossref_captions")

    # Build the AST
    exporter = one.get_ast()
    ast = exporter.build_ast()

    # Extract cross-reference data
    extractor = CrossRefExtractor(ast)
    data = extractor.extract()

    # Count targets with captions
    targets_with_captions = [t for t in data.targets.values() if t.caption_text]
    targets_without_captions = [t for t in data.targets.values() if not t.caption_text]

    print(f"\n✓ Caption extraction test passed!")
    print(f"  Targets with captions: {len(targets_with_captions)}/{len(data.targets)}")
    print(f"  Targets without captions: {len(targets_without_captions)}/{len(data.targets)}")

    # Currently, database-generated figures/tables don't have captions in the AST
    # This is a limitation - captions are in the database, not the markdown/AST
    # For now, we just document this behavior

    # The qc-workflow figure is defined in markdown with an image, it might have caption info
    qc_workflow = data.figures.get('qc-workflow')
    if qc_workflow:
        print(f"  qc-workflow caption: {qc_workflow.caption_text}")

    # validation-criteria table is defined in markdown, it might have a caption
    validation_criteria = data.tables.get('validation-criteria')
    if validation_criteria:
        print(f"  validation-criteria caption: {validation_criteria.caption_text}")

