from dataclasses import dataclass
import pandas as pd
from .formatting import TableFormat


@dataclass
class Table:
    name: str
    df: pd.DataFrame
    caption: str
    format: TableFormat = TableFormat()

    def to_markdown(self, include_name_in_cell=False):
        df = self.df.copy()
        if include_name_in_cell:
            col_name = df.columns[0]
            df.iloc[0, df.columns.get_loc(col_name)] = self.name
        tbl_str = df.to_markdown(index=False, tablefmt="grid")
        tbl_str += f"\nTable: {self.caption}"
        return tbl_str
