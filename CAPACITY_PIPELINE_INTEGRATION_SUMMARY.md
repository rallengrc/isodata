# Capacity Pipeline Integration - Complete ✅

## Summary

Full integration of NYISO ICAP capacity market data into the pipeline is **complete and working**.

## What Was Implemented

### 1. ✅ Capacity Pipeline (`pipelines/capacity_pipeline.py`)
- `run_capacity_pipeline()` - Main pipeline function
- `backfill_capacity_data()` - Historical data backfill (by capability periods)
- Logs to SQLite metadata
- Writes to Parquet with validation
- Refreshes DuckDB views

### 2. ✅ CLI Integration (`run_pipeline.py`)
- Added `--capacity` flag
- Added `--auction-type` argument (MONTHLY, STRIP)
- Smart defaults for capability periods
- Full backfill support

### 3. ✅ ISODataAdapter Extension (`adapters/nyiso_compat.py`)
- Added capacity dataset types: `capacity_monthly`, `capacity_strip`, `icap_monthly`, `icap_strip`
- `_transform_capacity_to_nyiso_format()` - Uses delivery_month as time index
- Updated `_load_from_duckdb()` to handle capacity data
- Updated `_load_from_parquet()` to search across years for capacity data

## Usage

### Fetch Capacity Data
```bash
# Fetch Winter 2023-2024 capacity data
python run_pipeline.py --capacity --iso NYISO --start-date 2023-11-01 --end-date 2024-04-30 --auction-type MONTHLY

# Fetch current capability period (defaults if dates not specified)
python run_pipeline.py --capacity --iso NYISO --auction-type MONTHLY

# Backfill historical data
python run_pipeline.py --capacity --iso NYISO --backfill --start-year 2020 --auction-type MONTHLY
```

### Visualize Capacity Data
```python
from adapters.nyiso_compat import create_iso_data_adapter
from pathlib import Path

# Load capacity data in NYISOToolkit format
adapter = create_iso_data_adapter(
    iso_code='NYISO',
    dataset='capacity_monthly',
    year=2024,
    parquet_base=Path('data/parquet'),
    duckdb_path=Path('analytics_db/analytics.duckdb')
)

df = adapter.df
print(df.head())
# Output: Monthly time series with MultiIndex columns
# Index: delivery_datetime (first day of each month)
# Columns: ('Capacity Price ($/kW-month)', 'NYC'), etc.
```

## Data Structure

### Storage
- **Parquet**: `data/parquet/NYISO/CAPACITY/{year}/{month}/data_{year}_{month}.parquet`
- **DuckDB**: Views automatically include capacity data
- **SQLite**: Metadata logged with `dataset_name = "capacity_monthly_nyiso"`

### Transformation
- **Time Index**: `delivery_month` (YYYYMM) → first day of month as DatetimeIndex
- **Format**: Monthly time series compatible with NYISOToolkit
- **Columns**: MultiIndex [('Capacity Price ($/kW-month)', 'Zone')]

## Test Results

✅ **Pipeline Test**: Successfully fetched 30 records for Winter 2023-2024
✅ **Storage Test**: 6 Parquet files created (one per delivery month)
✅ **Adapter Test**: Successfully transformed to NYISOToolkit format
✅ **Metadata Test**: SQLite logging working

### Sample Output
```
Fetching NYISO capacity prices (MONTHLY) from 2023-11-01 to 2024-04-30...
Fetched 30 capacity price records
Wrote 6 Parquet files (30 rows)
Refreshed DuckDB views

Pipeline completed:
  Status: success
  Rows: 30
  Files: 6
```

### Data Inventory
```
Total Parquet files: 7
  NYISO:
    CAPACITY: 6 files
      2023: 2 files (11, 12)
      2024: 4 files (01, 02, 03, 04)
    ENERGY: 1 files
      2024: 1 files (01)
```

## Next Steps

1. ✅ **Complete** - Capacity pipeline integration
2. ✅ **Complete** - NYISOToolkit compatibility
3. ⏳ **Future** - ICAP-specific visualizations (see `ICAP_VISUALIZATION_ANALYSIS.md`)
4. ⏳ **Future** - Strip auction support
5. ⏳ **Future** - Excel import for historical data

## Files Modified/Created

### Created
- `pipelines/capacity_pipeline.py` - Capacity pipeline implementation
- `CAPACITY_PIPELINE_INTEGRATION_SUMMARY.md` - This file
- `ICAP_VISUALIZATION_ANALYSIS.md` - Visualization analysis

### Modified
- `run_pipeline.py` - Added `--capacity` flag and arguments
- `adapters/nyiso_compat.py` - Extended for CAPACITY market type

## Verification Commands

```bash
# List all data
python scripts/purge_data_cli.py --list

# Query capacity data in DuckDB
python -c "import duckdb; con = duckdb.connect('analytics_db/analytics.duckdb'); print(con.execute('SELECT COUNT(*) FROM market_prices WHERE market_type = \\'CAPACITY\\'').fetchone())"

# Test adapter
python -c "from adapters.nyiso_compat import create_iso_data_adapter; from pathlib import Path; adapter = create_iso_data_adapter('NYISO', 'capacity_monthly', 2024, parquet_base=Path('data/parquet'), duckdb_path=Path('analytics_db/analytics.duckdb')); print(adapter.df.head())"
```
