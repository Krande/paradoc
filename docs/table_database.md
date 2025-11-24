# Table Database Documentation

## Overview

The Paradoc table database provides a robust SQLite-based storage system for managing table data with support for custom annotations, sorting, and filtering. All database models are defined using Pydantic v2 for type safety and validation.

## Features

- **SQLite Database**: Lightweight, file-based storage for table and plot data
- **Pydantic v2 Models**: Type-safe data models with validation
- **Custom Annotations**: Markdown-based table configuration
- **Sorting & Filtering**: Built-in support for table transformations
- **Pandas Integration**: Seamless conversion between DataFrames and database models

## Installation

The database functionality requires Pydantic v2. Add it to your project dependencies:

```bash
pixi add pydantic>=2.0
```

## Database Models

### TableData
Stores complete table information including columns, cells, caption, and display options.

### TableColumn
Represents a single column with name and data type (string, int, float, bool).

### TableCell
Stores individual cell values with row/column coordinates.

### TableAnnotation
Parses and stores custom display options from markdown annotations.

## Basic Usage

### 1. Creating a Database Manager

```python
from paradoc.db import DbManager

# Create or connect to database
db = DbManager("my_data.db")

# Use as context manager (recommended)
with DbManager("my_data.db") as db:
    # ... work with database
    pass
```

### 2. Storing Tables

```python
import pandas as pd
from paradoc.db import DbManager, dataframe_to_table_data

# Create a DataFrame
df = pd.DataFrame({
    'Name': ['Alice', 'Bob', 'Charlie'],
    'Age': [25, 30, 35],
    'City': ['New York', 'Boston', 'Chicago']
})

# Convert to table data
table_data = dataframe_to_table_data(
    key='my_table',  # No __ markers in the key
    df=df,
    caption='Employee Information',
    show_index=False
)

# Store in database
with DbManager("my_data.db") as db:
    db.add_table(table_data)
```

### 3. Retrieving Tables

```python
from paradoc.db import DbManager, table_data_to_dataframe

with DbManager("my_data.db") as db:
    # Get table data
    table_data = db.get_table('my_table')
    
    # Convert back to DataFrame
    df = table_data_to_dataframe(table_data)
    print(df)
    
    # List all tables
    all_tables = db.list_tables()
    print(f"Available tables: {all_tables}")
```

## Markdown Annotations

### Syntax

In markdown files, reference tables with the key wrapped in double underscores:

```markdown
# My Report

Here is a table:

{{__my_table__}}
```

Add custom annotations after the reference:

```markdown
{{__my_table__}}{tbl:index:no}
```

### Annotation Options

| Option | Syntax | Description |
|--------|--------|-------------|
| **Hide Index** | `{tbl:index:no}` | Don't show the table index |
| **Show Index** | `{tbl:index:yes}` | Show the table index (default) |
| **Sort Ascending** | `{tbl:sortby:column_name}` | Sort by column (ascending) |
| **Sort Descending** | `{tbl:sortby:column_name:desc}` | Sort by column (descending) |
| **Filter** | `{tbl:filter:regex_pattern}` | Filter rows matching pattern |
| **Filter Column** | `{tbl:filter:pattern:column_name}` | Filter specific column |
| **No Caption** | `{tbl:nocaption}` | Hide the table caption |

### Combining Options

Use semicolons to combine multiple options:

```markdown
{{__my_table__}}{tbl:index:no;sortby:Age:desc;filter:.*York.*}
```

This will:
- Hide the index
- Sort by 'Age' column in descending order
- Filter rows containing "York"

## Examples

### Example 1: Simple Table Reference

```markdown
# Employee List

{{__employee_data__}}
```

### Example 2: Sorted Table Without Index

```markdown
# Top Performers (sorted by score)

{{__performance_data__}}{tbl:sortby:score:desc;index:no}
```

### Example 3: Filtered Results

```markdown
# New York Employees Only

{{__employee_data__}}{tbl:filter:New York;index:no}
```

### Example 4: Complex Annotation

```markdown
# Sales Report

Top products sorted by revenue:

{{__sales_data__}}{tbl:sortby:revenue:desc;filter:^Widget.*;index:no}
```

## Programmatic Usage

### Parsing Markdown References

```python
from paradoc.db import parse_table_reference

# Parse a reference string
reference = '{{__my_table__}}{tbl:index:no;sortby:Name}'
key, annotation = parse_table_reference(reference)

print(f"Table key: {key}")  # 'my_table'
print(f"Show index: {annotation.show_index}")  # False
print(f"Sort by: {annotation.sort_by}")  # 'Name'
```

### Applying Annotations to DataFrames

```python
from paradoc.db import apply_table_annotation, table_data_to_dataframe
from paradoc.db.models import TableAnnotation

# Get table from database
with DbManager("my_data.db") as db:
    table_data = db.get_table('my_table')
    df = table_data_to_dataframe(table_data)

# Create annotation
annotation = TableAnnotation(
    sort_by='Age',
    sort_ascending=False,
    show_index=False,
    filter_pattern='.*York.*'
)

# Apply transformations
df_modified, show_index = apply_table_annotation(df, annotation)
```

## Database Schema

The database uses the following tables:

- **tables**: Main table metadata (key, caption, defaults)
- **table_columns**: Column definitions (name, data type)
- **table_cells**: Individual cell values
- **table_sort_config**: Default sorting configuration
- **table_filter_config**: Default filtering configuration
- **plots**: Plot data storage (for future use)

## API Reference

### DbManager

```python
class DbManager:
    def __init__(self, db_path: str | Path)
    def add_table(self, table_data: TableData) -> None
    def get_table(self, key: str) -> Optional[TableData]
    def list_tables(self) -> List[str]
    def delete_table(self, key: str) -> None
    def close(self) -> None
```

### Utility Functions

```python
def dataframe_to_table_data(
    key: str,
    df: pd.DataFrame,
    caption: str,
    show_index: bool = True
) -> TableData

def table_data_to_dataframe(table_data: TableData) -> pd.DataFrame

def parse_table_reference(reference_str: str) -> Tuple[str, Optional[TableAnnotation]]

def apply_table_annotation(
    df: pd.DataFrame,
    annotation: Optional[TableAnnotation],
    default_show_index: bool = True
) -> Tuple[pd.DataFrame, bool]
```

## Testing

Run the test suite:

```bash
pixi run test tests/tables/test_table_db.py
```

Run the example demo:

```bash
pixi run -e prod python examples/table_db_demo.py
```

## Future: Plot Data

The database schema includes a `plots` table for storing plot data. The API is similar:

```python
from paradoc.db.models import PlotData

plot_data = PlotData(
    key='my_plot',
    plot_type='line',
    data={'x': [1, 2, 3], 'y': [4, 5, 6]},
    caption='Sample Plot'
)

with DbManager("my_data.db") as db:
    db.add_plot(plot_data)
    retrieved_plot = db.get_plot('my_plot')
```

## Notes

- Table keys in the database do NOT include the `__` markers
- The `__` markers are only used in markdown files for uniqueness
- All regex patterns use Python's `re` module syntax
- Database connections are automatically closed when using context managers
- Pydantic v2 provides automatic validation and type checking

