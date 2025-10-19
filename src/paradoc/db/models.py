"""Pydantic v2 models for table and plot database schema."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class TableColumn(BaseModel):
    """Represents a single column in a table."""
    name: str
    data_type: str = "string"  # string, int, float, bool, etc.

    model_config = {"frozen": False}


class TableCell(BaseModel):
    """Represents a cell value in a table."""
    row_index: int
    column_name: str
    value: Any

    model_config = {"frozen": False}


class TableSortConfig(BaseModel):
    """Configuration for table sorting."""
    column_name: str
    ascending: bool = True

    model_config = {"frozen": False}


class TableFilterConfig(BaseModel):
    """Configuration for table filtering."""
    column_name: str
    pattern: str  # regex pattern or simple string match
    is_regex: bool = True

    model_config = {"frozen": False}


class TableAnnotation(BaseModel):
    """Custom annotations for table display options."""
    show_index: bool = True
    sort_by: Optional[str] = None
    sort_ascending: bool = True
    filter_pattern: Optional[str] = None
    filter_column: Optional[str] = None
    no_caption: bool = False

    model_config = {"frozen": False}

    @classmethod
    def from_annotation_string(cls, annotation_str: str) -> TableAnnotation:
        """
        Parse annotation string like '{tbl:index:no;sortby:column_a;filter:pattern}'.

        Examples:
            {tbl:index:no}
            {tbl:sortby:column_a}
            {tbl:filter:.*pattern.*}
            {tbl:index:no;sortby:column_a:desc}
        """
        config = cls()

        if not annotation_str:
            return config

        # Remove outer braces and 'tbl:' prefix
        annotation_str = annotation_str.strip()
        if annotation_str.startswith("{") and annotation_str.endswith("}"):
            annotation_str = annotation_str[1:-1]

        if annotation_str.startswith("tbl:"):
            annotation_str = annotation_str[4:]

        # Split by semicolon for multiple options
        parts = annotation_str.split(";")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Split by colon
            tokens = [t.strip() for t in part.split(":")]

            if tokens[0] == "index":
                if len(tokens) > 1 and tokens[1].lower() == "no":
                    config.show_index = False
                elif len(tokens) > 1 and tokens[1].lower() == "yes":
                    config.show_index = True

            elif tokens[0] == "sortby":
                if len(tokens) > 1:
                    config.sort_by = tokens[1]
                    # Check for ascending/descending
                    if len(tokens) > 2:
                        config.sort_ascending = tokens[2].lower() != "desc"

            elif tokens[0] == "filter":
                if len(tokens) > 1:
                    config.filter_pattern = tokens[1]
                    # Optionally specify column
                    if len(tokens) > 2:
                        config.filter_column = tokens[2]

            elif tokens[0] == "nocaption":
                config.no_caption = True

        return config


class TableData(BaseModel):
    """Complete table data stored in database."""
    key: str = Field(..., description="Unique key for the table (without __ markers)")
    columns: List[TableColumn]
    cells: List[TableCell]
    caption: str
    default_sort: Optional[TableSortConfig] = None
    default_filter: Optional[TableFilterConfig] = None
    show_index_default: bool = True
    metadata: dict = Field(default_factory=dict)

    model_config = {"frozen": False}

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        """Ensure key doesn't contain __ markers."""
        if v.startswith("__") or v.endswith("__"):
            raise ValueError("Table key should not contain __ markers (they are added in markdown)")
        return v


class PlotData(BaseModel):
    """Complete plot data stored in database (placeholder for future use)."""
    key: str = Field(..., description="Unique key for the plot (without __ markers)")
    plot_type: str  # e.g., 'line', 'bar', 'scatter', etc.
    data: dict  # JSON-serializable plot data
    caption: str
    metadata: dict = Field(default_factory=dict)

    model_config = {"frozen": False}

