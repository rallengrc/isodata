"""Check Parquet file schema."""
import pandas as pd
from pathlib import Path

parquet_dir = Path("data/parquet")
files = list(parquet_dir.rglob("*.parquet"))

if files:
    print(f"Found {len(files)} Parquet file(s)")
    df = pd.read_parquet(files[0])
    print(f"\nColumns ({len(df.columns)}):")
    for col in df.columns:
        print(f"  - {col}")
    
    print(f"\nSample data (first 3 rows):")
    cols_to_show = ['auction_month', 'delivery_month', 'zone', 'zone_normalized', 'zone_original', 'data_quality_score']
    available_cols = [c for c in cols_to_show if c in df.columns]
    if available_cols:
        print(df[available_cols].head(3).to_string())
    else:
        print("New columns not found - showing all columns:")
        print(df.head(3).to_string())
    
    print(f"\nTotal rows: {len(df)}")
    if 'zone' in df.columns:
        print(f"\nUnique zones: {df['zone'].unique()[:10]}")
else:
    print("No Parquet files found")

