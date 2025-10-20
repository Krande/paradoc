"""Plot rendering utilities for converting PlotData to image markdown."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    import plotly.express as px
    import plotly.graph_objects as go

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

import pandas as pd

from .models import PlotAnnotation, PlotData

logger = logging.getLogger(__name__)


class PlotRenderer:
    """Handles rendering of plots to various formats."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize plot renderer with custom function registry.

        Args:
            cache_dir: Optional directory for caching rendered figures
        """
        self._custom_functions: Dict[str, Callable] = {}
        self._figure_cache = None

        # Initialize cache if directory provided
        if cache_dir:
            try:
                from paradoc.cache import PlotFigureCache

                self._figure_cache = PlotFigureCache(cache_dir)
                logger.debug(f"Initialized plot figure cache at {cache_dir}")
            except Exception as e:
                logger.warning(f"Failed to initialize plot cache: {e}")

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
    ) -> str:
        """
        Render plot to an image and return markdown image reference.

        Args:
            plot_data: PlotData instance
            annotation: Optional annotation overrides
            output_path: Optional path to save image
            format: Image format ('png', 'svg', 'jpeg')
            include_interactive_marker: If True, add data attribute for interactive rendering (processed later in AST)

        Returns:
            Markdown image string
        """
        if not PLOTLY_AVAILABLE:
            raise ImportError("plotly is required for plot rendering. Install with: pip install plotly")

        # Get figure from plot data
        fig = self._create_figure(plot_data)

        # Apply size overrides from annotation or plot_data
        width = annotation.width if annotation and annotation.width else plot_data.width or 800
        height = annotation.height if annotation and annotation.height else plot_data.height or 600

        fig.update_layout(width=width, height=height)

        # Determine format
        img_format = annotation.format if annotation and annotation.format else format

        # Export to image
        if output_path:
            # Save to file
            # get_chrome()
            if img_format == "svg":
                fig.write_image(str(output_path), format="svg")
            elif img_format == "jpeg":
                fig.write_image(str(output_path), format="jpeg")
            else:
                fig.write_image(str(output_path), format="png")

            # Return markdown reference with proper pandoc-crossref syntax
            # The correct syntax is: ![caption](path){#fig:key}
            caption = "" if (annotation and annotation.no_caption) else plot_data.caption

            # Build the figure ID
            fig_id = f"fig:{plot_data.key}"

            if caption and not (annotation and annotation.no_caption):
                md_str = f"![{caption}]({output_path.name}){{#{fig_id}}}"
            else:
                md_str = f"![]({output_path.name}){{#{fig_id}}}"

            return md_str
        else:
            # Return base64 embedded image
            img_bytes = fig.to_image(format=img_format)
            img_b64 = base64.b64encode(img_bytes).decode()

            caption = "" if (annotation and annotation.no_caption) else plot_data.caption

            # Build the figure ID
            fig_id = f"fig:{plot_data.key}"

            if caption and not (annotation and annotation.no_caption):
                md_str = f"![{caption}](data:image/{img_format};base64,{img_b64}){{#{fig_id}}}"
            else:
                md_str = f"![](data:image/{img_format};base64,{img_b64}){{#{fig_id}}}"

            return md_str

    def _create_figure(self, plot_data: PlotData) -> Any:
        """
        Create a plotly figure from PlotData with timestamp-based caching.

        Args:
            plot_data: PlotData instance

        Returns:
            Plotly figure object
        """
        # Try to get from cache if available
        # Note: We need the database timestamp to validate the cache
        # This method is called with just PlotData, so we can't use caching here directly
        # The caching is better handled at a higher level where we have access to timestamps

        # Create figure based on plot type
        if plot_data.plot_type == "custom":
            # Use custom function
            if not plot_data.custom_function_name:
                raise ValueError("Custom plot type requires custom_function_name")

            func = self._custom_functions.get(plot_data.custom_function_name)
            if not func:
                raise ValueError(
                    f"Custom function '{plot_data.custom_function_name}' not registered. "
                    f"Use renderer.register_custom_function() to register it."
                )

            fig = func(plot_data.data)

        elif plot_data.plot_type == "plotly":
            # Reconstruct plotly figure from dict
            fig = go.Figure(plot_data.data)

        else:
            # Use default plot types
            fig = self._create_default_plot(plot_data)

        return fig

    def _create_figure_with_cache(self, plot_data: PlotData, db_timestamp: float) -> Any:
        """
        Create a plotly figure from PlotData with caching support.

        Args:
            plot_data: PlotData instance
            db_timestamp: Unix timestamp of when the plot was last updated in the database

        Returns:
            Plotly figure object
        """
        # Try to get from cache if available
        if self._figure_cache:
            cached_fig = self._figure_cache.get_figure(plot_data.key, db_timestamp)
            if cached_fig:
                return cached_fig

        # Cache miss - create figure
        fig = self._create_figure(plot_data)

        # Cache the figure if caching is enabled
        if self._figure_cache:
            self._figure_cache.set_figure(plot_data.key, db_timestamp, fig)

        return fig

    def _create_default_plot(self, plot_data: PlotData) -> Any:
        """
        Create a default plotly figure from PlotData.

        Args:
            plot_data: PlotData instance

        Returns:
            Plotly figure object
        """
        # Convert data back to DataFrame
        df = pd.DataFrame(plot_data.data["data"])

        # Create plot based on type
        if plot_data.plot_type == "line":
            # Assume first column is x, rest are y series
            if len(df.columns) >= 2:
                fig = px.line(df, x=df.columns[0], y=df.columns[1:])
            else:
                fig = px.line(df)

        elif plot_data.plot_type == "bar":
            if len(df.columns) >= 2:
                fig = px.bar(df, x=df.columns[0], y=df.columns[1:])
            else:
                fig = px.bar(df)

        elif plot_data.plot_type == "scatter":
            if len(df.columns) >= 2:
                fig = px.scatter(df, x=df.columns[0], y=df.columns[1])
            else:
                fig = px.scatter(df)

        elif plot_data.plot_type == "histogram":
            if len(df.columns) >= 1:
                fig = px.histogram(df, x=df.columns[0])
            else:
                fig = px.histogram(df)

        elif plot_data.plot_type == "box":
            if len(df.columns) >= 1:
                fig = px.box(df, y=df.columns[0])
            else:
                fig = px.box(df)

        elif plot_data.plot_type == "heatmap":
            # For heatmap, assume data is already in matrix form
            fig = px.imshow(
                df.values, labels=dict(x="Column", y="Row", color="Value"), x=df.columns.tolist(), y=df.index.tolist()
            )

        else:
            raise ValueError(f"Unsupported plot type: {plot_data.plot_type}")

        return fig

    def _get_plot_spec_dict(self, plot_data: PlotData) -> Dict[str, Any]:
        """
        Convert PlotData to a complete specification dictionary for hashing.

        This includes all data and styling that affects the rendered output.
        """
        spec = {
            "plot_type": plot_data.plot_type,
            "data": plot_data.data,
            "caption": plot_data.caption,
            "width": plot_data.width,
            "height": plot_data.height,
            "metadata": plot_data.metadata,
        }

        if plot_data.plot_type == "custom":
            spec["custom_function_name"] = plot_data.custom_function_name

        return spec
