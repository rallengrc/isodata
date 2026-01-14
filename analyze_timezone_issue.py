#!/usr/bin/env python3
"""
Analyze timezone issues between NYISO and EIA data.
"""

import pandas as pd
from pathlib import Path
import pytz

print("=" * 80)
print("Timezone Analysis: NYISO vs EIA")
print("=" * 80)
print()

# Load NYISO data
nyiso_file = Path('data/parquet/NYISO/ENERGY/2024/01/data_2024_01.parquet')
if nyiso_file.exists():
    df_nyiso = pd.read_parquet(nyiso_file)
    print("NYISO Data:")
    print(f"  Shape: {df_nyiso.shape}")
    print(f"  Columns: {list(df_nyiso.columns)}")
    print(f"  start_time dtype: {df_nyiso['start_time'].dtype}")
    print(f"  start_time timezone: {df_nyiso['start_time'].dt.tz}")
    print(f"  Sample start_time values:")
    print(df_nyiso[['start_time', 'end_time', 'zone', 'price']].head(5))
    print()
else:
    print("NYISO file not found")
    df_nyiso = pd.DataFrame()

# Load EIA data
eia_files = list(Path('data/parquet/EIA/ENERGY').glob('**/*.parquet'))
if eia_files:
    df_eia = pd.read_parquet(eia_files[0])
    print("EIA Data:")
    print(f"  Shape: {df_eia.shape}")
    print(f"  Columns: {list(df_eia.columns)}")
    print(f"  start_time dtype: {df_eia['start_time'].dtype}")
    print(f"  start_time timezone: {df_eia['start_time'].dt.tz}")
    print(f"  Sample start_time values:")
    print(df_eia[['start_time', 'end_time', 'zone', 'price']].head(5))
    print()
else:
    print("EIA files not found")
    df_eia = pd.DataFrame()

# Compare timezones
if not df_nyiso.empty and not df_eia.empty:
    print("=" * 80)
    print("Timezone Comparison:")
    print("=" * 80)
    
    nyiso_tz = df_nyiso['start_time'].dt.tz
    eia_tz = df_eia['start_time'].dt.tz
    
    print(f"NYISO timezone: {nyiso_tz}")
    print(f"EIA timezone: {eia_tz}")
    print()
    
    # Check date ranges
    print("Date Ranges:")
    print(f"NYISO: {df_nyiso['start_time'].min()} to {df_nyiso['start_time'].max()}")
    print(f"EIA:   {df_eia['start_time'].min()} to {df_eia['start_time'].max()}")
    print()
    
    # Try to align and compare
    print("=" * 80)
    print("Attempting to Align Timestamps:")
    print("=" * 80)
    
    # Normalize both to UTC for comparison
    nyiso_utc = df_nyiso['start_time'].dt.tz_convert('UTC') if nyiso_tz else df_nyiso['start_time']
    eia_utc = df_eia['start_time'].dt.tz_localize('UTC') if eia_tz is None else df_eia['start_time'].dt.tz_convert('UTC')
    
    # Create comparison
    nyiso_sample = df_nyiso[['start_time', 'zone', 'price']].copy()
    nyiso_sample['start_time_utc'] = nyiso_utc
    nyiso_sample = nyiso_sample.groupby('start_time_utc')['price'].mean().reset_index()
    nyiso_sample.columns = ['timestamp_utc', 'nyiso_avg_price']
    
    eia_sample = df_eia[['start_time', 'price']].copy()
    eia_sample['timestamp_utc'] = eia_utc
    eia_sample = eia_sample.rename(columns={'price': 'eia_price'})[['timestamp_utc', 'eia_price']]
    
    # Merge
    comparison = pd.merge(nyiso_sample, eia_sample, on='timestamp_utc', how='inner')
    
    if not comparison.empty:
        print(f"Aligned {len(comparison)} timestamps")
        print()
        print("Sample Comparison (first 10 rows):")
        print(comparison.head(10))
        print()
        print("Statistics:")
        print(f"  NYISO avg price: ${comparison['nyiso_avg_price'].mean():.2f}/MWh")
        print(f"  EIA price: ${comparison['eia_price'].mean():.2f}/MWh")
        print(f"  Difference: ${abs(comparison['nyiso_avg_price'].mean() - comparison['eia_price'].mean()):.2f}/MWh")
    else:
        print("No overlapping timestamps found after alignment")
    
    print()
    print("=" * 80)
    print("Other Inconsistencies:")
    print("=" * 80)
    
    # Check zone granularity
    print(f"NYISO zones: {df_nyiso['zone'].nunique()} unique zones")
    print(f"EIA zones: {df_eia['zone'].nunique()} unique zones")
    print(f"NYISO zones: {sorted(df_nyiso['zone'].unique())}")
    print(f"EIA zones: {sorted(df_eia['zone'].unique())}")
    print()
    
    # Check price ranges
    print("Price Statistics:")
    print(f"NYISO price range: ${df_nyiso['price'].min():.2f} - ${df_nyiso['price'].max():.2f}/MWh")
    print(f"EIA price range: ${df_eia['price'].min():.2f} - ${df_eia['price'].max():.2f}/MWh")
    print()
    
    # Check data completeness
    print("Data Completeness:")
    print(f"NYISO records: {len(df_nyiso)}")
    print(f"EIA records: {len(df_eia)}")
    print(f"NYISO unique timestamps: {df_nyiso['start_time'].nunique()}")
    print(f"EIA unique timestamps: {df_eia['start_time'].nunique()}")

