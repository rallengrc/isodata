#!/usr/bin/env python3
"""Test script for database queries - properly handles SQL quoting."""

from pathlib import Path
import duckdb

# Connect to database (directory renamed to avoid import conflict)
db_path = Path('analytics_db/analytics.duckdb')
con = duckdb.connect(str(db_path))

print("=" * 60)
print("Testing Database Queries")
print("=" * 60)
print()

# Test 1: Count records
print("Test 1: Counting NYISO records...")
result = con.execute("SELECT COUNT(*) as total FROM market_prices WHERE iso_code = 'NYISO'").fetchone()
print(f"✓ NYISO records in database: {result[0]}")
print()

# Test 2: Average prices by zone
print("Test 2: Average prices by zone...")
df = con.execute("""
    SELECT zone, AVG(price) as avg_price, COUNT(*) as count
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
date_range = con.execute("""
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
samples = con.execute("""
    SELECT iso_code, zone, start_time, price
    FROM market_prices 
    WHERE iso_code = 'NYISO'
    ORDER BY start_time DESC
    LIMIT 5
""").df()
print(samples)
print()

con.close()
print("=" * 60)
print("All queries completed successfully!")
print("=" * 60)

