"""Test that table keys are unique when tables are reused with different filters/sorts."""
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from paradoc import OneDoc
from paradoc.db import dataframe_to_table_data


def test_unique_table_keys_on_reuse(tmp_path):
    """Verify that reused tables get unique keys (_1, _2, etc.)."""

    # Setup test directory
    test_dir = tmp_path / "test_unique_keys"
    test_dir.mkdir()
    main_dir = test_dir / "00-main"
    main_dir.mkdir()

    # Create markdown with multiple uses of same table
    markdown_content = """# Test Document

## First Use (no annotation)
{{__test_table__}}

## Second Use (sorted)
{{__test_table__}}{tbl:sortby:Value:desc}

## Third Use (filtered)
{{__test_table__}}{tbl:filter:Item}

## Fourth Use (index hidden)
{{__test_table__}}{tbl:index:no}
"""

    md_file = main_dir / "test.md"
    md_file.write_text(markdown_content)

    # Initialize OneDoc
    one = OneDoc(source_dir=test_dir, work_dir=tmp_path / "work")

    # Add test table to database
    df = pd.DataFrame({
        'Name': ['Item A', 'Item B', 'Item C'],
        'Value': [100, 200, 150]
    })

    table_data = dataframe_to_table_data(
        key='test_table',
        df=df,
        caption='Test Table',
        show_index=True
    )

    one.db_manager.add_table(table_data)

    # Compile to HTML
    one.compile("test_output", export_format="html")

    # Read generated markdown
    build_file = tmp_path / "work" / "_build" / "00-main" / "test.md"
    generated_md = build_file.read_text()

    # Verify unique keys are generated
    assert "{#tbl:test_table}" in generated_md, "First use should have original key"
    assert "{#tbl:test_table_1}" in generated_md, "Second use should have _1 suffix"
    assert "{#tbl:test_table_2}" in generated_md, "Third use should have _2 suffix"
    assert "{#tbl:test_table_3}" in generated_md, "Fourth use should have _3 suffix"

    # Verify all occurrences are unique
    import re
    table_keys = re.findall(r'\{#tbl:test_table[^}]*\}', generated_md)
    assert len(table_keys) == 4, "Should have exactly 4 table references"
    assert len(set(table_keys)) == 4, "All table keys should be unique"


def test_different_tables_no_suffix(tmp_path):
    """Verify that different tables don't get suffixes."""

    # Setup test directory
    test_dir = tmp_path / "test_different_tables"
    test_dir.mkdir()
    main_dir = test_dir / "00-main"
    main_dir.mkdir()

    # Create markdown with different tables
    markdown_content = """# Test Document

## Table A
{{__table_a__}}

## Table B
{{__table_b__}}
"""

    md_file = main_dir / "test.md"
    md_file.write_text(markdown_content)

    # Initialize OneDoc
    one = OneDoc(source_dir=test_dir, work_dir=tmp_path / "work")

    # Add two different tables
    for key, caption in [('table_a', 'Table A'), ('table_b', 'Table B')]:
        df = pd.DataFrame({'Col': [1, 2, 3]})
        table_data = dataframe_to_table_data(key=key, df=df, caption=caption)
        one.db_manager.add_table(table_data)

    # Compile
    one.compile("test_output", export_format="html")

    # Read generated markdown
    build_file = tmp_path / "work" / "_build" / "00-main" / "test.md"
    generated_md = build_file.read_text()

    # Verify no suffixes for different tables
    assert "{#tbl:table_a}" in generated_md
    assert "{#tbl:table_b}" in generated_md
    assert "{#tbl:table_a_1}" not in generated_md
    assert "{#tbl:table_b_1}" not in generated_md

