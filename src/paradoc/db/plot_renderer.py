"""Plot rendering utilities for converting PlotData to image markdown."""

from __future__ import annotations

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

from .models import PlotData

logger = logging.getLogger(__name__)


class PlotRenderer:
    """Handles rendering of plots to various formats."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize plot renderer with custom function registry.

        Args:
            cache_dir: Optional directory for caching rendered figures (unused, kept for API compatibility)
        """
        self._custom_functions: Dict[str, Callable] = {}
        # Note: Caching is now handled at the document level using PNG+timestamp files
        # This parameter is kept for backward compatibility but not used

    def register_custom_function(self, name: str, func: Callable) -> None:
        """
        Register a custom plotting function.

        Args:
            name: Name of the function
            func: Callable that returns a plotly figure
        """
        self._custom_functions[name] = func

    def _create_figure(self, plot_data: PlotData) -> Any:
        """
        Create a plotly figure from PlotData with timestamp-based caching.

        Args:
            plot_data: PlotData instance

        Returns:
            Plotly figure object
        """
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
            if not PLOTLY_AVAILABLE:
                raise ImportError("plotly is required for plot rendering. Install with: pip install plotly")

            # Reconstruct plotly figure from dict
            fig = go.Figure(plot_data.data)

        else:
            # Use default plot types
            fig = self._create_default_plot(plot_data)

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
