"""Test that equations are properly exported in the AST JSON format for frontend rendering."""

import json
import pytest
from paradoc import OneDoc
from paradoc.io.ast.exporter import ASTExporter


@pytest.fixture(scope="function")
def doc_with_equations(files_dir, tmp_path):
    """Create a test document with equations."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_equation_ast")
    one._prep_compilation()
    one._perform_variable_substitution(False)
    return one


def test_equation_ast_structure(doc_with_equations):
    """Test that equations are exported as Math elements in the AST with proper structure."""
    exporter = ASTExporter(doc_with_equations)
    ast = exporter.build_ast()

    blocks = ast.get('blocks', [])
    assert len(blocks) > 0, "AST should contain blocks"

    # Find all Math elements in the AST
    math_elements = []

    def find_math_in_inlines(inlines):
        """Recursively find Math elements in inline content."""
        if not isinstance(inlines, list):
            return

        for inline in inlines:
            if isinstance(inline, dict):
                if inline.get('t') == 'Math':
                    math_elements.append(inline)
                # Recursively check nested structures
                if 'c' in inline and isinstance(inline['c'], list):
                    for item in inline['c']:
                        if isinstance(item, list):
                            find_math_in_inlines(item)

    def find_math_in_blocks(blks):
        """Recursively find Math elements in blocks."""
        for block in blks:
            if isinstance(block, dict):
                block_type = block.get('t')

                # Check Para and Plain blocks for inline math
                if block_type in ['Para', 'Plain']:
                    content = block.get('c', [])
                    if isinstance(content, list):
                        find_math_in_inlines(content)

                # Check Div blocks recursively
                elif block_type == 'Div':
                    content = block.get('c', [])
                    if len(content) >= 2 and isinstance(content[1], list):
                        find_math_in_blocks(content[1])

                # Check other block types that might contain blocks
                elif block_type in ['BlockQuote', 'BulletList', 'OrderedList']:
                    content = block.get('c', [])
                    if isinstance(content, list):
                        find_math_in_blocks(content)

    find_math_in_blocks(blocks)

    # doc_lorum has equations like E=mc^2 and diffusion equation
    assert len(math_elements) > 0, "Expected to find Math elements in doc_lorum"

    # Verify structure of Math elements
    for math_elem in math_elements:
        assert math_elem.get('t') == 'Math', f"Expected type 'Math', got {math_elem.get('t')}"

        content = math_elem.get('c')
        assert content is not None, "Math element should have content"
        assert isinstance(content, list), "Math content should be a list"
        assert len(content) == 2, f"Math content should have 2 elements [type, latex], got {len(content)}"

        math_type = content[0]
        latex_str = content[1]

        # Math type should be a dict with 't' key
        assert isinstance(math_type, dict), f"Math type should be dict, got {type(math_type)}"
        assert 't' in math_type, "Math type should have 't' key"
        assert math_type['t'] in ['InlineMath', 'DisplayMath'], \
            f"Math type should be InlineMath or DisplayMath, got {math_type['t']}"

        # LaTeX string should be a string
        assert isinstance(latex_str, str), f"LaTeX should be string, got {type(latex_str)}"
        assert len(latex_str) > 0, "LaTeX string should not be empty"

    print(f"\n✓ Found {len(math_elements)} Math elements in AST")
    for i, math_elem in enumerate(math_elements[:5]):  # Print first 5
        math_type = math_elem['c'][0]['t']
        latex = math_elem['c'][1][:50]  # First 50 chars
        print(f"  Math {i+1}: {math_type} - {latex}")


def test_equation_with_crossref_id(doc_with_equations):
    """Test that equations with crossref IDs are properly structured in AST."""
    exporter = ASTExporter(doc_with_equations)
    ast = exporter.build_ast()

    blocks = ast.get('blocks', [])

    # Find equations with IDs (they should be in Span elements with eq: prefix)
    equation_spans = []

    def find_equation_spans(inlines):
        """Find Span elements that contain equations with IDs."""
        if not isinstance(inlines, list):
            return

        for inline in inlines:
            if isinstance(inline, dict):
                if inline.get('t') == 'Span':
                    content = inline.get('c', [])
                    if len(content) >= 1:
                        attrs = content[0]
                        # Extract ID from attrs
                        span_id = None
                        if isinstance(attrs, list) and len(attrs) >= 1:
                            span_id = attrs[0] if isinstance(attrs[0], str) else None
                        elif isinstance(attrs, dict):
                            span_id = attrs.get('id')

                        if span_id and span_id.startswith('eq:'):
                            equation_spans.append({
                                'id': span_id,
                                'span': inline
                            })

                # Check nested structures
                if 'c' in inline and isinstance(inline['c'], list):
                    for item in inline['c']:
                        if isinstance(item, list):
                            find_equation_spans(item)

    def search_blocks(blks):
        """Search blocks for equation spans."""
        for block in blks:
            if isinstance(block, dict):
                if block.get('t') in ['Para', 'Plain']:
                    content = block.get('c', [])
                    if isinstance(content, list):
                        find_equation_spans(content)
                elif block.get('t') == 'Div':
                    content = block.get('c', [])
                    if len(content) >= 2 and isinstance(content[1], list):
                        search_blocks(content[1])

    search_blocks(blocks)

    # doc_lorum has equations with IDs like eq:energy, eq:diffusion
    assert len(equation_spans) >= 2, \
        f"Expected at least 2 equations with IDs in doc_lorum, found {len(equation_spans)}"

    # Check for known equations
    equation_ids = [eq['id'] for eq in equation_spans]
    assert 'eq:energy' in equation_ids, \
        f"Expected 'eq:energy' in equation IDs, found: {equation_ids}"
    assert 'eq:diffusion' in equation_ids, \
        f"Expected 'eq:diffusion' in equation IDs, found: {equation_ids}"

    print(f"\n✓ Found {len(equation_spans)} equations with crossref IDs:")
    for eq in equation_spans:
        print(f"  - {eq['id']}")


def test_display_vs_inline_math(doc_with_equations):
    """Test that display math ($$) and inline math ($) are properly distinguished."""
    exporter = ASTExporter(doc_with_equations)
    ast = exporter.build_ast()

    blocks = ast.get('blocks', [])

    display_math = []
    inline_math = []

    def classify_math(inlines):
        """Classify math elements as display or inline."""
        if not isinstance(inlines, list):
            return

        for inline in inlines:
            if isinstance(inline, dict):
                if inline.get('t') == 'Math':
                    content = inline.get('c', [])
                    if len(content) >= 2:
                        math_type = content[0]
                        latex = content[1]
                        if isinstance(math_type, dict):
                            if math_type.get('t') == 'DisplayMath':
                                display_math.append(latex)
                            elif math_type.get('t') == 'InlineMath':
                                inline_math.append(latex)

                # Check nested structures
                if 'c' in inline and isinstance(inline['c'], list):
                    for item in inline['c']:
                        if isinstance(item, list):
                            classify_math(item)

    def search_blocks(blks):
        """Search blocks for math elements."""
        for block in blks:
            if isinstance(block, dict):
                if block.get('t') in ['Para', 'Plain']:
                    content = block.get('c', [])
                    if isinstance(content, list):
                        classify_math(content)
                elif block.get('t') == 'Div':
                    content = block.get('c', [])
                    if len(content) >= 2 and isinstance(content[1], list):
                        search_blocks(content[1])

    search_blocks(blocks)

    # doc_lorum should have both display and potentially inline math
    assert len(display_math) > 0, "Expected to find display math ($$) in doc_lorum"

    print(f"\n✓ Found {len(display_math)} display math and {len(inline_math)} inline math elements")
    if display_math:
        print(f"  Display math example: {display_math[0][:50]}")
    if inline_math:
        print(f"  Inline math example: {inline_math[0][:50]}")

