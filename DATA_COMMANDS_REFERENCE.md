# Data Commands Reference

Complete reference for all data pulling and purging commands.

## 📥 Data Pulling Commands

### Initialize Pipeline (First Time Only)
```bash
python run_pipeline.py --init
```
Creates directories, SQLite metadata DB, and DuckDB analytics DB.

---

### Energy Market Data (NYISO)

#### Recent Data (Last 7 Days)
```bash
python run_pipeline.py --energy --iso NYISO --product DA
```

#### Specific Date Range
```bash
# Day-ahead energy prices
python run_pipeline.py --energy --iso NYISO --start-date 2024-01-01 --end-date 2024-01-07 --product DA

# Real-time energy prices
python run_pipeline.py --energy --iso NYISO --start-date 2024-01-01 --end-date 2024-01-07 --product RT
```

#### Backfill Historical Data
```bash
# Backfill entire year
python run_pipeline.py --energy --iso NYISO --backfill --start-year 2020 --product DA

# Backfill year range
python run_pipeline.py --energy --iso NYISO --backfill --start-year 2020 --end-year 2024 --product DA
```

**Product Options:**
- `DA` - Day-ahead market (default)
- `RT` - Real-time market

**Storage Location:**
- `data/parquet/NYISO/ENERGY/{year}/{month}/data_{year}_{month}.parquet`

---

### Capacity Market Data (NYISO ICAP)

**⚠️ Note:** Capacity pipeline not yet integrated into `run_pipeline.py`. Use test scripts for now.

#### Using Test Script (Recommended for Testing)
```bash
# Test with specific auction month
python test_icap_simple.py

# Test with date range (programmatic)
python test_icap_fetch_capacity.py
```

#### Programmatic Usage (Python)
```python
from adapters.nyiso_capacity import NYISOCapacityAdapter
from datetime import datetime
import pytz

adapter = NYISOCapacityAdapter()

# Fetch Winter 2023-2024 capacity data
start_date = datetime(2023, 11, 1, tzinfo=pytz.UTC)
end_date = datetime(2024, 4, 30, tzinfo=pytz.UTC)

facts = adapter.fetch_capacity_prices(
    start_date=start_date,
    end_date=end_date,
    nodes=None,  # All zones
    auction_type="MONTHLY",  # or "STRIP", or None for all
)
```

**Storage Location (when integrated):**
- `data/parquet/NYISO/CAPACITY/{year}/{month}/data_{year}_{month}.parquet`

**Auction Types:**
- `MONTHLY` - Monthly capacity auctions
- `STRIP` - Seasonal strip auctions (not yet implemented)
- `None` - All auction types

---

## 🗑️ Data Purging Commands

### List All Data (No Deletion)
```bash
python scripts/purge_data_cli.py --list
```

### Purge All Data
```bash
python scripts/purge_data_cli.py --purge-all --confirm
```
⚠️ **WARNING:** Deletes ALL Parquet data for ALL ISOs and ALL market types.

---

### Purge by ISO/Provider

#### Purge All NYISO Data
```bash
python scripts/purge_data_cli.py --purge-iso NYISO --confirm
```
Deletes all NYISO data (ENERGY, CAPACITY, ANCILLARY).

#### Purge All PJM Data (when available)
```bash
python scripts/purge_data_cli.py --purge-iso PJM --confirm
```

---

### Purge by Delivery Month (YYYYMM)

#### Purge January 2024 for All ISOs
```bash
python scripts/purge_data_cli.py --purge-month 202401 --confirm
```

#### Purge January 2024 for NYISO Only
```bash
python scripts/purge_data_cli.py --purge-month 202401 --iso NYISO --confirm
```

#### Purge January 2024 ENERGY Data for NYISO
```bash
python scripts/purge_data_cli.py --purge-month 202401 --iso NYISO --market-type ENERGY --confirm
```

#### Purge January 2024 CAPACITY Data for NYISO
```bash
python scripts/purge_data_cli.py --purge-month 202401 --iso NYISO --market-type CAPACITY --confirm
```

**Market Type Options:**
- `ENERGY` - Energy market data only
- `CAPACITY` - Capacity market data only
- `ANCILLARY` - Ancillary services data only
- (omit `--market-type`) - All market types

---

## 📊 Examples by Use Case

### Scenario 1: Fetch Energy Data for January 2024
```bash
# Pull data
python run_pipeline.py --energy --iso NYISO --start-date 2024-01-01 --end-date 2024-01-31 --product DA

# Verify it's there
python scripts/purge_data_cli.py --list

# If you need to re-fetch, purge first
python scripts/purge_data_cli.py --purge-month 202401 --iso NYISO --market-type ENERGY --confirm

# Then re-fetch
python run_pipeline.py --energy --iso NYISO --start-date 2024-01-01 --end-date 2024-01-31 --product DA
```

### Scenario 2: Fetch ICAP Data (Programmatic)
```python
# In Python script or Jupyter notebook
from adapters.nyiso_capacity import NYISOCapacityAdapter
from datetime import datetime
import pytz
from storage.parquet_writer import ParquetWriter
from run_pipeline import DIRS

# Fetch data
adapter = NYISOCapacityAdapter()
start_date = datetime(2023, 11, 1, tzinfo=pytz.UTC)
end_date = datetime(2024, 4, 30, tzinfo=pytz.UTC)

facts = adapter.fetch_capacity_prices(
    start_date=start_date,
    end_date=end_date,
    auction_type="MONTHLY",
)

# Write to Parquet
writer = ParquetWriter(DIRS["parquet"], validate=True)
result = writer.write_facts(
    facts=facts,
    iso_code="NYISO",
    market_type="CAPACITY",
)

print(f"Wrote {result['rows_written']} rows to {len(result['files'])} files")
```

### Scenario 3: Clean Up and Start Fresh
```bash
# List what you have
python scripts/purge_data_cli.py --list

# Purge everything
python scripts/purge_data_cli.py --purge-all --confirm

# Verify it's gone
python scripts/purge_data_cli.py --list

# Re-fetch what you need
python run_pipeline.py --energy --iso NYISO --start-date 2024-01-01 --end-date 2024-01-07 --product DA
```

### Scenario 4: Remove Only Energy Data, Keep Capacity
```bash
# Purge all ENERGY data for NYISO
python scripts/purge_data_cli.py --purge-iso NYISO --confirm
# Wait, that removes everything. Instead, purge by market type per month:

# For each month you want to clean:
python scripts/purge_data_cli.py --purge-month 202401 --iso NYISO --market-type ENERGY --confirm
```

**Note:** Currently, `--purge-iso` removes all market types. To purge only ENERGY while keeping CAPACITY, you need to purge by month with `--market-type ENERGY`.

---

## 🔍 Data Verification

### Check What Data You Have
```bash
python scripts/purge_data_cli.py --list
```

### Query Data in DuckDB
```python
import duckdb
from run_pipeline import DUCKDB_DB

con = duckdb.connect(str(DUCKDB_DB))

# Count all records
df = con.execute("SELECT COUNT(*) as cnt FROM market_prices").df()
print(f"Total records: {df['cnt'].iloc[0]}")

# Count by market type
df = con.execute("""
    SELECT market_type, COUNT(*) as cnt 
    FROM market_prices 
    GROUP BY market_type
""").df()
print(df)

# Count by ISO
df = con.execute("""
    SELECT iso_code, COUNT(*) as cnt 
    FROM market_prices 
    GROUP BY iso_code
""").df()
print(df)

con.close()
```

---

## 📝 Quick Reference Table

| Action | Command |
|--------|---------|
| **List data** | `python scripts/purge_data_cli.py --list` |
| **Pull energy (recent)** | `python run_pipeline.py --energy --iso NYISO --product DA` |
| **Pull energy (date range)** | `python run_pipeline.py --energy --iso NYISO --start-date YYYY-MM-DD --end-date YYYY-MM-DD --product DA` |
| **Pull energy (backfill)** | `python run_pipeline.py --energy --iso NYISO --backfill --start-year YYYY --product DA` |
| **Pull capacity** | Use `test_icap_simple.py` or programmatic (see above) |
| **Purge all** | `python scripts/purge_data_cli.py --purge-all --confirm` |
| **Purge by ISO** | `python scripts/purge_data_cli.py --purge-iso NYISO --confirm` |
| **Purge by month** | `python scripts/purge_data_cli.py --purge-month YYYYMM --confirm` |
| **Purge by month + ISO** | `python scripts/purge_data_cli.py --purge-month YYYYMM --iso NYISO --confirm` |
| **Purge by month + ISO + type** | `python scripts/purge_data_cli.py --purge-month YYYYMM --iso NYISO --market-type ENERGY --confirm` |

---

## 🚧 Coming Soon

- `python run_pipeline.py --capacity --iso NYISO` (capacity pipeline integration)
- Strip auction support for ICAP
- Excel import for historical ICAP data
