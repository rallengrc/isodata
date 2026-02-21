#!/usr/bin/env python3
"""
Generate schema documentation from actual code.

This script reads the actual schemas from the codebase and regenerates
the documentation files in docs/. Run this whenever schemas change.

Usage:
    python scripts/generate_schema_docs.py
"""

import sys
from pathlib import Path
import inspect
import sqlite3

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from canonical.schemas import MarketPriceFact
from run_pipeline import SQLITE_SCHEMA


def generate_sqlite_doc():
    """Generate SQLITE_SCHEMA.md from actual SQLite schema."""
    print("Generating SQLITE_SCHEMA.md...")
    
    # Parse SQLite schema
    tables = {}
    current_table = None
    
    for line in SQLITE_SCHEMA.split('\n'):
        line = line.strip()
        if not line or line.startswith('--'):
            continue
        
        if 'CREATE TABLE' in line.upper():
            # Extract table name
            parts = line.split()
            if 'IF NOT EXISTS' in line.upper():
                table_name = parts[4]
            else:
                table_name = parts[2]
            current_table = table_name
            tables[table_name] = {'columns': [], 'constraints': []}
        elif current_table and '(' in line:
            # Parse column or constraint
            line = line.rstrip(',').rstrip(')').strip()
            if line.startswith('PRIMARY KEY') or line.startswith('FOREIGN KEY'):
                tables[current_table]['constraints'].append(line)
            elif line:
                # Column definition
                parts = line.split()
                if len(parts) >= 2:
                    col_name = parts[0]
                    col_type = parts[1]
                    constraints = ' '.join(parts[2:]) if len(parts) > 2 else ''
                    tables[current_table]['columns'].append({
                        'name': col_name,
                        'type': col_type,
                        'constraints': constraints
                    })
    
    # Generate markdown
    doc = f"""# SQLite Metadata Database Schema

## Overview

The SQLite database (`metadata/metadata.db`) stores **metadata only** - information about data ingestion, sources, and configuration. It does NOT store the actual market price data.

## Database Location

```
metadata/metadata.db
```

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      SQLite Metadata DB                      │
│                  (metadata/metadata.db)                      │
└─────────────────────────────────────────────────────────────┘
"""
    
    # Add table diagrams
    for table_name, table_info in tables.items():
        doc += f"""
┌──────────────────────┐
│   {table_name:<18}│
├──────────────────────┤"""
        for col in table_info['columns']:
            constraint_str = ""
            if 'PRIMARY KEY' in col['constraints'].upper():
                constraint_str = " (PK)"
            elif 'NOT NULL' in col['constraints'].upper():
                constraint_str = " (NOT NULL)"
            doc += f"\n│ {col['name']:<15} {col['type']:<4}{constraint_str}│"
        doc += "\n└──────────────────────┘\n"
    
    doc += "\n## Table Definitions\n\n"
    
    for table_name, table_info in tables.items():
        doc += f"### `{table_name}`\n\n"
        doc += "| Column | Type | Constraints | Description |\n"
        doc += "|--------|------|-------------|-------------|\n"
        
        for col in table_info['columns']:
            constraints = col['constraints'] or 'None'
            # Try to infer description from name
            desc = infer_description(col['name'])
            doc += f"| `{col['name']}` | `{col['type']}` | {constraints} | {desc} |\n"
        
        doc += "\n"
    
    doc += """## Notes

- **No actual market data**: This database only stores metadata. Market price data is stored in Parquet files.
- **Accumulates over time**: Ingestion logs and data sources accumulate as you import more data.
- **Query examples**: See `test_queries.py` for examples of querying this metadata.
"""
    
    return doc


def infer_description(field_name):
    """Infer field description from name."""
    descriptions = {
        'iso_code': 'ISO identifier (e.g., \'NYISO\', \'PJM\')',
        'name': 'Full name or description',
        'market_start_year': 'Year the market started',
        'notes': 'Additional notes',
        'node_id': 'Node/zone identifier',
        'node_type': 'Type: \'NODE\', \'ZONE\', or \'HUB\'',
        'zone': 'Zone name if applicable',
        'valid_from': 'When this record became valid',
        'valid_to': 'When this record became invalid (NULL if still valid)',
        'dataset_name': 'Name of the dataset',
        'version': 'Version identifier',
        'created_at': 'When this record was created',
        'description': 'Description of the record',
        'source_url': 'Source URL or file path',
        'start_time': 'When ingestion started',
        'end_time': 'When ingestion completed',
        'status': '\'SUCCESS\', \'ERROR\', or \'NO_DATA\'',
        'row_count': 'Number of rows processed',
        'error_message': 'Error message (if status=\'ERROR\')',
        'url_key': 'Unique key for URL lookup',
        'url': 'The actual URL',
        'active': '1 if active, 0 if inactive',
        'updated_at': 'When record was last updated',
    }
    return descriptions.get(field_name, 'Field description')


def generate_parquet_doc():
    """Generate PARQUET_SCHEMA.md from MarketPriceFact schema."""
    print("Generating PARQUET_SCHEMA.md...")
    
    # Get schema from Pydantic model
    fields = MarketPriceFact.__fields__
    
    doc = """# Parquet Data Schema

## Overview

All market price data is stored in **Parquet files** in `data/parquet/`. This is the single source of truth for all market data. The schema is defined by the `MarketPriceFact` canonical model.

## Storage Location

```
data/parquet/
  {iso_code}/
    {market_type}/
      {year}/
        {month}/
          data_{year}_{month}.parquet
          data_{year}_{month}_{auction_type}.parquet
```

**Example:**
```
data/parquet/
  NYISO/
    ENERGY/
      2024/
        01/
          data_2024_01.parquet
    CAPACITY/
      2023/
        11/
          data_2023_11_monthly.parquet
          data_2023_11_strip.parquet
```

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Parquet Files                             │
│              (data/parquet/{iso}/{type}/{year}/{month}/)    │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                  MarketPriceFact                             │
│              (Canonical Schema - One Row Per Record)         │
├──────────────────────────────────────────────────────────────┤
"""
    
    # Group fields by category
    categories = {
        'IDENTIFIERS': ['iso_code', 'market_type', 'product', 'node_id', 'node_type', 'zone'],
        'TEMPORAL FIELDS (Full Precision)': ['start_time', 'end_time'],
        'TEMPORAL FIELDS (Month-Level Aggregation)': ['auction_month', 'delivery_month'],
        'CAPACITY MARKET SPECIFIC': ['capability_period', 'auction_type', 'awarded_mw', 'posted_at', 'season_id'],
        'PRICE FIELDS (Separate by Market Type)': ['price_energy', 'price_capacity', 'unit'],
        'ZONE NORMALIZATION TRACKING': ['zone_normalized', 'zone_original'],
        'DATA QUALITY TRACKING': ['data_quality_score', 'validation_errors'],
        'METADATA': ['auction_id', 'source_url', 'ingested_at'],
    }
    
    for category, field_names in categories.items():
        doc += f"│  {category:<58}│\n"
        for field_name in field_names:
            if field_name in fields:
                field = fields[field_name]
                field_type = str(field.type_).replace('typing.', '').replace('Optional[', '').replace(']', '')
                required = 'Required' if field.required else 'Optional'
                desc = field.field_info.description or 'No description'
                doc += f"│  ├─ {field_name}: {field_type:<20} ({required:<9})│\n"
        doc += "│                                                              │\n"
    
    doc += "└──────────────────────────────────────────────────────────────┘\n\n"
    doc += "## Field Definitions\n\n"
    
    # Generate field tables by category
    for category, field_names in categories.items():
        if category.startswith('TEMPORAL') or category.startswith('PRICE'):
            continue  # Skip these, they're in the diagram
        
        doc += f"### {category}\n\n"
        doc += "| Field | Type | Required | Description |\n"
        doc += "|-------|------|----------|-------------|\n"
        
        for field_name in field_names:
            if field_name in fields:
                field = fields[field_name]
                field_type = str(field.type_).replace('typing.', '').replace('Optional[', '').replace(']', '')
                required = 'Yes' if field.required else 'No'
                desc = field.field_info.description or 'No description'
                doc += f"| `{field_name}` | `{field_type}` | {required} | {desc} |\n"
        
        doc += "\n"
    
    # Add price fields section
    doc += """### Price Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `price_energy` | `Optional[float]` | Conditional | Energy price in $/MWh (required if market_type='ENERGY') |
| `price_capacity` | `Optional[float]` | Conditional | Capacity price in $/kW-month (required if market_type='CAPACITY') |
| `unit` | `str` | Yes | Price unit metadata: '$/MWh' or '$/kW-month' |

**Important:** 
- For ENERGY records: `price_energy` must be set, `price_capacity` must be NULL
- For CAPACITY records: `price_capacity` must be set, `price_energy` must be NULL
- This prevents mixing Power (kW) and Energy (kWh/MWh) units

"""
    
    doc += """## Partitioning Strategy

Parquet files are partitioned by:
1. `iso_code` (e.g., 'NYISO')
2. `market_type` (e.g., 'ENERGY', 'CAPACITY')
3. `year` (extracted from `delivery_month`, e.g., 2024)
4. `month` (extracted from `delivery_month`, e.g., 01)

For capacity markets with `auction_type`, files are further split:
- `data_2023_11_monthly.parquet` (MONTHLY auctions)
- `data_2023_11_strip.parquet` (STRIP auctions)

## Data Accumulation

- **Data accumulates over time**: Each import adds new Parquet files
- **No data deletion**: Parquet files are never automatically deleted
- **Partitioning enables efficient queries**: Query only the partitions you need
- **Schema evolution**: New fields can be added (union_by_name handles this)

## Querying Parquet Files

### Direct Parquet Query (DuckDB)

```sql
SELECT * 
FROM read_parquet('data/parquet/**/*.parquet', union_by_name=true)
WHERE iso_code = 'NYISO'
  AND market_type = 'ENERGY'
  AND delivery_month = '202401'
```

### Via DuckDB Views

```sql
SELECT * 
FROM market_prices
WHERE iso_code = 'NYISO'
  AND market_type = 'ENERGY'
  AND delivery_month = '202401'
```

The `market_prices` view is just a SQL query over Parquet files - it does NOT store data.
"""
    
    return doc


def generate_duckdb_doc():
    """Generate DUCKDB_SCHEMA.md from view definitions."""
    print("Generating DUCKDB_SCHEMA.md...")
    
    # Read view definitions from code
    views_file = project_root / 'storage' / 'duckdb_views.py'
    with open(views_file) as f:
        views_code = f.read()
    
    doc = """# DuckDB Views Schema

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

### `energy_prices`
**Filtered view for energy market data only**

| Property | Value |
|----------|-------|
| **Type** | Filtered view |
| **Source** | `market_prices` |
| **Filter** | `market_type = 'ENERGY'` |
| **Columns** | All fields from `MarketPriceFact` schema |

### `energy_prices_da`
**Day-ahead energy prices only**

| Property | Value |
|----------|-------|
| **Type** | Filtered view |
| **Source** | `energy_prices` |
| **Filter** | `product = 'ENERGY_DA'` |
| **Columns** | All fields from `MarketPriceFact` schema |

### `energy_prices_rt`
**Real-time energy prices only**

| Property | Value |
|----------|-------|
| **Type** | Filtered view |
| **Source** | `energy_prices` |
| **Filter** | `product = 'ENERGY_RT'` |
| **Columns** | All fields from `MarketPriceFact` schema |

### `energy_prices_by_iso`
**Energy prices grouped by ISO with backward-compatible price column**

| Property | Value |
|----------|-------|
| **Type** | Projected view |
| **Source** | `energy_prices` |
| **Filter** | None (all energy records) |
| **Columns** | Selected subset with price alias |

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

## Notes

- **Views are queries, not data**: Views don't store data - they query Parquet files on-demand
- **Real-time**: Views always reflect current Parquet file contents
- **Schema evolution**: `union_by_name=true` allows views to handle schema changes across Parquet files
- **Performance**: DuckDB optimizes queries over Parquet files automatically
- **No data duplication**: Views don't copy data - they read directly from Parquet files
"""
    
    return doc


def main():
    """Generate all schema documentation files."""
    docs_dir = project_root / 'docs'
    docs_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("Generating Schema Documentation")
    print("=" * 60)
    print()
    
    # Generate SQLite docs
    sqlite_doc = generate_sqlite_doc()
    sqlite_path = docs_dir / 'SQLITE_SCHEMA.md'
    with open(sqlite_path, 'w') as f:
        f.write(sqlite_doc)
    print(f"✓ Written: {sqlite_path}")
    
    # Generate Parquet docs
    parquet_doc = generate_parquet_doc()
    parquet_path = docs_dir / 'PARQUET_SCHEMA.md'
    with open(parquet_path, 'w') as f:
        f.write(parquet_doc)
    print(f"✓ Written: {parquet_path}")
    
    # Generate DuckDB docs
    duckdb_doc = generate_duckdb_doc()
    duckdb_path = docs_dir / 'DUCKDB_SCHEMA.md'
    with open(duckdb_path, 'w') as f:
        f.write(duckdb_doc)
    print(f"✓ Written: {duckdb_path}")
    
    print()
    print("=" * 60)
    print("✓ All schema documentation generated!")
    print("=" * 60)
    print()
    print("Files updated:")
    print(f"  - {sqlite_path.relative_to(project_root)}")
    print(f"  - {parquet_path.relative_to(project_root)}")
    print(f"  - {duckdb_path.relative_to(project_root)}")
    print()
    print("Note: These files are auto-generated. To update them,")
    print("      run this script after schema changes.")


if __name__ == '__main__':
    main()
