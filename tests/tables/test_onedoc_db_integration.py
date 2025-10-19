"""Test database integration with OneDoc."""
import pandas as pd
import pytest

from paradoc import OneDoc
from paradoc.db import dataframe_to_table_data


def test_onedoc_db_integration_basic(files_dir, tmp_path):
    """Test that OneDoc can use tables from the database."""
    # Create a test directory structure
    test_dir = tmp_path / "test_db_doc"
    test_dir.mkdir()

    main_dir = test_dir / "00-main"
    main_dir.mkdir()

    # Create a markdown file with table reference
    md_file = main_dir / "test.md"
    md_file.write_text("# Test\n\nHere is my table:\n\n{{__test_table__}}\n")

    # Create OneDoc instance (this will create data.db)
    one = OneDoc(test_dir, work_dir=tmp_path / "work")

    # Add table to database
    df = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie'],
        'Age': [25, 30, 35],
        'City': ['New York', 'Boston', 'Chicago']
    })

    table_data = dataframe_to_table_data(
        key='test_table',
        df=df,
        caption='Test Table',
        show_index=False
    )
    one.db_manager.add_table(table_data)

    # Perform compilation (HTML to avoid DOCX dependencies)
    one.compile("TestDoc", export_format="html")

    # Check that the build file contains the table
    build_file = tmp_path / "work" / "_build" / "00-main" / "test.md"
    assert build_file.exists()

    content = build_file.read_text()
    assert "Alice" in content
    assert "Bob" in content
    assert "Test Table" in content
    assert "tbl:test_table" in content


def test_onedoc_db_with_annotations(files_dir, tmp_path):
    """Test that OneDoc handles table annotations from database."""
    # Create a test directory structure
    test_dir = tmp_path / "test_db_annotations"
    test_dir.mkdir()

    main_dir = test_dir / "00-main"
    main_dir.mkdir()

    # Create a markdown file with annotated table reference
    md_file = main_dir / "test.md"
    md_file.write_text("# Test\n\n{{__annotated_table__}}{tbl:index:no;sortby:Age:desc}\n")

    # Create OneDoc instance
    one = OneDoc(test_dir, work_dir=tmp_path / "work")

    # Add table to database
    df = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie'],
        'Age': [25, 30, 35],
        'City': ['New York', 'Boston', 'Chicago']
    })

    table_data = dataframe_to_table_data(
        key='annotated_table',
        df=df,
        caption='Annotated Table',
        show_index=True  # Default shows index
    )
    one.db_manager.add_table(table_data)

    # Perform compilation
    one.compile("TestDoc", export_format="html")

    # Check that the build file contains sorted data
    build_file = tmp_path / "work" / "_build" / "00-main" / "test.md"
    assert build_file.exists()

    content = build_file.read_text()

    # Should be sorted by Age descending (Charlie, Bob, Alice)
    charlie_pos = content.find("Charlie")
    bob_pos = content.find("Bob")
    alice_pos = content.find("Alice")

    assert charlie_pos < bob_pos < alice_pos, "Table should be sorted by Age descending"

    # Should NOT have index (annotation says index:no)
    # This is harder to verify in markdown, but the table should not have a leading column


def test_onedoc_db_prefers_database_over_memory(files_dir, tmp_path):
    """Test that database tables are preferred over in-memory tables."""
    # Create a test directory structure
    test_dir = tmp_path / "test_db_priority"
    test_dir.mkdir()

    main_dir = test_dir / "00-main"
    main_dir.mkdir()

    # Create a markdown file
    md_file = main_dir / "test.md"
    md_file.write_text("# Test\n\n{{__priority_table__}}\n")

    # Create OneDoc instance
    one = OneDoc(test_dir, work_dir=tmp_path / "work")

    # Add table to database
    df_db = pd.DataFrame({
        'Source': ['Database'],
        'Value': [100]
    })

    table_data = dataframe_to_table_data(
        key='priority_table',
        df=df_db,
        caption='From Database',
        show_index=False
    )
    one.db_manager.add_table(table_data)

    # Also add to in-memory (this should be ignored)
    df_memory = pd.DataFrame({
        'Source': ['Memory'],
        'Value': [200]
    })
    one.add_table('priority_table', df_memory, 'From Memory')

    # Perform compilation
    one.compile("TestDoc", export_format="html")

    # Check that database version was used
    build_file = tmp_path / "work" / "_build" / "00-main" / "test.md"
    content = build_file.read_text()

    assert "Database" in content
    assert "From Database" in content
    assert "Memory" not in content or content.count("Memory") == 0  # Memory version should not appear


def test_onedoc_db_location(files_dir, tmp_path):
    """Test that database is only created when data is written to it."""
    test_dir = tmp_path / "test_db_location"
    test_dir.mkdir()

    main_dir = test_dir / "00-main"
    main_dir.mkdir()

    # Create OneDoc instance
    one = OneDoc(test_dir, work_dir=tmp_path / "work")

    # Check that database does NOT exist yet (lazy initialization)
    db_path = test_dir / "data.db"
    assert not db_path.exists(), f"Database should NOT be created until data is written"

    # Now add data to the database
    df = pd.DataFrame({'col': [1, 2, 3]})
    table_data = dataframe_to_table_data('test_table', df, 'Test')
    one.db_manager.add_table(table_data)

    # NOW the database should exist
    assert db_path.exists(), f"Database should be created at {db_path} after writing data"

    # Verify it's a valid database by querying it
    tables = one.db_manager.list_tables()
    assert 'test_table' in tables


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
