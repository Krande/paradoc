"""Demo of plot functionality in Paradoc."""
import pandas as pd
import numpy as np
from pathlib import Path

from paradoc import OneDoc
from paradoc.common import ExportFormats
from paradoc.db import dataframe_to_plot_data, custom_function_to_plot_data, plotly_figure_to_plot_data

# Example 1: Create a simple line plot from DataFrame
def demo_simple_line_plot():
    """Create a simple line plot from a DataFrame."""
    # Create sample data
    x = np.linspace(0, 10, 100)
    df = pd.DataFrame({
        'x': x,
        'sin(x)': np.sin(x),
        'cos(x)': np.cos(x)
    })

    # Create plot data
    plot_data = dataframe_to_plot_data(
        key='trig_plot',
        df=df,
        plot_type='line',
        caption='Trigonometric Functions',
        width=800,
        height=400
    )

    return plot_data


# Example 2: Create a bar chart
def demo_bar_chart():
    """Create a bar chart from a DataFrame."""
    df = pd.DataFrame({
        'Category': ['A', 'B', 'C', 'D', 'E'],
        'Values': [23, 45, 56, 78, 32]
    })

    plot_data = dataframe_to_plot_data(
        key='bar_chart',
        df=df,
        plot_type='bar',
        caption='Sample Bar Chart',
        width=600,
        height=400
    )

    return plot_data


# Example 3: Custom plotting function
def demo_custom_plot_function():
    """Create a custom plotting function."""
    import plotly.graph_objects as go

    def create_custom_scatter_plot(data):
        """Custom function that creates a scatter plot with annotations."""
        # Extract data from the dict
        x = data.get('x', [1, 2, 3, 4, 5])
        y = data.get('y', [2, 4, 3, 5, 6])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode='markers+lines',
            marker=dict(size=10, color='blue'),
            line=dict(color='red', width=2)
        ))

        fig.update_layout(
            title='Custom Scatter Plot',
            xaxis_title='X Axis',
            yaxis_title='Y Axis'
        )

        return fig

    # Create plot data for custom function
    plot_data = custom_function_to_plot_data(
        key='custom_scatter',
        function_name='create_custom_scatter',
        caption='Custom Scatter Plot',
        data={'x': [1, 2, 3, 4, 5], 'y': [2, 4, 3, 5, 6]},
        width=700,
        height=500
    )

    return plot_data, create_custom_scatter_plot


# Example 4: Direct plotly figure
def demo_plotly_figure():
    """Create a plot directly from a plotly figure."""
    try:
        import plotly.express as px

        # Create sample data
        df = pd.DataFrame({
            'x': np.random.randn(100),
            'y': np.random.randn(100)
        })

        # Create plotly figure
        fig = px.scatter(df, x='x', y='y', title='Random Scatter Plot')

        # Convert to PlotData
        plot_data = plotly_figure_to_plot_data(
            key='random_scatter',
            fig=fig,
            caption='Random Data Scatter Plot',
            width=600,
            height=600
        )

        return plot_data
    except ImportError:
        print("Plotly not installed. Skipping this example.")
        return None


def main():
    """Main demo function."""
    print("=" * 60)
    print("Paradoc Plot Demo")
    print("=" * 60)

    # Setup test directory
    test_dir = Path(__file__).parent / "temp" / "plot_demo"
    test_dir.mkdir(parents=True, exist_ok=True)

    main_dir = test_dir / "00-main"
    main_dir.mkdir(exist_ok=True)

    # Initialize OneDoc
    one = OneDoc(
        source_dir=test_dir,
        work_dir=test_dir.parent / "plot_demo_work",
        create_dirs=True
    )

    # Add plots to database
    print("\n1. Creating simple line plot...")
    plot1 = demo_simple_line_plot()
    one.db_manager.add_plot(plot1)
    print(f"   Added plot: {plot1.key}")

    print("\n2. Creating bar chart...")
    plot2 = demo_bar_chart()
    one.db_manager.add_plot(plot2)
    print(f"   Added plot: {plot2.key}")

    print("\n3. Creating custom plot function...")
    plot3, custom_func = demo_custom_plot_function()
    one.db_manager.add_plot(plot3)
    # Register the custom function
    one.plot_renderer.register_custom_function('create_custom_scatter', custom_func)
    print(f"   Added plot: {plot3.key}")
    print(f"   Registered custom function: create_custom_scatter")

    print("\n4. Creating plotly figure...")
    plot4 = demo_plotly_figure()
    if plot4:
        one.db_manager.add_plot(plot4)
        print(f"   Added plot: {plot4.key}")

    # List all plots in database
    print("\n" + "=" * 60)
    print("Plots in database:")
    for plot_key in one.db_manager.list_plots():
        print(f"   - {plot_key}")

    # Create markdown file with plot references
    markdown_content = """# Plot Demo

## Line Plot
This is a line plot showing trigonometric functions.

{{__trig_plot__}}

## Bar Chart
This is a bar chart showing category values.

{{__bar_chart__}}{plt:width:500;height:300}

## Custom Plot
This is a custom scatter plot with annotations.

{{__custom_scatter__}}

## Random Scatter
This is a random scatter plot from plotly express.

{{__random_scatter__}}{plt:height:400}
"""

    md_file = main_dir / "demo.md"
    md_file.write_text(markdown_content)
    print(f"\nCreated markdown file: {md_file}")

    print("\n" + "=" * 60)
    print("Plot demo setup complete!")
    print(f"Source directory: {test_dir}")
    print("\nTo compile the document, you would run:")
    print("  one.compile('plot_demo', export_format='html')")
    print("\nNote: Plot rendering to images will be implemented")
    print("      in the variable substitution phase.")
    print("=" * 60)

    # Now let's actually send it to the frontend to test image resolution
    print("\nNow testing send_to_frontend with plot images...")

    try:
        one.send_to_frontend(embed_images=True)
        print("\n✓ Successfully sent document to frontend with embedded plot images!")
        print("✓ All plot images were found and embedded correctly.")
    except Exception as e:
        print(f"\n✗ Failed to send to frontend: {e}")
        import traceback
        traceback.print_exc()

    one.compile("plot_demo_2", export_format=ExportFormats.DOCX)


if __name__ == "__main__":
    main()
