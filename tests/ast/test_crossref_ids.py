"""Test that cross-reference IDs for figures, tables, and equations are properly exported in the AST."""
import pytest
from paradoc import OneDoc
from paradoc.io.ast.exporter import ASTExporter


def find_blocks_by_type(blocks, block_type):
    """Recursively find all blocks of a given type in the AST."""
    found = []
    for block in blocks:
        if isinstance(block, dict) and block.get('t') == block_type:
            found.append(block)
        # Recursively search in nested blocks (e.g., in Div)
        if isinstance(block, dict) and 'c' in block:
            c = block['c']
            if isinstance(c, list):
                # Check if it contains nested blocks
                for item in c:
                    if isinstance(item, list):
                        found.extend(find_blocks_by_type(item, block_type))
                    elif isinstance(item, dict) and 'blocks' in item:
                        found.extend(find_blocks_by_type(item['blocks'], block_type))
    return found


def find_divs_with_class(blocks, class_name):
    """Find all Div blocks with a specific class."""
    found = []
    for block in blocks:
        if isinstance(block, dict) and block.get('t') == 'Div':
            c = block.get('c', [])
            if len(c) >= 2:
                attrs = c[0]
                if isinstance(attrs, dict):
                    classes = attrs.get('classes', [])
                    if class_name in classes:
                        found.append(block)
                elif isinstance(attrs, list) and len(attrs) >= 2:
                    # Attrs as list: [id, [classes], {attributes}]
                    classes = attrs[1] if len(attrs) > 1 else []
                    if class_name in classes:
                        found.append(block)
            # Recursively search nested blocks
            if len(c) >= 2:
                nested_blocks = c[1] if isinstance(c[1], list) else []
                found.extend(find_divs_with_class(nested_blocks, class_name))
    return found


def extract_id_from_attrs(attrs):
    """Extract ID from Pandoc Attr structure."""
    if isinstance(attrs, dict):
        return attrs.get('id', '')
    elif isinstance(attrs, list) and len(attrs) >= 1:
        # Attrs as list: [id, [classes], {attributes}]
        return attrs[0] if isinstance(attrs[0], str) else ''
    return ''


def test_figure_ids_in_ast(files_dir, tmp_path):
    """Test that figures with IDs are properly exported to AST."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_figure_ids")

    one._prep_compilation()
    one._perform_variable_substitution(False)

    exporter = ASTExporter(one)
    ast = exporter.build_ast()

    blocks = ast.get('blocks', [])

    # Look for Figure blocks (Pandoc 3+) or Div blocks with class 'figure'
    figures = find_blocks_by_type(blocks, 'Figure')
    figure_divs = find_divs_with_class(blocks, 'figure')

    all_figures = figures + figure_divs

    # doc_lorum has multiple figures with IDs like fig:historical-trends
    assert len(all_figures) > 0, "Expected to find figures in doc_lorum"

    # Check that at least one figure has an ID starting with 'fig:'
    figure_ids = []
    for fig in all_figures:
        c = fig.get('c', [])
        if len(c) >= 1:
            attrs = c[0]
            fig_id = extract_id_from_attrs(attrs)
            if fig_id:
                figure_ids.append(fig_id)

    fig_prefixed = [fid for fid in figure_ids if fid.startswith('fig:')]
    assert len(fig_prefixed) > 0, f"Expected figures with 'fig:' IDs, found IDs: {figure_ids}"

    # Verify specific known figure from doc_lorum
    assert 'fig:historical-trends' in figure_ids, f"Expected 'fig:historical-trends' in figure IDs, found: {figure_ids}"


def test_table_ids_in_ast(files_dir, tmp_path):
    """Test that tables with IDs are properly exported to AST."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_table_ids")

    one._prep_compilation()
    one._perform_variable_substitution(False)

    exporter = ASTExporter(one)
    ast = exporter.build_ast()

    blocks = ast.get('blocks', [])

    # Look for Table blocks (may be wrapped in Div by pandoc-crossref)
    tables = find_blocks_by_type(blocks, 'Table')

    # doc_lorum has tables with IDs like tbl:current-metrics
    assert len(tables) > 0, "Expected to find tables in doc_lorum"

    # pandoc-crossref wraps tables in Div blocks with the ID on the Div
    # Find all Div blocks that contain tables
    table_divs = []
    for block in blocks:
        if isinstance(block, dict) and block.get('t') == 'Div':
            c = block.get('c', [])
            if len(c) >= 2:
                # Check if this Div contains a Table
                nested_blocks = c[1] if isinstance(c[1], list) else []
                for nested in nested_blocks:
                    if isinstance(nested, dict) and nested.get('t') == 'Table':
                        table_divs.append(block)
                        break

    # Extract IDs from both direct Table blocks and Div-wrapped tables
    table_ids = []

    # Check direct Table blocks for IDs
    for tbl in tables:
        c = tbl.get('c', [])
        if len(c) >= 1:
            attrs = c[0]
            tbl_id = extract_id_from_attrs(attrs)
            if tbl_id:
                table_ids.append(tbl_id)

    # Check Div wrappers for IDs (this is where pandoc-crossref puts them)
    for div in table_divs:
        c = div.get('c', [])
        if len(c) >= 1:
            attrs = c[0]
            div_id = extract_id_from_attrs(attrs)
            if div_id:
                table_ids.append(div_id)

    tbl_prefixed = [tid for tid in table_ids if tid.startswith('tbl:')]
    assert len(tbl_prefixed) > 0, f"Expected tables with 'tbl:' IDs, found IDs: {table_ids}"

    # Verify specific known table from doc_lorum
    assert 'tbl:current-metrics' in table_ids, f"Expected 'tbl:current-metrics' in table IDs, found: {table_ids}"


def test_equation_ids_in_ast(files_dir, tmp_path):
    """Test that equations with IDs are properly exported to AST."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_equation_ids")

    one._prep_compilation()
    one._perform_variable_substitution(False)

    exporter = ASTExporter(one)
    ast = exporter.build_ast()

    blocks = ast.get('blocks', [])

    # Equations are typically in Span or Div elements with specific classes
    # Look for Span elements that might contain equation IDs
    def find_spans_with_id_prefix(blocks, prefix):
        found_ids = []

        def search_inlines(inlines):
            for inline in inlines:
                if isinstance(inline, dict):
                    if inline.get('t') == 'Span':
                        c = inline.get('c', [])
                        if len(c) >= 1:
                            attrs = c[0]
                            span_id = extract_id_from_attrs(attrs)
                            if span_id and span_id.startswith(prefix):
                                found_ids.append(span_id)
                    # Check nested inlines
                    if 'c' in inline and isinstance(inline['c'], list):
                        for item in inline['c']:
                            if isinstance(item, list):
                                search_inlines(item)

        def search_blocks(blks):
            for block in blks:
                if isinstance(block, dict):
                    if block.get('t') in ['Para', 'Plain']:
                        c = block.get('c', [])
                        if isinstance(c, list):
                            search_inlines(c)
                    elif block.get('t') == 'Div':
                        c = block.get('c', [])
                        if len(c) >= 1:
                            attrs = c[0]
                            div_id = extract_id_from_attrs(attrs)
                            if div_id and div_id.startswith(prefix):
                                found_ids.append(div_id)
                        if len(c) >= 2 and isinstance(c[1], list):
                            search_blocks(c[1])

        search_blocks(blocks)
        return found_ids

    equation_ids = find_spans_with_id_prefix(blocks, 'eq:')

    # doc_lorum has equations with IDs like eq:energy, eq:diffusion
    assert len(equation_ids) > 0, f"Expected to find equations with 'eq:' IDs in doc_lorum"

    # Check for known equations
    expected_eqs = ['eq:energy', 'eq:diffusion']
    for eq_id in expected_eqs:
        assert eq_id in equation_ids, f"Expected '{eq_id}' in equation IDs, found: {equation_ids}"
