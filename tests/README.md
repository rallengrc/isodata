# Test Suite

Comprehensive test suite for the Power Market Data Pipeline.

## Test Structure

```
tests/
├── __init__.py
├── run_tests.py              # Test runner
├── test_icap_adapter.py      # ICAP adapter and HTML parsing tests
├── test_energy_adapter.py    # Energy adapter tests
├── test_schemas.py           # Schema validation and normalization tests
└── test_storage.py           # Storage components (Parquet, DuckDB, purge) tests
```

## Running Tests

### Run All Tests
```bash
python tests/run_tests.py
```

### Run Specific Test Module
```bash
python tests/run_tests.py test_icap_adapter
python tests/run_tests.py test_schemas
python tests/run_tests.py test_energy_adapter
python tests/run_tests.py test_storage
```

### Verbose Output
```bash
python tests/run_tests.py -v
```

### Stop on First Failure
```bash
python tests/run_tests.py --failfast
```

## Test Coverage

### ICAP Adapter Tests (`test_icap_adapter.py`)
- ✅ HTML parser with saved HTML file
- ✅ Live fetching from NYISO portal
- ✅ `fetch_capacity_prices()` method
- ✅ Data structure validation

### Schema Tests (`test_schemas.py`)
- ✅ Energy price normalization
- ✅ Capacity price normalization (with new fields: `awarded_mw`, `posted_at`, `season_id`)
- ✅ Zone name normalization
- ✅ Temporal utility functions

### Energy Adapter Tests (`test_energy_adapter.py`)
- ✅ Fetching energy prices
- ✅ Node discovery

### Storage Tests (`test_storage.py`)
- ✅ ParquetWriter functionality
- ✅ DuckDB views creation and querying
- ✅ Data purge utility

## Test Requirements

Some tests require:
- **Network access**: ICAP and energy adapter tests fetch live data
- **NYISOToolkit**: Energy adapter tests require NYISOToolkit
- **Test HTML file**: ICAP parser test uses `C:\Users\rallen\Documents\winter2324.html`

## Notes

- Tests use temporary directories for storage tests
- Live tests may be slow due to network requests
- Some tests may skip if dependencies are missing (using `skipTest`)
