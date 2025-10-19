"""Test annotation parsing and application."""
import pandas as pd
from paradoc.db.utils import parse_table_reference, apply_table_annotation

# Test 1: Parse a complex annotation
reference = '{{__employee_data__}}{tbl:sortby:Sales:desc;filter:^((?!25000).)*$;index:no}'
print("Testing annotation parsing...")
print(f"Reference: {reference}")

key, annotation = parse_table_reference(reference)
print(f"Key: {key}")
print(f"Annotation: {annotation}")
if annotation:
    print(f"  - show_index: {annotation.show_index}")
    print(f"  - sort_by: {annotation.sort_by}")
    print(f"  - sort_ascending: {annotation.sort_ascending}")
    print(f"  - filter_pattern: {annotation.filter_pattern}")

# Test 2: Apply annotation to DataFrame
print("\nTesting annotation application...")
df = pd.DataFrame({
    'Name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
    'Sales': [95000, 0, 87000, 0, 125000],
    'Location': ['New York', 'Boston', 'Chicago', 'New York', 'Seattle']
})

print("\nOriginal DataFrame:")
print(df)

df_transformed, show_index = apply_table_annotation(df, annotation, default_show_index=True)

print(f"\nTransformed DataFrame (should be sorted by Sales desc, filtered):")
print(df_transformed)
print(f"Show index: {show_index}")

# Test 3: New York filter
reference2 = '{{__employee_data__}}{tbl:filter:New York;sortby:Name;index:no}'
key2, annotation2 = parse_table_reference(reference2)
print(f"\n\nTest 2 - Filter: {reference2}")
print(f"Annotation: {annotation2}")
if annotation2:
    print(f"  - filter_pattern: {annotation2.filter_pattern}")
    print(f"  - sort_by: {annotation2.sort_by}")

df_transformed2, show_index2 = apply_table_annotation(df, annotation2, default_show_index=True)
print(f"\nTransformed DataFrame (filter New York, sort by Name):")
print(df_transformed2)

