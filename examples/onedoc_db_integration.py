"""
Example demonstrating database integration with OneDoc.

This example shows how to:
1. Store table data in the database
2. Reference tables in markdown with annotations
3. Compile documents using database tables
"""
import pandas as pd
from pathlib import Path

from paradoc import OneDoc
from paradoc.db import dataframe_to_table_data


def setup_example_project(base_dir: Path):
    """Create an example project structure."""
    # Create directories
    main_dir = base_dir / "00-main"
    main_dir.mkdir(parents=True, exist_ok=True)

    # Create a markdown document with table references
    markdown_content = """# Sales Report 2024

## Employee Performance

Here is our complete employee list:

{{__employee_data__}}

## Top Performers

Sorted by sales (highest first), showing only employees with sales over 50K:

{{__employee_data__}}{tbl:sortby:Sales:desc;filter:^((?!25000).)*$;index:no}

## New York Office

Employees in the New York office:

{{__employee_data__}}{tbl:filter:New York;sortby:Name;index:no}

## Summary Table

A simple summary without the index column:

{{__summary_data__}}{tbl:index:no}
"""

    md_file = main_dir / "report.md"
    md_file.write_text(markdown_content)

    print(f"✓ Created example project at {base_dir}")
    print(f"  - Markdown file: {md_file}")


def populate_database(one_doc: OneDoc):
    """Add example tables to the database."""

    # Employee data
    df_employees = pd.DataFrame({
        'Name': ['Alice Johnson', 'Bob Smith', 'Charlie Brown', 'Diana Prince', 'Eve Wilson'],
        'Department': ['Sales', 'Engineering', 'Sales', 'Marketing', 'Sales'],
        'Location': ['New York', 'Boston', 'Chicago', 'New York', 'Seattle'],
        'Sales': [95000, 0, 87000, 0, 125000],
        'Years': [5, 3, 7, 4, 6]
    })

    employee_table = dataframe_to_table_data(
        key='employee_data',
        df=df_employees,
        caption='Employee Directory',
        show_index=True
    )

    one_doc.db_manager.add_table(employee_table)
    print("✓ Added 'employee_data' table to database")

    # Summary data
    df_summary = pd.DataFrame({
        'Metric': ['Total Employees', 'Departments', 'Locations', 'Avg Tenure'],
        'Value': [5, 3, 4, '5 years']
    })

    summary_table = dataframe_to_table_data(
        key='summary_data',
        df=df_summary,
        caption='Summary Statistics',
        show_index=False
    )

    one_doc.db_manager.add_table(summary_table)
    print("✓ Added 'summary_data' table to database")


def main():
    """Run the complete example."""

    # Setup project directory
    example_dir = Path("examples/temp/onedoc_db_example")
    example_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("OneDoc Database Integration Example")
    print("=" * 70)
    print()

    # Step 1: Create project structure
    print("Step 1: Setting up project structure")
    print("-" * 70)
    setup_example_project(example_dir)
    print()

    # Step 2: Initialize OneDoc (this creates data.db)
    print("Step 2: Initializing OneDoc")
    print("-" * 70)
    one = OneDoc(
        source_dir=example_dir,
        work_dir="temp/onedoc_work"  # Use simple relative path
    )

    db_location = example_dir / "data.db"
    print(f"✓ Database created at: {db_location}")
    print()

    # Step 3: Populate database with tables
    print("Step 3: Adding tables to database")
    print("-" * 70)
    populate_database(one)
    print()

    # Step 4: List tables in database
    print("Step 4: Verifying database contents")
    print("-" * 70)
    all_tables = one.db_manager.list_tables()
    print(f"Tables in database: {all_tables}")
    print()

    # Step 5: Compile the document
    print("Step 5: Compiling document with database tables")
    print("-" * 70)
    one.send_to_frontend()
    one.compile("SalesReport", export_format="html")
    print()

    # Step 6: Show what was generated
    print("Step 6: Examining generated markdown")
    print("-" * 70)

    build_file = Path("temp/onedoc_work") / "_build" / "00-main" / "report.md"
    if build_file.exists():
        content = build_file.read_text()

        # Show a snippet
        lines = content.split('\n')
        print(f"Generated markdown has {len(lines)} lines")
        print()
        print("First few lines:")
        for line in lines[:20]:
            print(f"  {line}")
        print("  ...")

    print()
    print("=" * 70)
    print("✓ Example completed successfully!")
    print("=" * 70)
    print()
    print(f"Output files:")
    print(f"  - Database: {db_location}")
    print(f"  - HTML: temp/onedoc_work/_dist/SalesReport.html")
    print(f"  - Markdown: {build_file}")
    print()
    print("Markdown annotations used:")
    print("  - {{__employee_data__}} - Basic table")
    print("  - {{__employee_data__}}{{tbl:sortby:Sales:desc;filter:...}} - Sorted & filtered")
    print("  - {{__employee_data__}}{{tbl:filter:New York;sortby:Name}} - Filtered by location")
    print("  - {{__summary_data__}}{{tbl:index:no}} - Hide index")


if __name__ == '__main__':
    main()
