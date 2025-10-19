"""Debug the full flow."""
import pandas as pd
from pathlib import Path

from paradoc import OneDoc
from paradoc.db import dataframe_to_table_data

# Create test dir
test_dir = Path("temp/debug_test")
test_dir.mkdir(parents=True, exist_ok=True)
(test_dir / "00-main").mkdir(exist_ok=True)

# Create markdown with annotation
md_content = """# Test

## Sorted Table
{{__test_data__}}{tbl:sortby:Sales:desc;index:no}
"""

(test_dir / "00-main" / "test.md").write_text(md_content)

# Create OneDoc
one = OneDoc(test_dir, work_dir="temp/debug_work")

# Add data to database
df = pd.DataFrame({
    'Name': ['Alice', 'Bob', 'Charlie'],
    'Sales': [95000, 50000, 125000]
})

table_data = dataframe_to_table_data('test_data', df, 'Test Table', show_index=True)
one.db_manager.add_table(table_data)

print("Original data in database:")
print(df)
print()

# Compile
one.compile("TestDoc", export_format="html")

# Check the result
build_file = Path("temp/debug_work/_build/00-main/test.md")
content = build_file.read_text()
print("Generated markdown:")
print(content)

