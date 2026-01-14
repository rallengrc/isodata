# Data Purge Utility

Utility to keep DuckDB views and Parquet files in sync by purging data with different granularity.

## Features

1. **Purge All**: Delete all Parquet data
2. **Purge by ISO**: Delete all data for a specific provider (e.g., NYISO, PJM)
3. **Purge by YYYYMM**: Delete data for a specific delivery month
4. **List Data**: Inventory all stored data without deleting

## Safety Features

- All purge operations require explicit `confirm=True` to prevent accidental deletion
- Automatically refreshes DuckDB views after purging
- Removes empty directories after file deletion

## Command Line Usage

### List All Data

```bash
python scripts/purge_data_cli.py --list
```

### Purge All Data

```bash
python scripts/purge_data_cli.py --purge-all --confirm
```

### Purge by ISO

```bash
# Purge all NYISO data
python scripts/purge_data_cli.py --purge-iso NYISO --confirm

# Purge all PJM data
python scripts/purge_data_cli.py --purge-iso PJM --confirm
```

### Purge by Delivery Month

```bash
# Purge January 2024 data for all ISOs
python scripts/purge_data_cli.py --purge-month 202401 --confirm

# Purge January 2024 data for NYISO only
python scripts/purge_data_cli.py --purge-month 202401 --iso NYISO --confirm

# Purge January 2024 ENERGY data for NYISO
python scripts/purge_data_cli.py --purge-month 202401 --iso NYISO --market-type ENERGY --confirm
```

### JSON Output

Add `--json` flag for machine-readable output:

```bash
python scripts/purge_data_cli.py --list --json
```

## Programmatic Usage

### Using the DataPurge Class

```python
from pathlib import Path
from storage.purge_data import DataPurge
from run_pipeline import DIRS, DUCKDB_DB

# Initialize purger
purger = DataPurge(DIRS["parquet"], DUCKDB_DB)

# List all data
inventory = purger.list_data()
print(f"Total files: {inventory['total_files']}")

# Purge all NYISO data
result = purger.purge_by_iso("NYISO", confirm=True)
print(f"Deleted {result['files_deleted']} files")

# Purge January 2024 data
result = purger.purge_by_yyyymm(
    "202401",
    iso_code="NYISO",
    market_type="ENERGY",
    confirm=True,
)
print(f"Deleted {result['files_deleted']} files")
```

### Using Convenience Functions

```python
from storage.purge_data import purge_all, purge_by_iso, purge_by_yyyymm
from run_pipeline import DIRS, DUCKDB_DB

# Purge all data
result = purge_all(DIRS["parquet"], DUCKDB_DB, confirm=True)

# Purge by ISO
result = purge_by_iso("NYISO", DIRS["parquet"], DUCKDB_DB, confirm=True)

# Purge by month
result = purge_by_yyyymm(
    "202401",
    DIRS["parquet"],
    DUCKDB_DB,
    iso_code="NYISO",
    market_type="ENERGY",
    confirm=True,
)
```

## Return Values

All purge functions return a dictionary with:

- `status`: "success" or "no_data"
- `files_deleted`: Number of Parquet files deleted
- `views_refreshed`: Boolean indicating if DuckDB views were refreshed
- Additional fields depending on the operation

## Examples

See `examples/purge_examples.py` for complete examples.

## Notes

- Purge operations are **irreversible** - deleted Parquet files cannot be recovered
- DuckDB views are automatically refreshed after purging
- Empty directories are automatically cleaned up
- The `confirm` parameter is required for all purge operations to prevent accidents

