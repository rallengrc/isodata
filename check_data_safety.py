#!/usr/bin/env python3
"""
Verify that refresh_views() does NOT delete Parquet files.
This script demonstrates that views are just SQL queries, not data storage.
"""

from pathlib import Path
import duckdb
from storage.duckdb_views import DuckDBViews

# Check Parquet files BEFORE refreshing views
parquet_base = Path('data/parquet')
parquet_files_before = list(parquet_base.rglob("*.parquet"))
print(f"Parquet files BEFORE refresh_views(): {len(parquet_files_before)}")
if parquet_files_before:
    print(f"  Sample: {parquet_files_before[0]}")

# Refresh views (this should NOT delete any files)
duckdb_path = Path('analytics_db/analytics.duckdb')
views = DuckDBViews(duckdb_path, parquet_base)
views.refresh_views()
views.close()

# Check Parquet files AFTER refreshing views
parquet_files_after = list(parquet_base.rglob("*.parquet"))
print(f"\nParquet files AFTER refresh_views(): {len(parquet_files_after)}")
if parquet_files_after:
    print(f"  Sample: {parquet_files_after[0]}")

# Verify no files were deleted
if len(parquet_files_before) == len(parquet_files_after):
    print("\n✓ SUCCESS: No Parquet files were deleted!")
    print("  refresh_views() only updates SQL view definitions, not your data.")
else:
    print(f"\n⚠ WARNING: File count changed from {len(parquet_files_before)} to {len(parquet_files_after)}")
    print("  This should NOT happen - refresh_views() should not delete files!")

# Show what a view actually is
print("\n" + "="*60)
print("What is a DuckDB view?")
print("="*60)
con = duckdb.connect(str(duckdb_path))
try:
    # Get the view definition
    view_def = con.execute("SELECT sql FROM duckdb_views() WHERE view_name = 'market_prices'").fetchone()
    if view_def:
        print("\nThe 'market_prices' view is just this SQL query:")
        print(view_def[0])
        print("\nIt reads from your Parquet files - it does NOT store data!")
except Exception as e:
    print(f"Could not get view definition: {e}")
finally:
    con.close()

print("\n" + "="*60)
print("Summary:")
print("="*60)
print("• Parquet files in data/parquet/ = YOUR ACTUAL DATA (persistent)")
print("• DuckDB views = SQL queries that read from Parquet files")
print("• refresh_views() = Updates the SQL query, NOT your data files")
print("• Your data accumulates over time and is NEVER deleted by refresh_views()")
