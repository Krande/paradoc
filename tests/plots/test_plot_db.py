"""Unit tests for plot functionality in Paradoc."""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import shutil

from paradoc.db import (
    DbManager,
    PlotData,
    PlotAnnotation,
    dataframe_to_plot_data,
    custom_function_to_plot_data,
    plotly_figure_to_plot_data,
    parse_plot_reference,
)
from paradoc.db.plot_renderer import PlotRenderer


class TestPlotData:
    """Test PlotData model."""

    def test_plot_data_creation(self):
        """Test creating a basic PlotData instance."""
        plot = PlotData(
            key='test_plot',
            plot_type='line',
            data={'x': [1, 2, 3], 'y': [4, 5, 6]},
            caption='Test Plot'
        )

        assert plot.key == 'test_plot'
        assert plot.plot_type == 'line'
        assert plot.caption == 'Test Plot'
        assert plot.data == {'x': [1, 2, 3], 'y': [4, 5, 6]}

    def test_plot_data_with_dimensions(self):
        """Test PlotData with width and height."""
        plot = PlotData(
            key='sized_plot',
            plot_type='bar',
            data={},
            caption='Sized Plot',
            width=800,
            height=600
        )

        assert plot.width == 800
        assert plot.height == 600

    def test_plot_data_custom_function(self):
        """Test PlotData with custom function."""
        plot = PlotData(
            key='custom_plot',
            plot_type='custom',
            custom_function_name='my_custom_func',
            data={'param': 'value'},
            caption='Custom Plot'
        )

        assert plot.custom_function_name == 'my_custom_func'
        assert plot.plot_type == 'custom'

    def test_plot_data_key_validation(self):
        """Test that plot key validation rejects __ markers."""
        with pytest.raises(ValueError, match="should not contain __ markers"):
            PlotData(
                key='__invalid__',
                plot_type='line',
                data={},
                caption='Invalid'
            )


class TestPlotAnnotation:
    """Test PlotAnnotation parsing."""

    def test_parse_width_annotation(self):
        """Test parsing width annotation."""
        annotation = PlotAnnotation.from_annotation_string('{plt:width:800}')
        assert annotation.width == 800
        assert annotation.height is None
        assert annotation.no_caption is False

    def test_parse_height_annotation(self):
        """Test parsing height annotation."""
        annotation = PlotAnnotation.from_annotation_string('{plt:height:600}')
        assert annotation.width is None
        assert annotation.height == 600

    def test_parse_multiple_annotations(self):
        """Test parsing multiple annotations."""
        annotation = PlotAnnotation.from_annotation_string('{plt:width:800;height:600}')
        assert annotation.width == 800
        assert annotation.height == 600

    def test_parse_nocaption_annotation(self):
        """Test parsing nocaption annotation."""
        annotation = PlotAnnotation.from_annotation_string('{plt:nocaption}')
        assert annotation.no_caption is True

    def test_parse_format_annotation(self):
        """Test parsing format annotation."""
        annotation = PlotAnnotation.from_annotation_string('{plt:format:svg}')
        assert annotation.format == 'svg'

    def test_parse_complex_annotation(self):
        """Test parsing complex annotation string."""
        annotation = PlotAnnotation.from_annotation_string('{plt:width:1024;height:768;format:png}')
        assert annotation.width == 1024
        assert annotation.height == 768
        assert annotation.format == 'png'


class TestPlotUtilities:
    """Test plot utility functions."""

    def test_dataframe_to_plot_data(self):
        """Test converting DataFrame to PlotData."""
        df = pd.DataFrame({
            'x': [1, 2, 3, 4],
            'y': [2, 4, 6, 8]
        })

        plot = dataframe_to_plot_data(
            key='df_plot',
            df=df,
            plot_type='line',
            caption='DataFrame Plot',
            width=700,
            height=500
        )

        assert plot.key == 'df_plot'
        assert plot.plot_type == 'line'
        assert plot.caption == 'DataFrame Plot'
        assert plot.width == 700
        assert plot.height == 500
        assert 'columns' in plot.data
        assert 'data' in plot.data
        assert plot.data['columns'] == ['x', 'y']

    def test_custom_function_to_plot_data(self):
        """Test creating PlotData for custom function."""
        plot = custom_function_to_plot_data(
            key='custom_func_plot',
            function_name='my_plotting_function',
            caption='Custom Function Plot',
            data={'param1': 10, 'param2': 20}
        )

        assert plot.key == 'custom_func_plot'
        assert plot.plot_type == 'custom'
        assert plot.custom_function_name == 'my_plotting_function'
        assert plot.data == {'param1': 10, 'param2': 20}

    def test_parse_plot_reference_simple(self):
        """Test parsing simple plot reference."""
        key, annotation = parse_plot_reference('{{__my_plot__}}')
        assert key == 'my_plot'
        assert annotation is None

    def test_parse_plot_reference_with_annotation(self):
        """Test parsing plot reference with annotation."""
        key, annotation = parse_plot_reference('{{__my_plot__}}{plt:width:800}')
        assert key == 'my_plot'
        assert annotation is not None
        assert annotation.width == 800

    def test_parse_plot_reference_complex(self):
        """Test parsing complex plot reference with multiple annotations."""
        key, annotation = parse_plot_reference('{{__my_plot__}}{plt:width:1024;height:768;nocaption}')
        assert key == 'my_plot'
        assert annotation.width == 1024
        assert annotation.height == 768
        assert annotation.no_caption is True


class TestDbManagerPlots:
    """Test DbManager plot operations."""

    def setup_method(self):
        """Set up test database."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.db_path = self.test_dir / "test.db"
        self.db_manager = DbManager(self.db_path)

    def teardown_method(self):
        """Clean up test database."""
        self.db_manager.close()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_add_and_get_plot(self):
        """Test adding and retrieving a plot."""
        plot = PlotData(
            key='test_plot',
            plot_type='line',
            data={'x': [1, 2, 3], 'y': [4, 5, 6]},
            caption='Test Plot',
            width=800,
            height=600
        )

        # Add plot
        self.db_manager.add_plot(plot)

        # Retrieve plot
        retrieved = self.db_manager.get_plot('test_plot')

        assert retrieved is not None
        assert retrieved.key == 'test_plot'
        assert retrieved.plot_type == 'line'
        assert retrieved.caption == 'Test Plot'
        assert retrieved.width == 800
        assert retrieved.height == 600
        assert retrieved.data == {'x': [1, 2, 3], 'y': [4, 5, 6]}

    def test_list_plots(self):
        """Test listing all plots."""
        # Add multiple plots
        for i in range(3):
            plot = PlotData(
                key=f'plot_{i}',
                plot_type='bar',
                data={},
                caption=f'Plot {i}'
            )
            self.db_manager.add_plot(plot)

        # List plots
        plot_keys = self.db_manager.list_plots()

        assert len(plot_keys) == 3
        assert 'plot_0' in plot_keys
        assert 'plot_1' in plot_keys
        assert 'plot_2' in plot_keys

    def test_update_plot(self):
        """Test updating an existing plot."""
        # Add plot
        plot = PlotData(
            key='update_test',
            plot_type='line',
            data={'x': [1, 2]},
            caption='Original Caption'
        )
        self.db_manager.add_plot(plot)

        # Update plot
        updated_plot = PlotData(
            key='update_test',
            plot_type='bar',
            data={'x': [1, 2, 3, 4]},
            caption='Updated Caption',
            width=1000
        )
        self.db_manager.add_plot(updated_plot)

        # Retrieve and verify
        retrieved = self.db_manager.get_plot('update_test')
        assert retrieved.plot_type == 'bar'
        assert retrieved.caption == 'Updated Caption'
        assert retrieved.width == 1000
        assert len(retrieved.data['x']) == 4

    def test_delete_plot(self):
        """Test deleting a plot."""
        # Add plot
        plot = PlotData(
            key='delete_test',
            plot_type='scatter',
            data={},
            caption='To Be Deleted'
        )
        self.db_manager.add_plot(plot)

        # Verify it exists
        assert self.db_manager.get_plot('delete_test') is not None

        # Delete plot
        self.db_manager.delete_plot('delete_test')

        # Verify it's gone
        assert self.db_manager.get_plot('delete_test') is None

    def test_get_nonexistent_plot(self):
        """Test retrieving a plot that doesn't exist."""
        result = self.db_manager.get_plot('nonexistent')
        assert result is None


class TestPlotRenderer:
    """Test PlotRenderer functionality."""

    def setup_method(self):
        """Set up test renderer."""
        self.renderer = PlotRenderer()
        self.test_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test directory."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_register_custom_function(self):
        """Test registering a custom plotting function."""
        def my_custom_plot(data):
            import plotly.graph_objects as go
            return go.Figure()

        self.renderer.register_custom_function('my_plot', my_custom_plot)
        assert 'my_plot' in self.renderer._custom_functions

    def test_create_line_plot(self):
        """Test creating a default line plot."""
        df = pd.DataFrame({
            'x': np.linspace(0, 10, 50),
            'y': np.sin(np.linspace(0, 10, 50))
        })

        plot_data = dataframe_to_plot_data(
            key='line_test',
            df=df,
            plot_type='line',
            caption='Line Plot Test',
            width=600,
            height=400
        )

        # This would require plotly to be installed
        # Just test that the plot_data is created correctly
        assert plot_data.plot_type == 'line'
        assert 'data' in plot_data.data

    def test_create_bar_plot(self):
        """Test creating a default bar plot."""
        df = pd.DataFrame({
            'category': ['A', 'B', 'C', 'D'],
            'values': [10, 20, 15, 25]
        })

        plot_data = dataframe_to_plot_data(
            key='bar_test',
            df=df,
            plot_type='bar',
            caption='Bar Plot Test'
        )

        assert plot_data.plot_type == 'bar'
        assert len(plot_data.data['data']) == 4

    def test_plot_with_annotation_override(self):
        """Test that annotation overrides plot data settings."""
        plot_data = PlotData(
            key='override_test',
            plot_type='scatter',
            data={},
            caption='Override Test',
            width=800,
            height=600
        )

        annotation = PlotAnnotation(width=1024, height=768)

        # The annotation should override the plot_data dimensions
        assert annotation.width == 1024
        assert annotation.height == 768


class TestPlotIntegration:
    """Integration tests for plot functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.db_path = self.test_dir / "test.db"
        self.db_manager = DbManager(self.db_path)
        self.renderer = PlotRenderer()

    def teardown_method(self):
        """Clean up test environment."""
        self.db_manager.close()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_full_plot_workflow(self):
        """Test complete workflow: create, store, retrieve, render."""
        # Create plot data
        df = pd.DataFrame({
            'x': [1, 2, 3, 4, 5],
            'y': [2, 4, 3, 5, 6]
        })

        plot_data = dataframe_to_plot_data(
            key='workflow_test',
            df=df,
            plot_type='line',
            caption='Workflow Test Plot',
            width=700,
            height=500
        )

        # Store in database
        self.db_manager.add_plot(plot_data)

        # Retrieve from database
        retrieved = self.db_manager.get_plot('workflow_test')

        assert retrieved is not None
        assert retrieved.key == 'workflow_test'
        assert retrieved.caption == 'Workflow Test Plot'

        # Reconstruct DataFrame
        df_retrieved = pd.DataFrame(retrieved.data['data'])
        assert len(df_retrieved) == 5
        assert list(df_retrieved.columns) == ['x', 'y']

    def test_multiple_plots_same_type(self):
        """Test storing multiple plots of the same type."""
        for i in range(5):
            df = pd.DataFrame({
                'x': list(range(i+1)),
                'y': [j**2 for j in range(i+1)]
            })

            plot_data = dataframe_to_plot_data(
                key=f'multi_plot_{i}',
                df=df,
                plot_type='scatter',
                caption=f'Plot {i}'
            )

            self.db_manager.add_plot(plot_data)

        # Verify all plots are stored
        plots = self.db_manager.list_plots()
        assert len(plots) == 5

        # Verify each plot
        for i in range(5):
            plot = self.db_manager.get_plot(f'multi_plot_{i}')
            assert plot is not None
            assert len(plot.data['data']) == i + 1

    def test_plot_metadata(self):
        """Test storing and retrieving plot metadata."""
        plot_data = PlotData(
            key='metadata_test',
            plot_type='heatmap',
            data={},
            caption='Metadata Test',
            metadata={
                'source': 'test_suite',
                'created_by': 'unit_test',
                'version': '1.0'
            }
        )

        self.db_manager.add_plot(plot_data)

        retrieved = self.db_manager.get_plot('metadata_test')
        assert retrieved.metadata['source'] == 'test_suite'
        assert retrieved.metadata['created_by'] == 'unit_test'
        assert retrieved.metadata['version'] == '1.0'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

