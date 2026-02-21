# Data Schema Documentation

This directory contains ERD-like documentation for all data structures in the isodata pipeline.

## Files

- **[SQLITE_SCHEMA.md](SQLITE_SCHEMA.md)** - SQLite metadata database schema
  - Tables: `iso`, `market_node`, `dataset_version`, `data_source`, `ingestion_log`, `url_registry`
  - Stores metadata only (not actual market price data)
  - Location: `metadata/metadata.db`

- **[PARQUET_SCHEMA.md](PARQUET_SCHEMA.md)** - Parquet file schema
  - Canonical `MarketPriceFact` schema
  - All market price data is stored here
  - Location: `data/parquet/{iso}/{market_type}/{year}/{month}/`
  - Data accumulates over time and is never automatically deleted

- **[DUCKDB_SCHEMA.md](DUCKDB_SCHEMA.md)** - DuckDB views schema
  - SQL views that query Parquet files
  - Views are NOT data storage - they are SQL queries
  - Location: `analytics_db/analytics.duckdb`
  - Views read from Parquet files in real-time

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA STORAGE                              │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐         ┌──────────────────────┐
│   SQLite Metadata    │         │   Parquet Files      │
│  (metadata.db)       │         │  (data/parquet/)     │
├──────────────────────┤         ├──────────────────────┤
│ • iso                │         │ • MarketPriceFact    │
│ • market_node        │         │   records            │
│ • dataset_version    │         │ • Partitioned by:    │
│ • data_source        │         │   - iso_code         │
│ • ingestion_log      │         │   - market_type      │
│ • url_registry       │         │   - year              │
│                      │         │   - month            │
│ Metadata only        │         │                      │
│ (no price data)      │         │ Actual price data    │
└──────────────────────┘         └──────────────────────┘
         │                                 │
         │                                 │
         └─────────────┬───────────────────┘
                       │
         ┌─────────────▼───────────────────┐
         │      DuckDB Views               │
         │  (analytics.duckdb)             │
         ├─────────────────────────────────┤
         │ • market_prices                 │
         │ • energy_prices                 │
         │ • capacity_prices               │
         │                                 │
         │ SQL queries over Parquet files  │
         │ (NOT copies of data)            │
         └─────────────────────────────────┘
```

## Key Concepts

### SQLite (Metadata)
- **Purpose**: Track data ingestion, sources, and configuration
- **Location**: `metadata/metadata.db`
- **Contains**: No actual market price data, only metadata
- **Accumulates**: Ingestion logs, data sources, URL registry entries

### Parquet Files (Data)
- **Purpose**: Store all market price data
- **Location**: `data/parquet/{iso}/{market_type}/{year}/{month}/`
- **Contains**: All actual market price records
- **Accumulates**: Data accumulates over time, never automatically deleted
- **Schema**: Defined by `MarketPriceFact` in `canonical/schemas.py`

### DuckDB Views (Queries)
- **Purpose**: Provide SQL interface to query Parquet files
- **Location**: `analytics_db/analytics.duckdb`
- **Contains**: SQL view definitions (queries), NOT data
- **Updates**: Use `update_view_definitions()` to update view definitions when schema changes
- **Important**: Views are just SQL queries - they don't store or copy data

## Data Flow

```
1. Import Data
   └─> Write to Parquet files (data/parquet/)
   └─> Log to SQLite (metadata/metadata.db)
   └─> Update DuckDB views (analytics.duckdb)

2. Query Data
   └─> Query DuckDB views
       └─> DuckDB reads from Parquet files
           └─> Returns results

3. Update Views (when schema changes)
   └─> update_view_definitions()
       └─> Updates SQL view definitions
       └─> Does NOT touch Parquet files
       └─> Does NOT delete any data
```

## Important Notes

- **Data Safety**: Parquet files are never automatically deleted
- **View Updates**: `update_view_definitions()` only updates SQL queries, not data
- **Single Source of Truth**: Parquet files are the only place actual data is stored
- **Metadata Tracking**: SQLite tracks where data came from and when it was imported

## Keeping Documentation Up to Date

These documentation files are **auto-generated** from the actual code schemas.

### When to Regenerate

Run the generator script whenever you:
- Add/modify SQLite tables
- Change `MarketPriceFact` schema fields
- Add/modify DuckDB views
- Update field types or constraints

### How to Regenerate

```bash
python scripts/generate_schema_docs.py
```

This script will:
1. Read actual schemas from code (`canonical/schemas.py`, `run_pipeline.py`, `storage/duckdb_views.py`)
2. Delete old documentation files
3. Generate fresh documentation with current schemas
4. Create ERD diagrams automatically

**Note**: The generator script reads from the actual code, so documentation will always match the current implementation.
