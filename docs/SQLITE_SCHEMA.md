# SQLite Metadata Database Schema

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

┌──────────────────────┐
│        iso           │
├──────────────────────┤
│ iso_code (PK) TEXT   │
│ name TEXT            │
│ market_start_year INT│
│ notes TEXT           │
└──────────────────────┘
         │
         │ 1:N
         │
┌──────────────────────┐
│    market_node       │
├──────────────────────┤
│ iso_code TEXT        │
│ node_id TEXT         │
│ node_type TEXT       │
│ zone TEXT            │
│ valid_from DATE      │
│ valid_to DATE        │
└──────────────────────┘

┌──────────────────────┐
│  dataset_version     │
├──────────────────────┤
│ dataset_name TEXT    │
│ version TEXT         │
│ created_at TIMESTAMP │
│ description TEXT     │
└──────────────────────┘

┌──────────────────────┐
│    data_source       │
├──────────────────────┤
│ dataset_name TEXT    │
│ source_url TEXT      │
│ iso_code TEXT        │
└──────────────────────┘

┌──────────────────────┐
│   ingestion_log      │
├──────────────────────┤
│ dataset_name TEXT    │
│ iso_code TEXT        │
│ start_time TIMESTAMP │
│ end_time TIMESTAMP   │
│ status TEXT          │
│ row_count INTEGER    │
│ error_message TEXT   │
└──────────────────────┘

┌──────────────────────┐
│   url_registry       │
├──────────────────────┤
│ url_key (PK) TEXT    │
│ url TEXT NOT NULL    │
│ description TEXT     │
│ iso_code TEXT        │
│ active INT DEFAULT 1 │
│ created_at TIMESTAMP │
│ updated_at TIMESTAMP │
└──────────────────────┘
```

## Table Definitions

### `iso`
Reference table for ISO/RTO organizations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `iso_code` | TEXT | PRIMARY KEY | ISO identifier (e.g., 'NYISO', 'PJM') |
| `name` | TEXT | | Full name of the ISO |
| `market_start_year` | INTEGER | | Year the ISO market started |
| `notes` | TEXT | | Additional notes about the ISO |

**Example:**
```sql
INSERT INTO iso VALUES ('NYISO', 'New York Independent System Operator', 1999, 'Serves New York State');
```

### `market_node`
Reference table for market nodes (zones, hubs, pricing nodes).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `iso_code` | TEXT | | ISO identifier (FK to iso.iso_code) |
| `node_id` | TEXT | | Node identifier |
| `node_type` | TEXT | | Type: 'NODE', 'ZONE', or 'HUB' |
| `zone` | TEXT | | Zone name if applicable |
| `valid_from` | DATE | | When this node became valid |
| `valid_to` | DATE | | When this node became invalid (NULL if still valid) |

**Example:**
```sql
INSERT INTO market_node VALUES ('NYISO', 'NYC', 'ZONE', 'NYC', '1999-01-01', NULL);
```

### `dataset_version`
Tracks versions of datasets (for schema evolution tracking).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `dataset_name` | TEXT | | Name of the dataset |
| `version` | TEXT | | Version identifier |
| `created_at` | TIMESTAMP | | When this version was created |
| `description` | TEXT | | Description of changes in this version |

### `data_source`
Tracks data sources (URLs, file paths) for each dataset.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `dataset_name` | TEXT | | Name of the dataset |
| `source_url` | TEXT | | Source URL or file path |
| `iso_code` | TEXT | | ISO identifier |

**Example:**
```sql
INSERT INTO data_source VALUES 
  ('energy_da_nyiso', 'https://mis.nyiso.com/public/', 'NYISO');
```

### `ingestion_log`
Logs all data ingestion attempts (successful and failed).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `dataset_name` | TEXT | | Name of the dataset |
| `iso_code` | TEXT | | ISO identifier |
| `start_time` | TIMESTAMP | | When ingestion started |
| `end_time` | TIMESTAMP | | When ingestion completed |
| `status` | TEXT | | 'SUCCESS', 'ERROR', or 'NO_DATA' |
| `row_count` | INTEGER | | Number of rows ingested (if successful) |
| `error_message` | TEXT | | Error message (if status='ERROR') |

**Example:**
```sql
INSERT INTO ingestion_log VALUES 
  ('energy_da_nyiso', 'NYISO', '2024-01-15 10:00:00', '2024-01-15 10:05:00', 
   'SUCCESS', 720, NULL);
```

### `url_registry`
Central registry for all hard-coded URLs used by the pipeline.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `url_key` | TEXT | PRIMARY KEY | Unique key for URL lookup (e.g., 'nyiso_energy_base') |
| `url` | TEXT | NOT NULL | The actual URL |
| `description` | TEXT | | Description of what this URL is for |
| `iso_code` | TEXT | | ISO identifier (if applicable) |
| `active` | INTEGER | DEFAULT 1 | 1 if active, 0 if inactive |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When record was created |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When record was last updated |

**Example:**
```sql
INSERT INTO url_registry VALUES 
  ('nyiso_energy_base', 'https://mis.nyiso.com/public/', 
   'NYISO Market Information System base URL', 'NYISO', 1, 
   '2024-01-01 00:00:00', '2024-01-01 00:00:00');
```

## Relationships

- `market_node.iso_code` → `iso.iso_code` (many-to-one)
- `data_source.iso_code` → `iso.iso_code` (many-to-one)
- `ingestion_log.iso_code` → `iso.iso_code` (many-to-one)
- `url_registry.iso_code` → `iso.iso_code` (many-to-one)

## Notes

- **No actual market data**: This database only stores metadata. Market price data is stored in Parquet files.
- **Accumulates over time**: Ingestion logs and data sources accumulate as you import more data.
- **Query examples**: See `test_queries.py` for examples of querying this metadata.
