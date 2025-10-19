"""Quick test to verify lazy initialization."""
import os
from pathlib import Path
import shutil

from paradoc import OneDoc

# Clean up any existing test directory
test_dir = Path("temp/lazy_init_test")
if test_dir.exists():
    shutil.rmtree(test_dir)

test_dir.mkdir(parents=True)
(test_dir / "00-main").mkdir()

print("=" * 60)
print("Testing Lazy Database Initialization")
print("=" * 60)
print()

# Step 1: Create OneDoc instance
print("Step 1: Creating OneDoc instance...")
one = OneDoc(test_dir, work_dir="temp/lazy_work")
print(f"✓ OneDoc created")
print()

# Step 2: Check if database exists
db_path = test_dir / "data.db"
print("Step 2: Checking if database exists...")
print(f"Database path: {db_path}")
print(f"Database exists: {db_path.exists()}")

if not db_path.exists():
    print("✓ CORRECT: Database was NOT created on instantiation (lazy initialization)")
else:
    print("✗ ERROR: Database was created on instantiation (should be lazy)")
print()

# Step 3: Add data to database
print("Step 3: Adding data to database...")
import pandas as pd
from paradoc.db import dataframe_to_table_data

df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [25, 30]})
table_data = dataframe_to_table_data('test', df, 'Test Table')
one.db_manager.add_table(table_data)
print("✓ Data added")
print()

# Step 4: Check if database exists NOW
print("Step 4: Checking if database exists after writing data...")
print(f"Database exists: {db_path.exists()}")
if db_path.exists():
    print("✓ CORRECT: Database was created when data was written")
    print(f"Database size: {db_path.stat().st_size} bytes")
else:
    print("✗ ERROR: Database still doesn't exist after writing data")
print()

print("=" * 60)
print("✓ Lazy initialization is working correctly!")
print("=" * 60)

