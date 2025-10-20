"""Example demonstrating interactive tables in the frontend."""

import pandas as pd
from paradoc import OneDoc
from paradoc.db import DbManager, dataframe_to_table_data

def main():
    """Create a document with interactive tables."""

    # Create a database manager for storing table data
    db = DbManager("examples/temp/interactive_tables.db")

    # Create some sample tables
    df_sales = pd.DataFrame({
        "Product": ["Widget A", "Widget B", "Widget C", "Widget D", "Widget E"],
        "Q1 Sales": [1200, 850, 2100, 1450, 980],
        "Q2 Sales": [1350, 920, 2250, 1500, 1050],
        "Q3 Sales": [1280, 880, 2180, 1420, 1020],
        "Q4 Sales": [1450, 950, 2350, 1600, 1100],
    })

    df_employees = pd.DataFrame({
        "Name": ["Alice Smith", "Bob Johnson", "Charlie Brown", "Diana Prince", "Eve Adams"],
        "Department": ["Sales", "Engineering", "Marketing", "HR", "Engineering"],
        "Salary": [75000, 95000, 68000, 72000, 88000],
        "Years": [3, 5, 2, 7, 4],
    })

    # Add tables to database with sort options
    table_sales = dataframe_to_table_data(
        key="quarterly_sales",
        df=df_sales,
        caption="Quarterly Sales Data",
        show_index=True,
        default_sort=("Product", True)
    )
    db.add_table(table_sales)

    table_employees = dataframe_to_table_data(
        key="employee_data",
        df=df_employees,
        caption="Employee Information",
        show_index=False,
        default_sort=("Salary", False)  # Sort by salary descending
    )
    db.add_table(table_employees)

    # Create markdown document with table references
    markdown_content = """
# Interactive Tables Demo

This document demonstrates the new interactive table feature. When you hover over a table
that has data stored in the database, you'll see a "Static | Interactive" toggle button.

## Sales Performance

Below is the quarterly sales data for our product line. In static mode, you see the rendered
markdown table. In interactive mode, you can sort and filter the data:

| Product   | Q1 Sales | Q2 Sales | Q3 Sales | Q4 Sales |
|-----------|----------|----------|----------|----------|
| Widget A  | 1200     | 1350     | 1280     | 1450     |
| Widget B  | 850      | 920      | 880      | 950      |
| Widget C  | 2100     | 2250     | 2180     | 2350     |
| Widget D  | 1450     | 1500     | 1420     | 1600     |
| Widget E  | 980      | 1050     | 1020     | 1100     |

: Quarterly Sales Data {#tbl:quarterly_sales}

**Try it**: Hover over the table above and click "Interactive" to enable sorting and filtering!

## Employee Directory

Here's our employee information. The interactive version allows you to:
- Sort by any column (click column headers)
- Filter rows using the search box
- See the default sort applied (by Salary, descending)

| Name          | Department   | Salary | Years |
|---------------|--------------|--------|-------|
| Alice Smith   | Sales        | 75000  | 3     |
| Bob Johnson   | Engineering  | 95000  | 5     |
| Charlie Brown | Marketing    | 68000  | 2     |
| Diana Prince  | HR           | 72000  | 7     |
| Eve Adams     | Engineering  | 88000  | 4     |

: Employee Information {#tbl:employee_data}

## How It Works

The interactive table feature works similarly to interactive plots:

1. **Static Mode**: Shows the rendered markdown table from the document
2. **Interactive Mode**: Shows a sortable, filterable table loaded from the database
3. **Toggle**: Hover over the table to see the mode selector

This gives you the best of both worlds - clean printed output and interactive exploration!
"""

    # Create document
    doc = OneDoc(
        name="Interactive Tables Demo",
        content=markdown_content,
        db_manager=db
    )

    # Send to frontend
    print("Sending document to frontend...")
    print("Make sure the frontend is running on http://localhost:5173")
    print("\nTo test:")
    print("1. Hover over either table")
    print("2. Click 'Interactive' to switch to the interactive version")
    print("3. Try sorting by clicking column headers")
    print("4. Try filtering using the search box")
    print("5. Click 'Static' to return to the markdown rendered table")

    doc.send_to_frontend(
        use_static_html=True,
        open_browser=True
    )

if __name__ == "__main__":
    main()

