# DuckDB Views Schema

## Overview

DuckDB views provide a SQL interface to query Parquet files. **Views are NOT data storage** - they are SQL queries that read from Parquet files in real-time. The views are stored in `analytics_db/analytics.duckdb`.

## Database Location

```
analytics_db/analytics.duckdb
```

## Important Notes

⚠️ **CRITICAL**: DuckDB views are **NOT copies of your data**. They are SQL queries that read from Parquet files.

- **Views = SQL queries** (like `SELECT * FROM read_parquet('data/parquet/**/*.parquet')`)
- **Data = Parquet files** in `data/parquet/` (this is your actual data)
- **Updating views** (`update_view_definitions()`) does NOT delete or modify Parquet files
- **Your data accumulates** in Parquet files and is never automatically deleted

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  DuckDB Database                             │
│            (analytics_db/analytics.duckdb)                   │
│                                                              │
│  NOTE: Views are SQL queries, NOT data storage!            │
│  All views read from: data/parquet/**/*.parquet            │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    market_prices                            │
│              (Unified view - all market types)               │
├──────────────────────────────────────────────────────────────┤
│ SQL Definition:                                               │
│   SELECT *                                                    │
│   FROM read_parquet('data/parquet/**/*.parquet',             │
│                     union_by_name=true)                       │
│                                                               │
│ Columns (from Parquet schema):                                │
│   • All MarketPriceFact fields                                │
│   • See PARQUET_SCHEMA.md for full field list                │
└──────────────────────────────────────────────────────────────┘
         │
         │ (filtered by market_type)
         │
         ├─────────────────────┬─────────────────────┐
         │                     │                     │
┌────────▼──────────┐  ┌───────▼────────┐  ┌────────▼──────────┐
│  energy_prices    │  │ capacity_prices│  │ (future views)    │
│  (ENERGY only)    │  │ (CAPACITY only)│  │                   │
├───────────────────┤  ├────────────────┤  │                   │
│ SQL:              │  │ SQL:           │  │                   │
│ SELECT *          │  │ SELECT *       │  │                   │
│ FROM market_prices│  │ FROM           │  │                   │
│ WHERE             │  │   market_prices│  │                   │
│   market_type =   │  │ WHERE          │  │                   │
│   'ENERGY'        │  │   market_type =│  │                   │
│                   │  │   'CAPACITY'   │  │                   │
└───────────────────┘  └────────────────┘  └───────────────────┘
         │
         │ (filtered by product)
         │
         ├─────────────────────┬─────────────────────┐
         │                     │                     │
┌────────▼──────────┐  ┌───────▼────────┐           │
│ energy_prices_da  │  │ energy_prices_rt│           │
│ (Day-Ahead)       │  │ (Real-Time)     │           │
├───────────────────┤  ├────────────────┤           │
│ SQL:              │  │ SQL:           │           │
│ SELECT *          │  │ SELECT *       │           │
│ FROM energy_prices │  │ FROM           │           │
│ WHERE             │  │   energy_prices│           │
│   product =       │  │ WHERE          │           │
│   'ENERGY_DA'     │  │   product =    │           │
│                   │  │   'ENERGY_RT'  │           │
└───────────────────┘  └────────────────┘           │
                                                      │
┌─────────────────────────────────────────────────────▼──────────┐
│              energy_prices_by_iso                             │
│              (Grouped by ISO, with price alias)                │
├────────────────────────────────────────────────────────────────┤
│ SQL:                                                            │
│   SELECT                                                        │
│     iso_code,                                                   │
│     node_id,                                                    │
│     zone,                                                       │
│     start_time,                                                 │
│     end_time,                                                   │
│     COALESCE(price_energy, price) as price,                    │
│     unit                                                        │
│   FROM energy_prices                                            │
│   ORDER BY iso_code, start_time                                 │
│                                                                 │
│ Purpose: Provides backward-compatible 'price' column           │
│          (aliases price_energy for ENERGY records)              │
└────────────────────────────────────────────────────────────────┘
```

## View Definitions

### `market_prices`
**Unified view across all market types**

| Property | Value |
|----------|-------|
| **Type** | Base view |
| **Source** | All Parquet files in `data/parquet/**/*.parquet` |
| **Filter** | None (all records) |
| **Columns** | All fields from `MarketPriceFact` schema |
| **SQL** | `SELECT * FROM read_parquet('data/parquet/**/*.parquet', union_by_name=true)` |

**Purpose**: Single entry point to query all market data regardless of type.

**Example Query:**
```sql
SELECT * FROM market_prices 
WHERE iso_code = 'NYISO' 
  AND delivery_month = '202401'
LIMIT 10;
```

### `energy_prices`
**Filtered view for energy market data only**

| Property | Value |
|----------|-------|
| **Type** | Filtered view |
| **Source** | `market_prices` |
| **Filter** | `market_type = 'ENERGY'` |
| **Columns** | All fields from `MarketPriceFact` schema |

**SQL Definition:**
```sql
CREATE VIEW energy_prices AS
SELECT *
FROM market_prices
WHERE market_type = 'ENERGY'
```

**Example Query:**
```sql
SELECT zone, AVG(COALESCE(price_energy, price)) as avg_price
FROM energy_prices
WHERE iso_code = 'NYISO'
GROUP BY zone;
```

### `energy_prices_da`
**Day-ahead energy prices only**

| Property | Value |
|----------|-------|
| **Type** | Filtered view |
| **Source** | `energy_prices` |
| **Filter** | `product = 'ENERGY_DA'` |
| **Columns** | All fields from `MarketPriceFact` schema |

**SQL Definition:**
```sql
CREATE VIEW energy_prices_da AS
SELECT *
FROM energy_prices
WHERE product = 'ENERGY_DA'
```

### `energy_prices_rt`
**Real-time energy prices only**

| Property | Value |
|----------|-------|
| **Type** | Filtered view |
| **Source** | `energy_prices` |
| **Filter** | `product = 'ENERGY_RT'` |
| **Columns** | All fields from `MarketPriceFact` schema |

**SQL Definition:**
```sql
CREATE VIEW energy_prices_rt AS
SELECT *
FROM energy_prices
WHERE product = 'ENERGY_RT'
```

### `energy_prices_by_iso`
**Energy prices grouped by ISO with backward-compatible price column**

| Property | Value |
|----------|-------|
| **Type** | Projected view |
| **Source** | `energy_prices` |
| **Filter** | None (all energy records) |
| **Columns** | Selected subset with price alias |

**SQL Definition:**
```sql
CREATE VIEW energy_prices_by_iso AS
SELECT 
    iso_code,
    node_id,
    zone,
    start_time,
    end_time,
    COALESCE(price_energy, price) as price,
    unit
FROM energy_prices
ORDER BY iso_code, start_time
```

**Purpose**: 
- Provides backward-compatible `price` column (aliases `price_energy`)
- Works with both old Parquet files (with `price` field) and new files (with `price_energy` field)
- Useful for NYISOToolkit compatibility

### `capacity_prices`
**Filtered view for capacity market data only**

| Property | Value |
|----------|-------|
| **Type** | Filtered view |
| **Source** | `market_prices` |
| **Filter** | `market_type = 'CAPACITY'` |
| **Columns** | All fields from `MarketPriceFact` schema |

**SQL Definition:**
```sql
CREATE VIEW capacity_prices AS
SELECT *
FROM market_prices
WHERE market_type = 'CAPACITY'
```

**Example Query:**
```sql
SELECT zone, AVG(COALESCE(price_capacity, price)) as avg_price
FROM capacity_prices
WHERE iso_code = 'NYISO'
  AND auction_type = 'MONTHLY'
GROUP BY zone;
```

## View Hierarchy

```
market_prices (base view - all data)
│
├── energy_prices (filtered: market_type = 'ENERGY')
│   ├── energy_prices_da (filtered: product = 'ENERGY_DA')
│   ├── energy_prices_rt (filtered: product = 'ENERGY_RT')
│   └── energy_prices_by_iso (projected: selected columns with price alias)
│
└── capacity_prices (filtered: market_type = 'CAPACITY')
```

## Column Mapping

Views inherit all columns from the underlying Parquet files. Key columns include:

### Price Columns (Backward Compatible)
- `price_energy`: Energy price in $/MWh (for ENERGY records)
- `price_capacity`: Capacity price in $/kW-month (for CAPACITY records)
- `price`: Legacy field (for backward compatibility with old Parquet files)

**Note**: Views use `COALESCE(price_energy, price)` and `COALESCE(price_capacity, price)` in queries to support both old and new Parquet file schemas.

### Common Columns
- `iso_code`, `market_type`, `product`
- `node_id`, `node_type`, `zone`
- `start_time`, `end_time`
- `auction_month`, `delivery_month`
- `unit`
- `source_url`, `ingested_at`

### Capacity-Specific Columns
- `capability_period`, `auction_type`
- `awarded_mw`, `posted_at`, `season_id`

See [PARQUET_SCHEMA.md](PARQUET_SCHEMA.md) for complete field definitions.

## View Management

### Updating View Definitions

When the Parquet schema changes, update view definitions:

```python
from storage.duckdb_views import DuckDBViews
from pathlib import Path

views = DuckDBViews(
    Path('analytics_db/analytics.duckdb'),
    Path('data/parquet')
)
views.update_view_definitions()  # Updates SQL queries, does NOT delete data
views.close()
```

**Important**: `update_view_definitions()`:
- ✅ Updates SQL view definitions
- ✅ Does NOT delete or modify Parquet files
- ✅ Does NOT delete any data
- ✅ Your Parquet files are safe

### View Creation Logic

1. **If Parquet files exist**: Views are created from actual Parquet files
   ```sql
   CREATE VIEW market_prices AS
   SELECT * FROM read_parquet('data/parquet/**/*.parquet', union_by_name=true)
   ```

2. **If no Parquet files exist**: Empty views are created with the expected schema
   ```sql
   CREATE VIEW market_prices AS
   SELECT 
     CAST(NULL AS VARCHAR) as iso_code,
     CAST(NULL AS DOUBLE) as price_energy,
     ...
   WHERE FALSE
   ```

## Query Examples

### Query All Data
```sql
SELECT COUNT(*) FROM market_prices;
```

### Query Energy Data
```sql
SELECT 
    zone,
    AVG(COALESCE(price_energy, price)) as avg_price
FROM energy_prices
WHERE iso_code = 'NYISO'
GROUP BY zone;
```

### Query Capacity Data
```sql
SELECT 
    zone,
    auction_type,
    AVG(COALESCE(price_capacity, price)) as avg_price
FROM capacity_prices
WHERE iso_code = 'NYISO'
GROUP BY zone, auction_type;
```

### Mixed Query (Energy + Capacity)
```sql
SELECT 
    market_type,
    zone,
    AVG(CASE 
        WHEN market_type = 'ENERGY' THEN COALESCE(price_energy, price)
        ELSE COALESCE(price_capacity, price)
    END) as avg_price
FROM market_prices
WHERE iso_code = 'NYISO'
GROUP BY market_type, zone;
```

## Notes

- **Views are queries, not data**: Views don't store data - they query Parquet files on-demand
- **Real-time**: Views always reflect current Parquet file contents
- **Schema evolution**: `union_by_name=true` allows views to handle schema changes across Parquet files
- **Performance**: DuckDB optimizes queries over Parquet files automatically
- **No data duplication**: Views don't copy data - they read directly from Parquet files
