"""A table's text cells reach the document as written: numbers kept to their written decimals, and a cell
starting with ">" not read as a block quote."""

import pandas as pd
import pypandoc

from paradoc.common import Table


def _table() -> Table:
    df = pd.DataFrame(
        {
            "Check": ["weld", "member"],
            "Utilization": ["0.30", "1.50"],  # text, written to two decimals
            "Range": [">= 0.25", "<= 35"],
            "Value": [0.125, 2.0],  # numbers stay numbers
        }
    )
    return Table("checks", df, "Checks")


def test_text_cells_keep_their_decimals_and_numbers_are_formatted_as_before():
    md = _table().to_markdown()
    assert "0.30" in md and "1.50" in md
    assert "0.125" in md and "| 2 " in md


def test_a_cell_starting_with_a_greater_than_sign_is_not_a_block_quote():
    md = _table().to_markdown()
    html = pypandoc.convert_text(md, "html", format="markdown")
    assert "<blockquote" not in html
    assert "&gt;= 0.25" in html and "&lt;= 35" in html
