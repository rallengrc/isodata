#!/usr/bin/env python3
"""Test script for database queries - properly handles SQL quoting."""

from pathlib import Path
import duckdb
import sqlite3
from datetime import datetime

# Connect to databases
duckdb_path = Path('analytics_db/analytics.duckdb')
sqlite_path = Path('metadata/metadata.db')

duckdb_con = duckdb.connect(str(duckdb_path))
sqlite_con = sqlite3.connect(str(sqlite_path))

# Refresh DuckDB views to ensure they see latest Parquet files
from storage.duckdb_views import DuckDBViews
from pathlib import Path
parquet_base = Path('data/parquet')
parquet_files = list(parquet_base.rglob("*.parquet"))
print(f"Found {len(parquet_files)} Parquet file(s)")
if parquet_files:
    print(f"  Sample files: {parquet_files[:3]}")
print()
views = DuckDBViews(duckdb_path, parquet_base)
views.refresh_views()
views.close()
print("✓ DuckDB views refreshed")
print()

print("=" * 80)
print("Testing Database Queries")
print("=" * 80)
print()

# ============================================================================
# DUCKDB QUERIES (Market Data)
# ============================================================================

print("=" * 80)
print("DUCKDB QUERIES - Market Data")
print("=" * 80)
print()

# Test 1: Count records
print("Test 1: Counting NYISO records...")
result = duckdb_con.execute("SELECT COUNT(*) as total FROM market_prices WHERE iso_code = 'NYISO'").fetchone()
print(f"✓ NYISO records in database: {result[0]}")
print()

# Test 2: Average prices by zone
print("Test 2: Average prices by zone...")
df = duckdb_con.execute("""
    SELECT zone, AVG(CASE WHEN market_type = 'ENERGY' THEN COALESCE(price_energy, price) ELSE COALESCE(price_capacity, price) END) as avg_price, COUNT(*) as count
    FROM market_prices 
    WHERE iso_code = 'NYISO' 
    GROUP BY zone 
    ORDER BY avg_price DESC
    LIMIT 10
""").df()
print(df)
print()

# Test 3: Date range
print("Test 3: Date range of data...")
date_range = duckdb_con.execute("""
    SELECT 
        MIN(start_time) as earliest,
        MAX(start_time) as latest,
        COUNT(DISTINCT zone) as zone_count
    FROM market_prices 
    WHERE iso_code = 'NYISO'
""").fetchone()
print(f"✓ Date range: {date_range[0]} to {date_range[1]}")
print(f"✓ Zones: {date_range[2]}")
print()

# Test 4: Sample records
print("Test 4: Sample records...")
samples = duckdb_con.execute("""
    SELECT iso_code, zone, start_time, CASE WHEN market_type = 'ENERGY' THEN COALESCE(price_energy, price) ELSE COALESCE(price_capacity, price) END as price
    FROM market_prices 
    WHERE iso_code = 'NYISO'
    ORDER BY start_time DESC
    LIMIT 5
""").df()
print(samples)
print()

# ============================================================================
# SQLITE QUERIES (Metadata)
# ============================================================================

print("=" * 80)
print("SQLITE QUERIES - Metadata")
print("=" * 80)
print()

# Metadata Test 1: Recent ingestion logs
print("Metadata Test 1: Recent ingestion logs (last 10)...")
sqlite_con.row_factory = sqlite3.Row
cursor = sqlite_con.execute("""
    SELECT 
        dataset_name,
        iso_code,
        status,
        row_count,
        start_time,
        end_time,
        CASE 
            WHEN end_time IS NOT NULL AND start_time IS NOT NULL 
            THEN ROUND((julianday(end_time) - julianday(start_time)) * 24 * 60, 2)
            ELSE NULL
        END as duration_minutes
    FROM ingestion_log
    ORDER BY start_time DESC
    LIMIT 10
""")
rows = cursor.fetchall()
if rows:
    # Use wider columns and truncate very long dataset names for readability
    print(f"{'Dataset':<60} {'ISO':<8} {'Status':<10} {'Rows':<10} {'Duration (min)':<15} {'Start Time'}")
    print("-" * 140)
    for row in rows:
        duration = f"{row['duration_minutes']:.2f}" if row['duration_minutes'] else "N/A"
        start_time = row['start_time'][:19] if row['start_time'] else "N/A"
        dataset = row['dataset_name'] or ""
        if len(dataset) > 57:
            dataset = dataset[:57] + "..."
        print(f"{dataset:<60} {row['iso_code']:<8} {row['status']:<10} {row['row_count'] or 0:<10} {duration:<15} {start_time}")
else:
    print("  No ingestion logs found")
print()

# Metadata Test 2: Ingestion statistics by ISO
print("Metadata Test 2: Ingestion statistics by ISO...")
cursor = sqlite_con.execute("""
    SELECT 
        iso_code,
        COUNT(*) as total_runs,
        SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
        SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as failed,
        SUM(CASE WHEN status = 'NO_DATA' THEN 1 ELSE 0 END) as no_data,
        SUM(row_count) as total_rows,
        MIN(start_time) as first_ingestion,
        MAX(start_time) as last_ingestion
    FROM ingestion_log
    GROUP BY iso_code
    ORDER BY iso_code
""")
rows = cursor.fetchall()
if rows:
    print(f"{'ISO':<8} {'Runs':<8} {'Success':<10} {'Failed':<10} {'No Data':<10} {'Total Rows':<15} {'First':<20} {'Last'}")
    print("-" * 120)
    for row in rows:
        first = row['first_ingestion'][:19] if row['first_ingestion'] else "N/A"
        last = row['last_ingestion'][:19] if row['last_ingestion'] else "N/A"
        print(f"{row['iso_code']:<8} {row['total_runs']:<8} {row['successful']:<10} {row['failed']:<10} {row['no_data']:<10} {row['total_rows'] or 0:<15} {first:<20} {last}")
else:
    print("  No ingestion logs found")
print()

# Metadata Test 3: Ingestion statistics by dataset
print("Metadata Test 3: Ingestion statistics by dataset...")
cursor = sqlite_con.execute("""
    SELECT 
        dataset_name,
        iso_code,
        COUNT(*) as total_runs,
        SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
        SUM(row_count) as total_rows,
        AVG(row_count) as avg_rows_per_run,
        MAX(start_time) as last_run
    FROM ingestion_log
    GROUP BY dataset_name, iso_code
    ORDER BY last_run DESC
    LIMIT 15
""")
rows = cursor.fetchall()
if rows:
    print(f"{'Dataset':<60} {'ISO':<8} {'Runs':<8} {'Success':<10} {'Total Rows':<15} {'Avg Rows':<12} {'Last Run'}")
    print("-" * 140)
    for row in rows:
        avg_rows = f"{row['avg_rows_per_run']:.0f}" if row['avg_rows_per_run'] else "0"
        last_run = row['last_run'][:19] if row['last_run'] else "N/A"
        dataset = row['dataset_name'] or ""
        if len(dataset) > 57:
            dataset = dataset[:57] + "..."
        print(f"{dataset:<60} {row['iso_code']:<8} {row['total_runs']:<8} {row['successful']:<10} {row['total_rows'] or 0:<15} {avg_rows:<12} {last_run}")
else:
    print("  No ingestion logs found")
print()

# Metadata Test 4: Data sources
print("Metadata Test 4: Data sources...")
cursor = sqlite_con.execute("""
    SELECT 
        dataset_name,
        iso_code,
        source_url
    FROM data_source
    ORDER BY dataset_name, iso_code
    LIMIT 20
""")
rows = cursor.fetchall()
if rows:
    print(f"{'Dataset':<60} {'ISO':<8} {'Filename':<40} {'Source URL'}")
    print("-" * 160)
    for row in rows:
        dataset = row['dataset_name'] or ""
        if len(dataset) > 57:
            dataset = dataset[:57] + "..."
        source_url_val = row['source_url'] or ""
        # Extract just the filename (useful for Excel imports)
        filename = source_url_val.split("\\")[-1].split("/")[-1] if source_url_val else ""
        if len(filename) > 37:
            filename_print = filename[:37] + "..."
        else:
            filename_print = filename
        url = source_url_val[:70] + "..." if len(source_url_val) > 70 else source_url_val
        print(f"{dataset:<60} {row['iso_code']:<8} {filename_print:<40} {url}")
else:
    print("  No data sources found")
print()

# Metadata Test 5: Failed ingestions
print("Metadata Test 5: Failed ingestions (last 10)...")
cursor = sqlite_con.execute("""
    SELECT 
        dataset_name,
        iso_code,
        start_time,
        error_message
    FROM ingestion_log
    WHERE status = 'ERROR'
    ORDER BY start_time DESC
    LIMIT 10
""")
rows = cursor.fetchall()
if rows:
    print(f"{'Dataset':<60} {'ISO':<8} {'Start Time':<20} {'Error Message'}")
    print("-" * 140)
    for row in rows:
        error = row['error_message'][:50] + "..." if row['error_message'] and len(row['error_message']) > 50 else (row['error_message'] or "N/A")
        start_time = row['start_time'][:19] if row['start_time'] else "N/A"
        dataset = row['dataset_name'] or ""
        if len(dataset) > 57:
            dataset = dataset[:57] + "..."
        print(f"{dataset:<60} {row['iso_code']:<8} {start_time:<20} {error}")
else:
    print("  No failed ingestions found")
print()

# Metadata Test 6: ISO information
print("Metadata Test 6: ISO information...")
cursor = sqlite_con.execute("""
    SELECT 
        iso_code,
        name,
        market_start_year,
        notes
    FROM iso
    ORDER BY iso_code
""")
rows = cursor.fetchall()
if rows:
    # Calculate column widths based on data
    max_code_len = max(len(row['iso_code']) for row in rows) if rows else 8
    max_name_len = max(len(row['name'] or '') for row in rows) if rows else 20
    max_year_len = 12  # "Start Year" header
    
    # Set minimum widths
    code_width = max(max_code_len + 2, 12)
    name_width = max(max_name_len + 2, 35)
    year_width = max_year_len
    
    # Print header
    header = f"{'ISO Code':<{code_width}} {'Name':<{name_width}} {'Start Year':<{year_width}} {'Notes'}"
    print(header)
    print("-" * len(header))
    
    # Print rows with full notes (no truncation)
    for row in rows:
        iso_code = row['iso_code'] or 'N/A'
        name = row['name'] or 'N/A'
        year = str(row['market_start_year']) if row['market_start_year'] else 'N/A'
        notes = row['notes'] or ''
        print(f"{iso_code:<{code_width}} {name:<{name_width}} {year:<{year_width}} {notes}")
else:
    print("  No ISO information found")
print()

# Metadata Test 7: Success rate summary
print("Metadata Test 7: Overall success rate...")
cursor = sqlite_con.execute("""
    SELECT 
        COUNT(*) as total_runs,
        SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
        SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as failed,
        SUM(CASE WHEN status = 'NO_DATA' THEN 1 ELSE 0 END) as no_data,
        ROUND(100.0 * SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct
    FROM ingestion_log
""")
row = cursor.fetchone()
if row and row['total_runs'] > 0:
    print(f"  Total runs: {row['total_runs']}")
    print(f"  Successful: {row['successful']}")
    print(f"  Failed: {row['failed']}")
    print(f"  No data: {row['no_data']}")
    print(f"  Success rate: {row['success_rate_pct']}%")
else:
    print("  No ingestion logs found")
print()

# Metadata Test 8: URL registry dump
print("Metadata Test 8: URL registry...")
cursor = sqlite_con.execute("""
    SELECT 
        url_key,
        iso_code,
        active,
        url,
        description
    FROM url_registry
    ORDER BY iso_code, url_key
""")
rows = cursor.fetchall()
if rows:
    print(f"{'Key':<25} {'ISO':<8} {'Active':<8} {'URL':<60} {'Description'}")
    print("-" * 140)
    for row in rows:
        url_key = row[0] or ""
        iso_code = row[1] or ""
        active = "yes" if row[2] else "no"
        url = row[3] or ""
        desc = row[4] or ""
        if len(url) > 57:
            url_print = url[:57] + "..."
        else:
            url_print = url
        if len(desc) > 40:
            desc_print = desc[:40] + "..."
        else:
            desc_print = desc
        print(f"{url_key:<25} {iso_code:<8} {active:<8} {url_print:<60} {desc_print}")
else:
    print("  No URL registry entries found")
print()

# Close connections
duckdb_con.close()
sqlite_con.close()

print("=" * 80)
print("All queries completed successfully!")
print("=" * 80)

