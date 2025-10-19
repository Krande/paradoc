"""Tests for the table database functionality."""
import pandas as pd
import pytest

from paradoc.db import (
    DbManager,
    TableAnnotation,
    apply_table_annotation,
    dataframe_to_table_data,
    parse_table_reference,
    table_data_to_dataframe,
)


def test_dataframe_to_table_data_and_back():
    """Test conversion between DataFrame and TableData."""
    df = pd.DataFrame({
        'a': [1, 2, 3],
        'b': [4.5, 5.5, 6.5],
        'c': ['x', 'y', 'z']
    })

    table_data = dataframe_to_table_data('test_table', df, 'Test Caption')

    assert table_data.key == 'test_table'
    assert table_data.caption == 'Test Caption'
    assert len(table_data.columns) == 3
    assert len(table_data.cells) == 9  # 3 rows x 3 columns

    # Convert back
    df_result = table_data_to_dataframe(table_data)
    # Compare values, allowing for dtype differences (int64 vs Int64)
    assert df_result.shape == df.shape
    assert list(df_result.columns) == list(df.columns)
    for col in df.columns:
        assert list(df_result[col].astype(str)) == list(df[col].astype(str))


def test_db_manager_add_and_get_table(tmp_path):
    """Test adding and retrieving tables from database."""
    db_path = tmp_path / "test.db"

    with DbManager(db_path) as db:
        df = pd.DataFrame({
            'col1': [1, 2],
            'col2': [3, 4]
        })

        table_data = dataframe_to_table_data('my_table', df, 'My Test Table')
        db.add_table(table_data)

        # Retrieve it
        retrieved = db.get_table('my_table')
        assert retrieved is not None
        assert retrieved.key == 'my_table'
        assert retrieved.caption == 'My Test Table'
        assert len(retrieved.columns) == 2
        assert len(retrieved.cells) == 4


def test_db_manager_list_tables(tmp_path):
    """Test listing all tables."""
    db_path = tmp_path / "test.db"

    with DbManager(db_path) as db:
        df1 = pd.DataFrame({'a': [1, 2]})
        df2 = pd.DataFrame({'b': [3, 4]})

        db.add_table(dataframe_to_table_data('table1', df1, 'Table 1'))
        db.add_table(dataframe_to_table_data('table2', df2, 'Table 2'))

        tables = db.list_tables()
        assert len(tables) == 2
        assert 'table1' in tables
        assert 'table2' in tables


def test_db_manager_delete_table(tmp_path):
    """Test deleting a table."""
    db_path = tmp_path / "test.db"

    with DbManager(db_path) as db:
        df = pd.DataFrame({'a': [1, 2]})
        db.add_table(dataframe_to_table_data('table_to_delete', df, 'Delete Me'))

        assert 'table_to_delete' in db.list_tables()

        db.delete_table('table_to_delete')
        assert 'table_to_delete' not in db.list_tables()


def test_parse_table_reference_simple():
    """Test parsing simple table reference."""
    key, annotation = parse_table_reference('{{__my_table__}}')

    assert key == 'my_table'
    assert annotation is None


def test_parse_table_reference_with_annotation():
    """Test parsing table reference with annotation."""
    key, annotation = parse_table_reference('{{__my_table__}}{tbl:index:no}')

    assert key == 'my_table'
    assert annotation is not None
    assert annotation.show_index is False


def test_parse_table_reference_with_sortby():
    """Test parsing table reference with sortby annotation."""
    key, annotation = parse_table_reference('{{__my_table__}}{tbl:sortby:column_a}')

    assert key == 'my_table'
    assert annotation is not None
    assert annotation.sort_by == 'column_a'
    assert annotation.sort_ascending is True


def test_parse_table_reference_with_sortby_desc():
    """Test parsing table reference with descending sort."""
    key, annotation = parse_table_reference('{{__my_table__}}{tbl:sortby:column_a:desc}')

    assert key == 'my_table'
    assert annotation is not None
    assert annotation.sort_by == 'column_a'
    assert annotation.sort_ascending is False


def test_parse_table_reference_multiple_options():
    """Test parsing table reference with multiple options."""
    key, annotation = parse_table_reference('{{__my_table__}}{tbl:index:no;sortby:col_b;filter:.*test.*}')

    assert key == 'my_table'
    assert annotation is not None
    assert annotation.show_index is False
    assert annotation.sort_by == 'col_b'
    assert annotation.filter_pattern == '.*test.*'


def test_table_annotation_from_string():
    """Test TableAnnotation parsing from string."""
    annotation = TableAnnotation.from_annotation_string('{tbl:index:no;sortby:name:desc}')

    assert annotation.show_index is False
    assert annotation.sort_by == 'name'
    assert annotation.sort_ascending is False


def test_apply_table_annotation_sorting():
    """Test applying sorting annotation."""
    df = pd.DataFrame({
        'name': ['Bob', 'Alice', 'Charlie'],
        'age': [30, 25, 35]
    })

    annotation = TableAnnotation(sort_by='name', sort_ascending=True)
    df_result, show_index = apply_table_annotation(df, annotation)

    assert df_result.iloc[0]['name'] == 'Alice'
    assert df_result.iloc[1]['name'] == 'Bob'
    assert df_result.iloc[2]['name'] == 'Charlie'


def test_apply_table_annotation_filtering():
    """Test applying filtering annotation."""
    df = pd.DataFrame({
        'name': ['Alice', 'Bob', 'Charlie'],
        'city': ['New York', 'Boston', 'New Haven']
    })

    annotation = TableAnnotation(filter_pattern='New.*')
    df_result, show_index = apply_table_annotation(df, annotation)

    assert len(df_result) == 2  # Alice and Charlie
    assert 'Bob' not in df_result['name'].values


def test_apply_table_annotation_index_visibility():
    """Test index visibility from annotation."""
    df = pd.DataFrame({'a': [1, 2, 3]})

    annotation = TableAnnotation(show_index=False)
    df_result, show_index = apply_table_annotation(df, annotation, default_show_index=True)

    assert show_index is False


def test_db_manager_with_sort_and_filter_config(tmp_path):
    """Test storing tables with sort and filter configurations."""
    db_path = tmp_path / "test.db"

    with DbManager(db_path) as db:
        df = pd.DataFrame({
            'name': ['Alice', 'Bob'],
            'score': [95, 87]
        })

        table_data = dataframe_to_table_data('scored_table', df, 'Scores')
        table_data.default_sort = {'column_name': 'score', 'ascending': False}

        from paradoc.db.models import TableSortConfig
        table_data.default_sort = TableSortConfig(column_name='score', ascending=False)

        db.add_table(table_data)

        # Retrieve and verify
        retrieved = db.get_table('scored_table')
        assert retrieved.default_sort is not None
        assert retrieved.default_sort.column_name == 'score'
        assert retrieved.default_sort.ascending is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
