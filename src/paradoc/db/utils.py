"""Utilities for converting between pandas DataFrames and database models."""
from __future__ import annotations

import re
from typing import Optional, Tuple

import pandas as pd

from .models import TableAnnotation, TableCell, TableColumn, TableData


def dataframe_to_table_data(
    key: str,
    df: pd.DataFrame,
    caption: str,
    show_index: bool = True
) -> TableData:
    """
    Convert a pandas DataFrame to a TableData model.

    Args:
        key: Unique table key (without __ markers)
        df: pandas DataFrame
        caption: Table caption
        show_index: Whether to show index by default

    Returns:
        TableData instance
    """
    # Extract columns
    columns = []
    for col_name in df.columns:
        dtype = str(df[col_name].dtype)
        # Map pandas dtypes to simpler types
        if 'int' in dtype:
            data_type = 'int'
        elif 'float' in dtype:
            data_type = 'float'
        elif 'bool' in dtype:
            data_type = 'bool'
        else:
            data_type = 'string'

        columns.append(TableColumn(name=str(col_name), data_type=data_type))

    # Extract cells
    cells = []
    for row_idx, row in df.iterrows():
        for col_name in df.columns:
            cell_value = row[col_name]
            # Handle NaN values
            if pd.isna(cell_value):
                cell_value = ""
            cells.append(TableCell(
                row_index=int(row_idx) if isinstance(row_idx, (int, float)) else len(cells) // len(df.columns),
                column_name=str(col_name),
                value=cell_value
            ))

    return TableData(
        key=key,
        columns=columns,
        cells=cells,
        caption=caption,
        show_index_default=show_index
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
        if col.data_type == 'int':
            try:
                df[col.name] = pd.to_numeric(df[col.name], errors='coerce').astype('Int64')
            except:
                pass
        elif col.data_type == 'float':
            try:
                df[col.name] = pd.to_numeric(df[col.name], errors='coerce')
            except:
                pass
        elif col.data_type == 'bool':
            try:
                df[col.name] = df[col.name].astype(bool)
            except:
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
    key_match = re.search(r'{{__(\w+)__}}', reference_str)
    if not key_match:
        raise ValueError(f"Invalid table reference format: {reference_str}")

    table_key = key_match.group(1)

    # Extract annotation if present
    annotation_match = re.search(r'{{__\w+__}}(\{tbl:.*?\})', reference_str)
    annotation = None
    if annotation_match:
        annotation_str = annotation_match.group(1)
        annotation = TableAnnotation.from_annotation_string(annotation_str)

    return table_key, annotation


def apply_table_annotation(
    df: pd.DataFrame,
    annotation: Optional[TableAnnotation],
    default_show_index: bool = True
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
        df_result = df_result.sort_values(
            by=annotation.sort_by,
            ascending=annotation.sort_ascending
        )

    # Apply filtering
    if annotation.filter_pattern:
        if annotation.filter_column and annotation.filter_column in df_result.columns:
            # Filter specific column
            mask = df_result[annotation.filter_column].astype(str).str.contains(
                annotation.filter_pattern,
                regex=True,
                na=False
            )
            df_result = df_result[mask]
        else:
            # Filter across all columns
            mask = df_result.astype(str).apply(
                lambda x: x.str.contains(annotation.filter_pattern, regex=True, na=False)
            ).any(axis=1)
            df_result = df_result[mask]

    show_index = annotation.show_index if annotation else default_show_index

    return df_result, show_index

