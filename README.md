# Power Market Data Pipeline

A comprehensive pipeline for aggregating and analyzing historical power market data from U.S. Independent System Operators (ISOs).

## Overview

This pipeline aggregates energy and capacity market data from multiple ISOs, normalizes it into a canonical schema, and stores it for analysis. The system is designed to:

- **Ingest** data from NYISO, EIA, and other ISOs
- **Normalize** data into a unified schema
- **Store** in Parquet format with partitioning
- **Analyze** using DuckDB for fast SQL queries
- **Track** metadata and ingestion logs in SQLite
- **Search** semantically using Qdrant (Phase 5)

## Architecture

```
ISO Adapters (NYISO, EIA, etc.)
    ↓
Canonical Schema (Normalization)
    ↓
Parquet Storage (Partitioned by ISO/Market/Year/Month)
    ↓
DuckDB Analytics (SQL views over Parquet)
    ↓
SQLite Metadata (Ingestion logs, node definitions)
    ↓
Qdrant (Semantic search - Phase 5)
```

## Installation

1. **Clone the repository** (if applicable)

2. **Create virtual environment** (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Set environment variables** (optional but recommended):
```bash
# EIA API key (for higher rate limits)
export EIA_API_KEY="your_eia_api_key_here"

# OpenAI API key (for Phase 5 - natural language search)
export OPENAI_API_KEY="your_openai_api_key_here"
```

   On Windows (Git Bash):
```bash
export EIA_API_KEY="your_eia_api_key_here"
export OPENAI_API_KEY="your_openai_api_key_here"
```

   Get an EIA API key: https://www.eia.gov/opendata/register.php

5. **Initialize the pipeline**:
```bash
python run_pipeline.py --init
```

## Quick Start

### 1. Initialize Pipeline
```bash
python run_pipeline.py --init
```

This creates:
- Directory structure
- SQLite metadata database
- DuckDB analytics database

### 2. Fetch NYISO Energy Data

**Recent data (last 7 days)**:
```bash
python run_pipeline.py --energy --iso NYISO --product DA
```

**Specific date range**:
```bash
python run_pipeline.py --energy --iso NYISO --start-date 2024-01-01 --end-date 2024-01-31 --product DA
```

**Backfill historical data**:
```bash
python run_pipeline.py --energy --iso NYISO --backfill --start-year 2020 --end-year 2024 --product DA
```

### 3. Download and Import NYISO ICAP Excel Files

**Download Excel files from NYISO**:
```bash
# Download all available ICAP Market Report Excel files
python scripts/download_nyiso_excel.py

# Download only files from 2024 onwards
python scripts/download_nyiso_excel.py --start-date 2024-01-01

# Download files for a specific year
python scripts/download_nyiso_excel.py --start-date 2023-01-01 --end-date 2023-12-31
```

Files are saved to `data/excel/nyiso/` by default.

**Import downloaded Excel files**:
```bash
# Import from Excel file (all auction types)
python run_pipeline.py --capacity --iso NYISO --excel-file data/excel/nyiso/ICAP-Market-Report-July-2024.xlsx

# Import only specific auction types
python run_pipeline.py --capacity --iso NYISO --excel-file data/excel/nyiso/ICAP-Market-Report-July-2024.xlsx --excel-auction-types MONTHLY STRIP
```

### 4. Explore Data in Jupyter

```bash
jupyter notebook notebooks/phase2_demo.ipynb
```

## Project Structure

```
power-market-pipeline/
├── adapters/              # ISO data adapters
│   ├── base.py           # Base adapter interface
│   ├── nyiso_energy.py   # NYISO adapter (NYISOToolkit)
│   └── eia.py            # EIA API adapter
├── canonical/            # Canonical schemas
│   ├── schemas.py        # Pydantic models
│   └── normalize.py      # Normalization utilities
├── storage/              # Storage layer
│   ├── parquet_writer.py # Parquet writer with partitioning
│   └── duckdb_views.py    # DuckDB views manager
├── pipelines/           # Pipeline runners
│   └── energy_pipeline.py # Energy price pipeline
├── notebooks/           # Jupyter notebooks
│   └── phase2_demo.ipynb
├── data/               # Data storage
│   └── parquet/        # Parquet files (partitioned)
├── metadata/           # Metadata
│   └── metadata.db     # SQLite database
├── duckdb/             # Analytics
│   └── analytics.duckdb # DuckDB database
├── run_pipeline.py     # Main CLI
└── requirements.txt    # Dependencies
```

## Data Schema

### MarketPriceFact (Canonical Schema)

All market data is normalized into this schema:

- `iso_code`: ISO identifier (NYISO, PJM, etc.)
- `market_type`: ENERGY, CAPACITY, or ANCILLARY
- `product`: ENERGY_DA, ENERGY_RT, CAPACITY_MONTHLY, etc.
- `node_id`: Node/zone identifier
- `node_type`: NODE, ZONE, or HUB
- `zone`: Zone name (if applicable)
- `start_time`: Period start time
- `end_time`: Period end time
- `price`: Price value
- `unit`: Price unit ($/MWh, $/kW-month, etc.)
- `auction_id`: Auction identifier (for capacity markets)
- `source_url`: Source URL
- `ingested_at`: Ingestion timestamp

## Storage Layout

Parquet files are partitioned as:
```
data/parquet/
  {iso_code}/
    {market_type}/
      {year}/
        {month}/
          data_{year}_{month}.parquet
```

Example:
```
data/parquet/NYISO/ENERGY/2024/01/data_2024_01.parquet
```

## DuckDB Views

The pipeline creates several views for easy querying:

- `energy_prices`: All energy prices
- `energy_prices_da`: Day-ahead energy prices
- `energy_prices_rt`: Real-time energy prices
- `energy_prices_by_iso`: Prices grouped by ISO
- `capacity_prices`: Capacity market prices
- `market_prices`: Unified view across all markets

## CLI Usage

### Initialize
```bash
python run_pipeline.py --init
```

### Energy Pipeline
```bash
# Recent data
python run_pipeline.py --energy --iso NYISO --product DA

# Date range
python run_pipeline.py --energy --iso NYISO --start-date 2024-01-01 --end-date 2024-01-31

# Backfill
python run_pipeline.py --energy --iso NYISO --backfill --start-year 2020
```

## Automation

### Cron Example (Linux/Mac)
```bash
# Daily update at 6 AM
0 6 * * * cd /path/to/pipeline && python run_pipeline.py --energy --iso NYISO --product DA
```

### Windows Task Scheduler
Create a task that runs:
```cmd
python C:\path\to\pipeline\run_pipeline.py --energy --iso NYISO --product DA
```

## Phase Status

- ✅ **Phase 1**: Foundation & Storage
- ✅ **Phase 2**: NYISO Energy Prices
- 🔄 **Phase 3**: NYISO ICAP (Capacity Market) - IN PROGRESS
  - ✅ Monthly auction HTML scraping
  - ✅ Strip auction HTML scraping
  - ✅ ROS data parsing
  - ✅ Excel historical data import
  - ⏳ Spot auction support (moved to Phase 7 - low priority)
- ⏳ **Phase 4**: Analytics + Jupyter Frontend + PUDL Integration
- ⏳ **Phase 5**: Additional ISOs (PJM, ISO-NE, MISO, CAISO, ERCOT, SPP)
- ⏳ **Phase 6**: Natural Language Search (Qdrant + OpenAI)
- ⏳ **Phase 7**: Spot Auction Support (low priority - rare events)

## Supported ISOs

Currently implemented:
- **NYISO**: Energy prices via NYISOToolkit ✅

Planned:
- PJM
- ISO-NE
- MISO
- CAISO
- ERCOT
- SPP

**Note on EIA**: EIA does NOT provide hourly wholesale electricity prices. 
EIA is kept for potential future use with complementary data (demand, generation, fuel mix).
For price data, always use direct ISO sources.

## Dependencies

- `duckdb`: Analytics database
- `pydantic`: Data validation
- `pandas`: Data manipulation
- `pyarrow`: Parquet I/O
- `nyisotoolkit`: NYISO data access
- `requests`: HTTP requests
- `matplotlib`, `seaborn`: Visualization
- `jupyter`: Notebooks

## Notes

- **NYISOToolkit**: Required for NYISO data. Install separately if needed.
- **EIA API Key**: Optional but recommended for higher rate limits.
- **Historical Data**: Availability varies by ISO (2000-2024 typically available).

## License

[Add your license here]

## Contributing

[Add contribution guidelines if applicable]

