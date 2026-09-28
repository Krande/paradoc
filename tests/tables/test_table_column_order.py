"""A table read back from the database keeps the column order it was written with.

The columns query used to have no ORDER BY, so SQLite answered it from the UNIQUE(table_key, name)
index and the columns came back alphabetically -- a "closed form" reference column written last
landed between two solver columns.
"""

import pandas as pd

from paradoc.db import DbManager, dataframe_to_table_data


def test_get_table_keeps_written_column_order(tmp_path):
    columns = ["Seed [m]", "ses", "aba", "closed form", "ca"]
    df = pd.DataFrame([[0.125, 1.0, 2.0, 3.0, 4.0], [0.0625, 5.0, 6.0, 7.0, 8.0]], columns=columns)

    db = DbManager(tmp_path / "paradoc.sqlite")
    db.add_table(dataframe_to_table_data(key="t", df=df, caption="x", show_index=False))

    table = db.get_table("t")
    assert [c.name for c in table.columns] == columns
    for row in (0, 1):
        assert [c.column_name for c in table.cells if c.row_index == row] == columns
