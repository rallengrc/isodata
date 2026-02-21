# Parquet Data Schema

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
│                                                              │
│  IDENTIFIERS                                                 │
│  ├─ iso_code: str                    (e.g., 'NYISO')        │
│  ├─ market_type: MarketType          (ENERGY, CAPACITY)     │
│  ├─ product: Product                 (ENERGY_DA, etc.)      │
│  ├─ node_id: str                     (e.g., 'NYC')          │
│  ├─ node_type: NodeType              (NODE, ZONE, HUB)      │
│  └─ zone: Optional[str]              (normalized zone)     │
│                                                              │
│  TEMPORAL FIELDS (Full Precision)                           │
│  ├─ start_time: datetime             (period start)         │
│  └─ end_time: datetime               (period end)           │
│                                                              │
│  TEMPORAL FIELDS (Month-Level Aggregation)                  │
│  ├─ auction_month: str                (YYYYMM, e.g., '202401')│
│  └─ delivery_month: str              (YYYYMM, e.g., '202401')│
│                                                              │
│  CAPACITY MARKET SPECIFIC                                   │
│  ├─ capability_period: Optional[str]  (SUMMER, WINTER)      │
│  ├─ auction_type: Optional[str]      (MONTHLY, STRIP, SPOT)│
│  ├─ awarded_mw: Optional[float]      (cleared quantity)    │
│  ├─ posted_at: Optional[datetime]   (when posted)         │
│  └─ season_id: Optional[str]         (NYISO season ID)      │
│                                                              │
│  PRICE FIELDS (Separate by Market Type)                     │
│  ├─ price_energy: Optional[float]    ($/MWh, ENERGY only)   │
│  ├─ price_capacity: Optional[float]  ($/kW-month, CAPACITY)│
│  └─ unit: str                        (unit metadata)        │
│                                                              │
│  ZONE NORMALIZATION TRACKING                                │
│  ├─ zone_normalized: Optional[str]   (normalized name)      │
│  └─ zone_original: Optional[str]     (original from source) │
│                                                              │
│  DATA QUALITY TRACKING                                      │
│  ├─ data_quality_score: Optional[float] (0.0 to 1.0)        │
│  └─ validation_errors: Optional[List[str]]                  │
│                                                              │
│  METADATA                                                    │
│  ├─ auction_id: Optional[str]        (auction identifier)   │
│  ├─ source_url: Optional[str]        (where data came from) │
│  └─ ingested_at: datetime            (when imported)        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Field Definitions

### Identifiers

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `iso_code` | `str` | Yes | ISO identifier: 'NYISO', 'PJM', 'EIA', etc. |
| `market_type` | `MarketType` | Yes | Enum: 'ENERGY', 'CAPACITY', 'ANCILLARY' |
| `product` | `Product` | Yes | Enum: 'ENERGY_DA', 'ENERGY_RT', 'CAPACITY_MONTHLY', etc. |
| `node_id` | `str` | Yes | Node/zone identifier (e.g., 'NYC', 'WEST') |
| `node_type` | `NodeType` | Yes | Enum: 'NODE', 'ZONE', 'HUB' |
| `zone` | `Optional[str]` | No | Normalized zone name (if applicable) |

### Temporal Fields (Full Precision)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start_time` | `datetime` | Yes | Period start time (exact timestamp, timezone-aware) |
| `end_time` | `datetime` | Yes | Period end time (exact timestamp, timezone-aware) |

### Temporal Fields (Month-Level Aggregation)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `auction_month` | `str` | Yes | Auction/market clearing month in YYYYMM format (e.g., '202401') |
| `delivery_month` | `str` | Yes | Delivery/application month in YYYYMM format (e.g., '202401') |

### Capacity Market Specific

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `capability_period` | `Optional[str]` | No | 'SUMMER' or 'WINTER' for capacity markets |
| `auction_type` | `Optional[str]` | No | 'MONTHLY', 'STRIP', or 'SPOT' for capacity markets |
| `awarded_mw` | `Optional[float]` | No | Awarded/cleared quantity in MW (for capacity markets) |
| `posted_at` | `Optional[datetime]` | No | When auction results were posted/published |
| `season_id` | `Optional[str]` | No | NYISO season/capability period ID (e.g., '702409') |

### Price Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `price_energy` | `Optional[float]` | Conditional | Energy price in $/MWh (required if market_type='ENERGY') |
| `price_capacity` | `Optional[float]` | Conditional | Capacity price in $/kW-month (required if market_type='CAPACITY') |
| `unit` | `str` | Yes | Price unit metadata: '$/MWh' or '$/kW-month' |

**Important:** 
- For ENERGY records: `price_energy` must be set, `price_capacity` must be NULL
- For CAPACITY records: `price_capacity` must be set, `price_energy` must be NULL
- This prevents mixing Power (kW) and Energy (kWh/MWh) units

### Zone Normalization Tracking

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `zone_normalized` | `Optional[str]` | No | Normalized zone name (e.g., 'NYC' from 'N.Y.C.') |
| `zone_original` | `Optional[str]` | No | Original zone name from source data |

### Data Quality Tracking

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `data_quality_score` | `Optional[float]` | No | Data quality score from 0.0 to 1.0 (1.0 = perfect) |
| `validation_errors` | `Optional[List[str]]` | No | List of validation error messages (if any) |

### Metadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `auction_id` | `Optional[str]` | No | Auction identifier if applicable |
| `source_url` | `Optional[str]` | No | Source URL or file path where data came from |
| `ingested_at` | `datetime` | Yes | Timestamp when record was ingested (auto-generated) |

## Partitioning Strategy

Parquet files are partitioned by:
1. `iso_code` (e.g., 'NYISO')
2. `market_type` (e.g., 'ENERGY', 'CAPACITY')
3. `year` (extracted from `delivery_month`, e.g., 2024)
4. `month` (extracted from `delivery_month`, e.g., 01)

For capacity markets with `auction_type`, files are further split:
- `data_2023_11_monthly.parquet` (MONTHLY auctions)
- `data_2023_11_strip.parquet` (STRIP auctions)

## Example Records

### Energy Market Record

```python
{
    "iso_code": "NYISO",
    "market_type": "ENERGY",
    "product": "ENERGY_DA",
    "node_id": "NYC",
    "node_type": "ZONE",
    "zone": "NYC",
    "start_time": "2024-01-15T10:00:00Z",
    "end_time": "2024-01-15T11:00:00Z",
    "auction_month": "202401",
    "delivery_month": "202401",
    "capability_period": None,
    "auction_type": None,
    "price_energy": 45.23,
    "price_capacity": None,
    "unit": "$/MWh",
    "awarded_mw": None,
    "posted_at": None,
    "season_id": None,
    "zone_normalized": "NYC",
    "zone_original": "NYC",
    "data_quality_score": 1.0,
    "validation_errors": None,
    "auction_id": None,
    "source_url": "https://mis.nyiso.com/public/",
    "ingested_at": "2024-01-15T12:00:00Z"
}
```

### Capacity Market Record

```python
{
    "iso_code": "NYISO",
    "market_type": "CAPACITY",
    "product": "CAPACITY_MONTHLY",
    "node_id": "NYC",
    "node_type": "ZONE",
    "zone": "NYC",
    "start_time": "2023-11-01T00:00:00Z",
    "end_time": "2023-12-01T00:00:00Z",
    "auction_month": "202310",
    "delivery_month": "202311",
    "capability_period": "WINTER",
    "auction_type": "MONTHLY",
    "price_energy": None,
    "price_capacity": 8.50,
    "unit": "$/kW-month",
    "awarded_mw": 1500.0,
    "posted_at": "2023-10-15T14:00:00Z",
    "season_id": "702409",
    "zone_normalized": "NYC",
    "zone_original": "NYC",
    "data_quality_score": 1.0,
    "validation_errors": None,
    "auction_id": "2023-11-MONTHLY",
    "source_url": "https://icappublic.nyiso.com/ucap/public/auc_view_monthly_detail.do",
    "ingested_at": "2024-01-15T12:00:00Z"
}
```

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
