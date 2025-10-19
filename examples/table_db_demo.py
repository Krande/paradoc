"""Example script demonstrating table database usage."""
import pandas as pd

from paradoc.db import DbManager, dataframe_to_table_data, parse_table_reference


def main():
    """Demonstrate table database functionality."""

    # Create a database manager
    db = DbManager("examples/temp/interactive_data.db")

    # Example 1: Create and store a simple table
    print("=" * 60)
    print("Example 1: Adding tables to database")
    print("=" * 60)

    df1 = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie', 'Diana'],
        'Age': [25, 30, 35, 28],
        'City': ['New York', 'Boston', 'Chicago', 'Seattle']
    })

    table_data1 = dataframe_to_table_data(
        key='my_table',
        df=df1,
        caption='Employee Information',
        show_index=False
    )

    db.add_table(table_data1)
    print(f"✓ Added table: {table_data1.key}")

    # Example 2: Create another table with numeric data
    df2 = pd.DataFrame({
        'Product': ['Widget A', 'Widget B', 'Widget C'],
        'Sales': [1200, 850, 2100],
        'Profit': [450.50, 320.25, 890.75]
    })

    table_data2 = dataframe_to_table_data(
        key='my_table_3',
        df=df2,
        caption='Sales Data',
        show_index=True
    )

    db.add_table(table_data2)
    print(f"✓ Added table: {table_data2.key}")

    # Example 3: List all tables
    print("\n" + "=" * 60)
    print("Example 2: Listing all tables in database")
    print("=" * 60)

    all_tables = db.list_tables()
    print(f"Tables in database: {all_tables}")

    # Example 4: Retrieve and display a table
    print("\n" + "=" * 60)
    print("Example 3: Retrieving table from database")
    print("=" * 60)

    retrieved = db.get_table('my_table')
    if retrieved:
        print(f"Table Key: {retrieved.key}")
        print(f"Caption: {retrieved.caption}")
        print(f"Columns: {[col.name for col in retrieved.columns]}")
        print(f"Number of rows: {len(set(cell.row_index for cell in retrieved.cells))}")
        print(f"Show index by default: {retrieved.show_index_default}")

    # Example 5: Parse markdown table references
    print("\n" + "=" * 60)
    print("Example 4: Parsing markdown table references")
    print("=" * 60)

    examples = [
        '{{__my_table__}}',
        '{{__my_table__}}{tbl:index:no}',
        '{{__my_table__}}{tbl:sortby:Age}',
        '{{__my_table__}}{tbl:sortby:Age:desc}',
        '{{__my_table__}}{tbl:index:no;sortby:Name;filter:.*York.*}',
    ]

    for example in examples:
        key, annotation = parse_table_reference(example)
        print(f"\nMarkdown: {example}")
        print(f"  → Table key: {key}")
        if annotation:
            print(f"  → Show index: {annotation.show_index}")
            if annotation.sort_by:
                print(f"  → Sort by: {annotation.sort_by} ({'asc' if annotation.sort_ascending else 'desc'})")
            if annotation.filter_pattern:
                print(f"  → Filter: {annotation.filter_pattern}")

    # Example 6: Apply annotations to modify table display
    print("\n" + "=" * 60)
    print("Example 5: Applying annotations to tables")
    print("=" * 60)

    from paradoc.db import apply_table_annotation, table_data_to_dataframe

    # Get the original dataframe
    table_from_db = db.get_table('my_table')
    df_original = table_data_to_dataframe(table_from_db)

    print("\nOriginal table:")
    print(df_original)

    # Apply sorting annotation
    from paradoc.db.models import TableAnnotation
    annotation = TableAnnotation(sort_by='Age', sort_ascending=False, show_index=False)
    df_sorted, show_idx = apply_table_annotation(df_original, annotation)

    print("\nAfter applying {tbl:sortby:Age:desc;index:no}:")
    print(df_sorted)
    print(f"Show index: {show_idx}")

    # Apply filtering annotation
    annotation2 = TableAnnotation(filter_pattern='.*e.*', show_index=False)
    df_filtered, show_idx2 = apply_table_annotation(df_original, annotation2)

    print("\nAfter applying {tbl:filter:.*e.*;index:no} (names containing 'e'):")
    print(df_filtered)

    print("\n" + "=" * 60)
    print("✓ All examples completed successfully!")
    print("=" * 60)

    db.close()


if __name__ == '__main__':
    main()

