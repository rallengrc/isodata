#!/usr/bin/env python3
"""
Phase 1 – End-to-End Pipeline Bootstrap

This script:
- Creates real directories
- Initializes SQLite metadata DB
- Initializes DuckDB analytics DB
- Prepares Parquet storage layout
- Is cron-safe and idempotent

Run:
  python run_pipeline.py --init
"""

import argparse
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import duckdb

# -----------------------------
# Directory layout
# -----------------------------
BASE_DIR = Path(__file__).parent
DIRS = {
    "config": BASE_DIR / "config",
    "metadata": BASE_DIR / "metadata",
    "parquet": BASE_DIR / "data" / "parquet",
    "analytics_db": BASE_DIR / "analytics_db",
    "logs": BASE_DIR / "logs",
    "notebooks": BASE_DIR / "notebooks",
}

SQLITE_DB = DIRS["metadata"] / "metadata.db"
DUCKDB_DB = DIRS["analytics_db"] / "analytics.duckdb"

# -----------------------------
# SQLite schema
# -----------------------------
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS iso (
    iso_code TEXT PRIMARY KEY,
    name TEXT,
    market_start_year INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS market_node (
    iso_code TEXT,
    node_id TEXT,
    node_type TEXT,
    zone TEXT,
    valid_from DATE,
    valid_to DATE
);

CREATE TABLE IF NOT EXISTS dataset_version (
    dataset_name TEXT,
    version TEXT,
    created_at TIMESTAMP,
    description TEXT
);

CREATE TABLE IF NOT EXISTS data_source (
    dataset_name TEXT,
    source_url TEXT,
    iso_code TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_log (
    dataset_name TEXT,
    iso_code TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status TEXT,
    row_count INTEGER,
    error_message TEXT
);
"""

# -----------------------------
# DuckDB base views
# -----------------------------
DUCKDB_INIT_SQL = """
-- Base schema placeholder
-- Parquet-backed views will be added in Phase 2
"""

# -----------------------------
# Functions
# -----------------------------

def init_directories():
    for d in DIRS.values():
        d.mkdir(parents=True, exist_ok=True)


def init_sqlite():
    conn = sqlite3.connect(SQLITE_DB)
    conn.executescript(SQLITE_SCHEMA)
    conn.commit()
    conn.close()


def init_duckdb():
    con = duckdb.connect(DUCKDB_DB)
    con.execute(DUCKDB_INIT_SQL)
    con.close()


def log_ingestion(dataset, iso, status, rows=None, error=None, start_time=None, end_time=None):
    """
    Log ingestion event to SQLite.
    
    Args:
        dataset: Dataset name
        iso: ISO code
        status: Status (SUCCESS, ERROR, NO_DATA)
        rows: Number of rows ingested
        error: Error message if any
        start_time: Start time (defaults to now)
        end_time: End time (defaults to now)
    """
    conn = sqlite3.connect(SQLITE_DB)
    now = datetime.utcnow()
    start = start_time if start_time else now
    end = end_time if end_time else now
    
    conn.execute(
        """
        INSERT INTO ingestion_log
        (dataset_name, iso_code, start_time, end_time, status, row_count, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dataset,
            iso,
            start,
            end,
            status,
            rows,
            error,
        ),
    )
    conn.commit()
    conn.close()


# -----------------------------
# CLI
# -----------------------------

def main():
    parser = argparse.ArgumentParser(description="Power Market Pipeline")
    parser.add_argument("--init", action="store_true", help="Initialize pipeline storage")
    
    # Energy pipeline arguments
    parser.add_argument("--energy", action="store_true", help="Run energy price pipeline")
    parser.add_argument("--iso", type=str, help="ISO code (NYISO, EIA, etc.)")
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--product", type=str, default="DA", choices=["DA", "RT"], help="Product type (DA or RT)")
    parser.add_argument("--backfill", action="store_true", help="Backfill historical data")
    parser.add_argument("--start-year", type=int, help="Start year for backfill")
    parser.add_argument("--end-year", type=int, help="End year for backfill (defaults to current year)")
    
    args = parser.parse_args()

    if args.init:
        init_directories()
        init_sqlite()
        init_duckdb()
        print("✔ Pipeline directories created")
        print("✔ SQLite metadata DB initialized")
        print("✔ DuckDB analytics DB initialized")
        return
    
    if args.energy:
        from pipelines.energy_pipeline import run_energy_pipeline, backfill_energy_data
        from adapters.nyiso_energy import NYISOEnergyAdapter
        from adapters.eia import EIAAdapter
        
        # Parse dates (make timezone-aware)
        import pytz
        if args.start_date:
            start_date = datetime.fromisoformat(args.start_date)
            if start_date.tzinfo is None:
                start_date = pytz.UTC.localize(start_date)
        else:
            start_date = datetime.now(pytz.UTC) - timedelta(days=7)  # Default: last 7 days
        
        if args.end_date:
            end_date = datetime.fromisoformat(args.end_date)
            if end_date.tzinfo is None:
                end_date = pytz.UTC.localize(end_date)
        else:
            end_date = datetime.now(pytz.UTC)
        
        # Select adapter
        if args.iso == "NYISO":
            adapter = NYISOEnergyAdapter()
        elif args.iso == "EIA":
            print("ERROR: EIA does not provide hourly wholesale electricity prices.")
            print("       EIA provides demand/generation data, not price data.")
            print("       Use --iso NYISO (or other ISO adapters) for price data.")
            return
        else:
            print(f"Unknown ISO: {args.iso}")
            print("Available ISOs: NYISO")
            print("Note: EIA removed - does not provide hourly price data")
            return
        
        # Run pipeline
        if args.backfill:
            if not args.start_year:
                print("--start-year required for backfill")
                return
            result = backfill_energy_data(
                adapter=adapter,
                start_year=args.start_year,
                end_year=args.end_year,
                product=args.product,
            )
            print(f"\nBackfill completed:")
            print(f"  Total rows: {result['total_rows']}")
            print(f"  Total files: {result['total_files']}")
            print(f"  Errors: {result['error_count']}")
        else:
            result = run_energy_pipeline(
                adapter=adapter,
                start_date=start_date,
                end_date=end_date,
                product=args.product,
            )
            print(f"\nPipeline completed:")
            print(f"  Status: {result['status']}")
            print(f"  Rows: {result.get('rows', 0)}")
            print(f"  Files: {result.get('files', 0)}")
        return

    print("Nothing to do. Use --init or --energy")


if __name__ == "__main__":
    main()
