"""Utilities for converting between pandas DataFrames and database models."""

from __future__ import annotations

import re
from typing import Any, Optional, Tuple

import pandas as pd

from .models import (
    PlotAnnotation,
    PlotData,
    TableAnnotation,
    TableCell,
    TableColumn,
    TableData,
)


def dataframe_to_table_data(
    key: str, df: pd.DataFrame, caption: str, show_index: bool = True, default_sort: Optional[Tuple[str, bool]] = None
) -> TableData:
    """
    Convert a pandas DataFrame to a TableData model.

    Args:
        key: Unique table key (without __ markers)
        df: pandas DataFrame
        caption: Table caption
        show_index: Whether to show index by default
        default_sort: Optional default sort as (column_name, ascending). E.g., ("Age", True) for ascending sort by Age.

    Returns:
        TableData instance
    """
    # Extract columns
    columns = []
    for col_name in df.columns:
        dtype = str(df[col_name].dtype)
        # Map pandas dtypes to simpler types
        if "int" in dtype:
            data_type = "int"
        elif "float" in dtype:
            data_type = "float"
        elif "bool" in dtype:
            data_type = "bool"
        else:
            data_type = "string"

        columns.append(TableColumn(name=str(col_name), data_type=data_type))

    # Extract cells
    cells = []
    for row_idx, row in df.iterrows():
        for col_name in df.columns:
            cell_value = row[col_name]
            # Handle NaN values
            if pd.isna(cell_value):
                cell_value = ""
            cells.append(
                TableCell(
                    row_index=int(row_idx) if isinstance(row_idx, (int, float)) else len(cells) // len(df.columns),
                    column_name=str(col_name),
                    value=cell_value,
                )
            )

    # Create default sort config if provided
    from .models import TableSortConfig

    default_sort_config = None
    if default_sort:
        column_name, ascending = default_sort
        default_sort_config = TableSortConfig(column_name=column_name, ascending=ascending)

    return TableData(
        key=key,
        columns=columns,
        cells=cells,
        caption=caption,
        show_index_default=show_index,
        default_sort=default_sort_config,
    )


def table_data_to_dataframe(table_data: TableData) -> pd.DataFrame:
    """
    Convert a TableData model to a pandas DataFrame.

    Args:
        table_data: TableData instance

    Returns:
        pandas DataFrame
    """
    # Group cells by row
    rows_dict = {}
    for cell in table_data.cells:
        if cell.row_index not in rows_dict:
            rows_dict[cell.row_index] = {}
        rows_dict[cell.row_index][cell.column_name] = cell.value

    # Create DataFrame
    column_names = [col.name for col in table_data.columns]
    rows = [rows_dict.get(i, {}) for i in sorted(rows_dict.keys())]

    df = pd.DataFrame(rows, columns=column_names)

    # Convert types based on column metadata
    for col in table_data.columns:
        if col.data_type == "int":
            try:
                df[col.name] = pd.to_numeric(df[col.name], errors="coerce").astype("Int64")
            except Exception:
                pass
        elif col.data_type == "float":
            try:
                df[col.name] = pd.to_numeric(df[col.name], errors="coerce")
            except Exception:
                pass
        elif col.data_type == "bool":
            try:
                df[col.name] = df[col.name].astype(bool)
            except Exception:
                pass

    return df


def parse_table_reference(reference_str: str) -> Tuple[str, Optional[TableAnnotation]]:
    """
    Parse a table reference string from markdown.

    Examples:
        {{__my_table__}} -> ('my_table', None)
        {{__my_table__}}{tbl:index:no} -> ('my_table', TableAnnotation(show_index=False))
        {{__my_table__}}{tbl:sortby:column_a;index:no} -> ('my_table', TableAnnotation(...))

    Args:
        reference_str: Full reference string from markdown

    Returns:
        Tuple of (table_key, annotation_config or None)
    """
    # Extract table key
    key_match = re.search(r"{{__(\w+)__}}", reference_str)
    if not key_match:
        raise ValueError(f"Invalid table reference format: {reference_str}")

    table_key = key_match.group(1)

    # Extract annotation if present - look for {tbl:...} after the key
    # Find where the annotation starts
    annotation_start = reference_str.find("{tbl:")
    annotation = None

    if annotation_start != -1:
        # Count braces to find the matching closing brace
        brace_depth = 0
        annotation_end = annotation_start

        for i in range(annotation_start, len(reference_str)):
            char = reference_str[i]
            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    annotation_end = i + 1
                    break

        if annotation_end > annotation_start:
            annotation_str = reference_str[annotation_start:annotation_end]
            annotation = TableAnnotation.from_annotation_string(annotation_str)

    return table_key, annotation


def apply_table_annotation(
    df: pd.DataFrame, annotation: Optional[TableAnnotation], default_show_index: bool = True
) -> Tuple[pd.DataFrame, bool]:
    """
    Apply table annotation settings to a DataFrame.

    Args:
        df: pandas DataFrame
        annotation: TableAnnotation instance or None
        default_show_index: Default index visibility

    Returns:
        Tuple of (modified DataFrame, show_index boolean)
    """
    if annotation is None:
        return df.copy(), default_show_index

    df_result = df.copy()

    # Apply sorting
    if annotation.sort_by and annotation.sort_by in df_result.columns:
        df_result = df_result.sort_values(by=annotation.sort_by, ascending=annotation.sort_ascending)

    # Apply filtering
    if annotation.filter_pattern:
        if annotation.filter_column and annotation.filter_column in df_result.columns:
            # Filter specific column
            mask = (
                df_result[annotation.filter_column]
                .astype(str)
                .str.contains(annotation.filter_pattern, regex=True, na=False)
            )
            df_result = df_result[mask]
        else:
            # Filter across all columns
            mask = (
                df_result.astype(str)
                .apply(lambda x: x.str.contains(annotation.filter_pattern, regex=True, na=False))
                .any(axis=1)
            )
            df_result = df_result[mask]

    # Reset index after transformations so indices are sequential
    df_result = df_result.reset_index(drop=True)

    show_index = annotation.show_index if annotation else default_show_index

    return df_result, show_index


# ============================================================================
# Plot utilities
# ============================================================================


def dataframe_to_plot_data(
    key: str,
    df: pd.DataFrame,
    plot_type: str,
    caption: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    **kwargs,
) -> PlotData:
    """
    Convert a pandas DataFrame to a PlotData model for default plot types.

    Args:
        key: Unique plot key (without __ markers)
        df: pandas DataFrame
        plot_type: Type of plot ('line', 'bar', 'scatter', 'histogram', etc.)
        caption: Plot caption
        width: Plot width in pixels
        height: Plot height in pixels
        **kwargs: Additional metadata

    Returns:
        PlotData instance
    """
    # Convert DataFrame to JSON-serializable dict
    data = {"columns": df.columns.tolist(), "data": df.to_dict(orient="records"), "index": df.index.tolist()}

    return PlotData(
        key=key, plot_type=plot_type, data=data, caption=caption, width=width, height=height, metadata=kwargs
    )


def custom_function_to_plot_data(
    key: str,
    function_name: str,
    caption: str,
    data: Optional[dict] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    **kwargs,
) -> PlotData:
    """
    Create a PlotData model for a custom Python function that returns a plotly figure.

    Args:
        key: Unique plot key (without __ markers)
        function_name: Name of the custom function (must be registered separately)
        caption: Plot caption
        data: Optional data to pass to the function
        width: Plot width in pixels
        height: Plot height in pixels
        **kwargs: Additional metadata

    Returns:
        PlotData instance
    """
    return PlotData(
        key=key,
        plot_type="custom",
        custom_function_name=function_name,
        data=data or {},
        caption=caption,
        width=width,
        height=height,
        metadata=kwargs,
    )


def plotly_figure_to_plot_data(
    key: str,
    fig: Any,  # plotly.graph_objects.Figure
    caption: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    **kwargs,
) -> PlotData:
    """
    Convert a plotly figure directly to PlotData.

    Args:
        key: Unique plot key (without __ markers)
        fig: Plotly figure object
        caption: Plot caption
        width: Plot width in pixels
        height: Plot height in pixels
        **kwargs: Additional metadata

    Returns:
        PlotData instance
    """
    # Store the figure as a dict using plotly's JSON serialization
    # This handles numpy arrays properly
    import json as json_lib

    if hasattr(fig, "to_json"):
        fig_dict = json_lib.loads(fig.to_json())
    elif hasattr(fig, "to_dict"):
        fig_dict = fig.to_dict()
    else:
        fig_dict = dict(fig)

    return PlotData(
        key=key, plot_type="plotly", data=fig_dict, caption=caption, width=width, height=height, metadata=kwargs
    )


def parse_plot_reference(reference_str: str) -> Tuple[str, Optional[PlotAnnotation]]:
    """
    Parse a plot reference string from markdown.

    Examples:
        {{__my_plot__}} -> ('my_plot', None)
        {{__my_plot__}}{plt:width:800} -> ('my_plot', PlotAnnotation(width=800))
        {{__my_plot__}}{plt:width:800;height:600} -> ('my_plot', PlotAnnotation(...))

    Args:
        reference_str: Full reference string from markdown

    Returns:
        Tuple of (plot_key, annotation_config or None)
    """
    # Extract plot key
    key_match = re.search(r"{{__(\w+)__}}", reference_str)
    if not key_match:
        raise ValueError(f"Invalid plot reference format: {reference_str}")

    plot_key = key_match.group(1)

    # Extract annotation if present - look for {plt:...} after the key
    annotation_start = reference_str.find("{plt:")
    annotation = None

    if annotation_start != -1:
        # Count braces to find the matching closing brace
        brace_depth = 0
        annotation_end = annotation_start

        for i in range(annotation_start, len(reference_str)):
            char = reference_str[i]
            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    annotation_end = i + 1
                    break

        if annotation_end > annotation_start:
            annotation_str = reference_str[annotation_start:annotation_end]
            annotation = PlotAnnotation.from_annotation_string(annotation_str)

    return plot_key, annotation
