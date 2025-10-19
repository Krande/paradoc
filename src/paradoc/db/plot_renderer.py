"""Plot rendering utilities for converting PlotData to image markdown."""
from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from plotly.io import get_chrome

try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

import pandas as pd

from .models import PlotData, PlotAnnotation


class PlotRenderer:
    """Handles rendering of plots to various formats."""

    def __init__(self):
        """Initialize plot renderer with custom function registry."""
        self._custom_functions: Dict[str, Callable] = {}

    def register_custom_function(self, name: str, func: Callable) -> None:
        """
        Register a custom plotting function.

        Args:
            name: Name of the function
            func: Callable that returns a plotly figure
        """
        self._custom_functions[name] = func

    def render_to_image(
        self,
        plot_data: PlotData,
        annotation: Optional[PlotAnnotation] = None,
        output_path: Optional[Path] = None,
        format: str = "png",
        include_interactive_marker: bool = False
    ) -> str:
        """
        Render plot to an image and return markdown image reference.

        Args:
            plot_data: PlotData instance
            annotation: Optional annotation overrides
            output_path: Optional path to save image
            format: Image format ('png', 'svg', 'jpeg')
            include_interactive_marker: If True, add data attribute for interactive rendering

        Returns:
            Markdown image string
        """
        if not PLOTLY_AVAILABLE:
            raise ImportError("plotly is required for plot rendering. Install with: pip install plotly")

        # Get figure from plot data
        fig = self._create_figure(plot_data)

        # Apply size overrides from annotation or plot_data
        width = (annotation.width if annotation and annotation.width
                else plot_data.width or 800)
        height = (annotation.height if annotation and annotation.height
                 else plot_data.height or 600)

        fig.update_layout(width=width, height=height)

        # Determine format
        img_format = (annotation.format if annotation and annotation.format
                     else format)

        # Export to image
        if output_path:
            # Save to file
            #get_chrome()
            if img_format == 'svg':
                fig.write_image(str(output_path), format='svg')
            elif img_format == 'jpeg':
                fig.write_image(str(output_path), format='jpeg')
            else:
                fig.write_image(str(output_path), format='png')

            # Return markdown reference with proper pandoc-crossref syntax
            # The correct syntax is: ![caption](path){#fig:key}
            caption = "" if (annotation and annotation.no_caption) else plot_data.caption

            # Build the figure ID with optional interactive marker
            fig_id = f"fig:{plot_data.key}"

            if caption and not (annotation and annotation.no_caption):
                if include_interactive_marker:
                    # Add data-plot-key attribute for frontend interactive rendering
                    md_str = f"![{caption}]({output_path.name}){{#{fig_id} data-plot-key=\"{plot_data.key}\"}}"
                else:
                    md_str = f"![{caption}]({output_path.name}){{#{fig_id}}}"
            else:
                if include_interactive_marker:
                    md_str = f"![]({output_path.name}){{#{fig_id} data-plot-key=\"{plot_data.key}\"}}"
                else:
                    md_str = f"![]({output_path.name}){{#{fig_id}}}"

            return md_str
        else:
            # Return base64 embedded image
            img_bytes = fig.to_image(format=img_format)
            img_b64 = base64.b64encode(img_bytes).decode()

            caption = "" if (annotation and annotation.no_caption) else plot_data.caption

            # Build the figure ID with optional interactive marker
            fig_id = f"fig:{plot_data.key}"

            if caption and not (annotation and annotation.no_caption):
                if include_interactive_marker:
                    md_str = f"![{caption}](data:image/{img_format};base64,{img_b64}){{#{fig_id} data-plot-key=\"{plot_data.key}\"}}"
                else:
                    md_str = f"![{caption}](data:image/{img_format};base64,{img_b64}){{#{fig_id}}}"
            else:
                if include_interactive_marker:
                    md_str = f"![](data:image/{img_format};base64,{img_b64}){{#{fig_id} data-plot-key=\"{plot_data.key}\"}}"
                else:
                    md_str = f"![](data:image/{img_format};base64,{img_b64}){{#{fig_id}}}"

            return md_str

    def _create_figure(self, plot_data: PlotData) -> Any:
        """
        Create a plotly figure from PlotData.

        Args:
            plot_data: PlotData instance

        Returns:
            Plotly figure object
        """
        if plot_data.plot_type == 'custom':
            # Use custom function
            if not plot_data.custom_function_name:
                raise ValueError("Custom plot type requires custom_function_name")

            func = self._custom_functions.get(plot_data.custom_function_name)
            if not func:
                raise ValueError(
                    f"Custom function '{plot_data.custom_function_name}' not registered. "
                    f"Use renderer.register_custom_function() to register it."
                )

            return func(plot_data.data)

        elif plot_data.plot_type == 'plotly':
            # Reconstruct plotly figure from dict
            return go.Figure(plot_data.data)

        else:
            # Use default plot types
            return self._create_default_plot(plot_data)

    def _create_default_plot(self, plot_data: PlotData) -> Any:
        """
        Create a default plotly figure from PlotData.

        Args:
            plot_data: PlotData instance

        Returns:
            Plotly figure object
        """
        # Convert data back to DataFrame
        df = pd.DataFrame(plot_data.data['data'])

        # Create plot based on type
        if plot_data.plot_type == 'line':
            # Assume first column is x, rest are y series
            if len(df.columns) >= 2:
                fig = px.line(df, x=df.columns[0], y=df.columns[1:])
            else:
                fig = px.line(df)

        elif plot_data.plot_type == 'bar':
            if len(df.columns) >= 2:
                fig = px.bar(df, x=df.columns[0], y=df.columns[1:])
            else:
                fig = px.bar(df)

        elif plot_data.plot_type == 'scatter':
            if len(df.columns) >= 2:
                fig = px.scatter(df, x=df.columns[0], y=df.columns[1])
            else:
                fig = px.scatter(df)

        elif plot_data.plot_type == 'histogram':
            if len(df.columns) >= 1:
                fig = px.histogram(df, x=df.columns[0])
            else:
                fig = px.histogram(df)

        elif plot_data.plot_type == 'box':
            if len(df.columns) >= 1:
                fig = px.box(df, y=df.columns[0])
            else:
                fig = px.box(df)

        elif plot_data.plot_type == 'heatmap':
            # For heatmap, assume data is already in matrix form
            fig = px.imshow(df.values,
                          labels=dict(x="Column", y="Row", color="Value"),
                          x=df.columns.tolist(),
                          y=df.index.tolist())

        else:
            raise ValueError(f"Unsupported plot type: {plot_data.plot_type}")

        return fig
