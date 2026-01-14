"""Test DuckDB schema reading."""
import duckdb
from pathlib import Path

con = duckdb.connect('analytics_db/analytics.duckdb')

# Find parquet files
files = list(Path('data/parquet').rglob('*.parquet'))
print(f"Found {len(files)} Parquet file(s)")

if files:
    file_path = str(files[0]).replace('\\', '/')
    print(f"\nReading file: {file_path}")
    
    # Try reading directly
    df = con.execute(f"SELECT * FROM read_parquet('{file_path}') LIMIT 1").df()
    print(f"\nColumns in file ({len(df.columns)}):")
    for col in df.columns:
        print(f"  - {col}")
    
    # Try selecting new columns
    try:
        df2 = con.execute(f"""
            SELECT auction_month, delivery_month, zone, zone_normalized, zone_original, data_quality_score 
            FROM read_parquet('{file_path}') 
            LIMIT 5
        """).df()
        print("\n✓ New columns readable directly from file:")
        print(df2.to_string())
    except Exception as e:
        print(f"\n✗ Error reading new columns: {e}")

# Check view
print("\n" + "="*60)
print("Checking view schema:")
try:
    df_view = con.execute("SELECT * FROM market_prices LIMIT 1").df()
    print(f"View columns ({len(df_view.columns)}):")
    for col in df_view.columns:
        print(f"  - {col}")
except Exception as e:
    print(f"Error reading view: {e}")

con.close()

