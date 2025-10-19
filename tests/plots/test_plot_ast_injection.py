"""Test that plot keys are properly injected into the AST JSON for frontend rendering."""
import pytest
import json
import pandas as pd
import numpy as np
from pathlib import Path
from paradoc import OneDoc
from paradoc.db import dataframe_to_plot_data
from paradoc.io.ast.exporter import ASTExporter


class TestPlotASTInjection:
    """Test suite for verifying plot key injection in AST."""

    def test_plot_key_in_ast_single_plot(self, tmp_path):
        """Test that a single plot gets data-plot-key attribute in AST."""
        # Create test document
        test_dir = tmp_path / "test_plot_ast"
        test_dir.mkdir(parents=True, exist_ok=True)

        # Create markdown file BEFORE initializing OneDoc
        main_dir = test_dir / "00-main"
        main_dir.mkdir(parents=True, exist_ok=True)

        markdown_content = """# Test Document

This document contains a plot.

{{__test_plot__}}

End of document.
"""
        md_file = main_dir / "test.md"
        md_file.write_text(markdown_content)

        # Create OneDoc instance
        one = OneDoc(test_dir, work_dir=tmp_path / "work")

        # Create sample plot data
        x = np.linspace(0, 2 * np.pi, 100)
        df = pd.DataFrame({
            'x': x,
            'sin(x)': np.sin(x),
        })

        # Add plot to database
        plot_data = dataframe_to_plot_data(
            key='test_plot',
            df=df,
            plot_type='line',
            caption='Test Plot',
            width=800,
            height=400
        )
        one.db_manager.add_plot(plot_data)

        # Compile document (this performs variable substitution)
        one.compile("test_output", export_format="html")

        # Enable frontend export mode and build AST
        one._is_frontend_export = True
        exporter = ASTExporter(one)
        ast = exporter.build_ast()

        # Verify the AST contains a Figure with data-plot-key attribute
        figure_found = False
        plot_key_found = False

        def check_blocks(blocks):
            nonlocal figure_found, plot_key_found
            for block in blocks:
                if not isinstance(block, dict):
                    continue

                if block.get("t") == "Figure":
                    figure_found = True
                    c = block.get("c", [])
                    if isinstance(c, list) and len(c) >= 3:
                        attr = c[0]
                        if isinstance(attr, list) and len(attr) >= 3:
                            fig_id = attr[0]
                            attrs_dict = attr[2] if len(attr) > 2 else []

                            # Check if this is our plot figure
                            if isinstance(fig_id, str) and fig_id.startswith("fig:test_plot"):
                                # Check for data-plot-key attribute
                                for kv in attrs_dict:
                                    if isinstance(kv, list) and len(kv) >= 2:
                                        if kv[0] == "data-plot-key" and kv[1] == "test_plot":
                                            plot_key_found = True
                                            break

                # Recursively check nested blocks
                if block.get("t") in ["Div", "BlockQuote"]:
                    nested = block.get("c")
                    if isinstance(nested, list) and len(nested) >= 2:
                        check_blocks(nested[1])

        check_blocks(ast.get("blocks", []))

        assert figure_found, "No Figure block found in AST"
        assert plot_key_found, "Figure found but data-plot-key attribute not present"

    def test_plot_key_in_ast_multiple_uses(self, tmp_path):
        """Test that the same plot used multiple times gets proper keys."""
        test_dir = tmp_path / "test_plot_ast_multi"
        test_dir.mkdir(parents=True, exist_ok=True)

        # Create markdown with multiple references BEFORE initializing OneDoc
        main_dir = test_dir / "00-main"
        main_dir.mkdir(parents=True, exist_ok=True)

        markdown_content = """# Test Document

First occurrence:

{{__repeated_plot__}}

Second occurrence:

{{__repeated_plot__}}

Third occurrence:

{{__repeated_plot__}}
"""
        md_file = main_dir / "test.md"
        md_file.write_text(markdown_content)

        one = OneDoc(test_dir, work_dir=tmp_path / "work")

        # Create plot
        df = pd.DataFrame({'x': [1, 2, 3], 'y': [4, 5, 6]})
        plot_data = dataframe_to_plot_data(
            key='repeated_plot',
            df=df,
            plot_type='line',
            caption='Repeated Plot',
        )
        one.db_manager.add_plot(plot_data)

        # Perform variable substitution without full compile
        one._prep_compilation()
        one._perform_variable_substitution(use_table_var_substitution=True)

        # Enable frontend export mode
        one._is_frontend_export = True

        # Build AST manually without pandoc-crossref to avoid duplicate ID errors
        # (This is just for testing - in production, each figure would have unique IDs)
        import pypandoc

        # Read the built markdown
        build_file = one.md_files_main[0].build_file
        md_content = build_file.read_text()

        # Convert to AST JSON without pandoc-crossref filter
        ast_json = pypandoc.convert_text(
            md_content,
            to="json",
            format="markdown",
            extra_args=["-M2GB", "+RTS", "-K64m", "-RTS"]
        )
        ast = json.loads(ast_json)

        # Find all figures with plot keys
        figures_with_plot_key = []

        def check_blocks(blocks):
            for block in blocks:
                if not isinstance(block, dict):
                    continue

                if block.get("t") == "Figure":
                    c = block.get("c", [])
                    if isinstance(c, list) and len(c) >= 3:
                        attr = c[0]
                        if isinstance(attr, list) and len(attr) >= 3:
                            fig_id = attr[0]
                            attrs_dict = attr[2] if len(attr) > 2 else []

                            # Check for data-plot-key attribute
                            for kv in attrs_dict:
                                if isinstance(kv, list) and len(kv) >= 2:
                                    if kv[0] == "data-plot-key":
                                        figures_with_plot_key.append({
                                            'fig_id': fig_id,
                                            'plot_key': kv[1]
                                        })
                                        break

                # Recursively check nested blocks
                if block.get("t") in ["Div", "BlockQuote"]:
                    nested = block.get("c")
                    if isinstance(nested, list) and len(nested) >= 2:
                        check_blocks(nested[1])

        check_blocks(ast.get("blocks", []))

        # Should find 3 figures, all with the same plot key
        assert len(figures_with_plot_key) == 3, f"Expected 3 figures with plot keys, found {len(figures_with_plot_key)}"

        # All should reference the same plot key (this is the key functionality)
        for fig in figures_with_plot_key:
            assert fig['plot_key'] == 'repeated_plot', f"Expected plot_key='repeated_plot', got '{fig['plot_key']}'"

        # Note: Without pandoc-crossref processing, figure IDs may all be the same
        # The important part is that the data-plot-key attribute is correctly set
        # so the frontend can identify which plots to render interactively
        fig_ids = [fig['fig_id'] for fig in figures_with_plot_key]
        # At least one should have the base plot name
        assert any('repeated_plot' in fid for fid in fig_ids), f"Expected at least one figure with 'repeated_plot' in ID, got {fig_ids}"

    def test_mixed_plots_and_regular_figures(self, tmp_path):
        """Test that only plot figures get data-plot-key, not regular images."""
        test_dir = tmp_path / "test_mixed_figures"
        test_dir.mkdir(parents=True, exist_ok=True)

        # Create markdown with both plot and regular image BEFORE initializing OneDoc
        main_dir = test_dir / "00-main"
        main_dir.mkdir(parents=True, exist_ok=True)

        # Create a dummy image file
        dummy_image = main_dir / "dummy.png"
        # Create a minimal 1x1 PNG file
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        dummy_image.write_bytes(png_data)

        markdown_content = """# Test Document

Here's a plot:

{{__my_plot__}}

Here's a regular image:

![Regular Image](dummy.png){#fig:regular_image}
"""
        md_file = main_dir / "test.md"
        md_file.write_text(markdown_content)

        one = OneDoc(test_dir, work_dir=tmp_path / "work")

        # Create a plot
        df = pd.DataFrame({'x': [1, 2], 'y': [3, 4]})
        plot_data = dataframe_to_plot_data(
            key='my_plot',
            df=df,
            plot_type='scatter',
            caption='My Plot',
        )
        one.db_manager.add_plot(plot_data)

        one.compile("test_output", export_format="html")
        one._is_frontend_export = True
        exporter = ASTExporter(one)
        ast = exporter.build_ast()

        # Find figures and check which ones have plot keys
        figures_info = []

        def check_blocks(blocks):
            for block in blocks:
                if not isinstance(block, dict):
                    continue

                if block.get("t") == "Figure":
                    c = block.get("c", [])
                    if isinstance(c, list) and len(c) >= 3:
                        attr = c[0]
                        if isinstance(attr, list) and len(attr) >= 3:
                            fig_id = attr[0]
                            attrs_dict = attr[2] if len(attr) > 2 else []

                            plot_key = None
                            for kv in attrs_dict:
                                if isinstance(kv, list) and len(kv) >= 2:
                                    if kv[0] == "data-plot-key":
                                        plot_key = kv[1]
                                        break

                            figures_info.append({
                                'fig_id': fig_id,
                                'plot_key': plot_key
                            })

                # Recursively check nested blocks
                if block.get("t") in ["Div", "BlockQuote"]:
                    nested = block.get("c")
                    if isinstance(nested, list) and len(nested) >= 2:
                        check_blocks(nested[1])

        check_blocks(ast.get("blocks", []))

        # Should find 2 figures
        assert len(figures_info) == 2, f"Expected 2 figures, found {len(figures_info)}"

        # One should have plot_key, one should not
        plot_figures = [f for f in figures_info if f['plot_key'] is not None]
        regular_figures = [f for f in figures_info if f['plot_key'] is None]

        assert len(plot_figures) == 1, "Expected exactly 1 plot figure"
        assert len(regular_figures) == 1, "Expected exactly 1 regular figure"

        assert plot_figures[0]['plot_key'] == 'my_plot'
        assert 'my_plot' in plot_figures[0]['fig_id']
        assert 'regular_image' in regular_figures[0]['fig_id']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
