"""
Query NYISO Energy and Capacity Market Data.

Demonstrates both DuckDB (recommended) and Parquet (direct) approaches.
Supports both ENERGY and CAPACITY market types, including MONTHLY and STRIP auctions.
"""

import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

# Paths
DUCKDB_PATH = Path("analytics_db/analytics.duckdb")
PARQUET_BASE = Path("data/parquet")

print("=" * 80)
print("NYISO Market Data Query Utility")
print("=" * 80)

# ============================================================================
# Option 1: DuckDB (RECOMMENDED - Easier, SQL-based)
# ============================================================================

print("\n" + "=" * 80)
print("OPTION 1: DuckDB (Recommended)")
print("=" * 80)

con = duckdb.connect(str(DUCKDB_PATH))

# ============================================================================
# SECTION A: CAPACITY DATA QUERIES
# ============================================================================

print("\n" + "=" * 80)
print("SECTION A: CAPACITY MARKET DATA")
print("=" * 80)

# Query A1: All Winter 2023-2024 capacity data
print("\nA1. All Winter 2023-2024 Capacity Data:")
print("-" * 80)
query_a1 = """
SELECT 
    iso_code,
    zone,
    auction_month,
    delivery_month,
    capability_period,
    auction_type,
    price,
    unit,
    awarded_mw,
    posted_at,
    season_id
FROM market_prices
WHERE market_type = 'CAPACITY'
  AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
ORDER BY delivery_month, zone
"""
df_a1 = con.execute(query_a1).df()
print(df_a1.to_string(index=False))
print(f"\nTotal capacity records: {len(df_a1)}")

# Query A2: Capacity summary by zone
print("\n\nA2. Capacity Summary by Zone:")
print("-" * 80)
query_a2 = """
SELECT 
    zone,
    COUNT(*) as record_count,
    MIN(price) as min_price,
    MAX(price) as max_price,
    AVG(price) as avg_price,
    SUM(awarded_mw) as total_awarded_mw
FROM market_prices
WHERE market_type = 'CAPACITY'
  AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
GROUP BY zone
ORDER BY avg_price DESC
"""
df_a2 = con.execute(query_a2).df()
print(df_a2.to_string(index=False))

# Query A3: Capacity price trends by delivery month (NYC)
print("\n\nA3. Capacity Price Trends by Delivery Month (NYC):")
print("-" * 80)
query_a3 = """
SELECT 
    delivery_month,
    price,
    awarded_mw,
    auction_month
FROM market_prices
WHERE market_type = 'CAPACITY'
  AND zone = 'NYC'
  AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
ORDER BY delivery_month
"""
df_a3 = con.execute(query_a3).df()
print(df_a3.to_string(index=False))

# Query A4: Capacity price matrix (zones × delivery months)
print("\n\nA4. Capacity Price Matrix: Zones × Delivery Months:")
print("-" * 80)
query_a4 = """
SELECT 
    zone,
    MAX(CASE WHEN delivery_month = '202311' THEN price END) as Nov_2023,
    MAX(CASE WHEN delivery_month = '202312' THEN price END) as Dec_2023,
    MAX(CASE WHEN delivery_month = '202401' THEN price END) as Jan_2024,
    MAX(CASE WHEN delivery_month = '202402' THEN price END) as Feb_2024,
    MAX(CASE WHEN delivery_month = '202403' THEN price END) as Mar_2024,
    MAX(CASE WHEN delivery_month = '202404' THEN price END) as Apr_2024
FROM market_prices
WHERE market_type = 'CAPACITY'
  AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
GROUP BY zone
ORDER BY zone
"""
df_a4 = con.execute(query_a4).df()
print(df_a4.to_string(index=False))

# Query A5: Strip auction data summary
print("\n\nA5. Strip Auction Data Summary:")
print("-" * 80)
query_a5 = """
SELECT 
    zone,
    capability_period,
    COUNT(*) as record_count,
    MIN(price) as min_price,
    MAX(price) as max_price,
    AVG(price) as avg_price,
    SUM(awarded_mw) as total_awarded_mw,
    MIN(delivery_month) as first_delivery_month,
    MAX(delivery_month) as last_delivery_month
FROM market_prices
WHERE market_type = 'CAPACITY'
  AND auction_type = 'STRIP'
  AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
GROUP BY zone, capability_period
ORDER BY zone
"""
df_a5 = con.execute(query_a5).df()
if len(df_a5) > 0:
    print(df_a5.to_string(index=False))
else:
    print("No strip auction data found")

# Query A6: MONTHLY vs STRIP price comparison
print("\n\nA6. MONTHLY vs STRIP Price Comparison (by Zone):")
print("-" * 80)
query_a6 = """
SELECT 
    zone,
    auction_type,
    COUNT(*) as record_count,
    AVG(price) as avg_price,
    MIN(price) as min_price,
    MAX(price) as max_price,
    AVG(awarded_mw) as avg_awarded_mw
FROM market_prices
WHERE market_type = 'CAPACITY'
  AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
  AND auction_type IN ('MONTHLY', 'STRIP')
GROUP BY zone, auction_type
ORDER BY zone, auction_type
"""
df_a6 = con.execute(query_a6).df()
if len(df_a6) > 0:
    print(df_a6.to_string(index=False))
else:
    print("No auction type comparison data found")

# Query A7: Strip auction price by delivery month (NYC)
print("\n\nA7. Strip Auction Price by Delivery Month (NYC):")
print("-" * 80)
query_a7 = """
SELECT 
    delivery_month,
    price,
    awarded_mw,
    auction_month,
    capability_period
FROM market_prices
WHERE market_type = 'CAPACITY'
  AND auction_type = 'STRIP'
  AND zone = 'NYC'
  AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
ORDER BY delivery_month
"""
df_a7 = con.execute(query_a7).df()
if len(df_a7) > 0:
    print(df_a7.to_string(index=False))
else:
    print("No strip auction data found for NYC")

# Query A8: All auction types summary
print("\n\nA8. Capacity Auction Types Summary:")
print("-" * 80)
query_a8 = """
SELECT 
    auction_type,
    COUNT(*) as total_records,
    COUNT(DISTINCT zone) as zone_count,
    COUNT(DISTINCT delivery_month) as delivery_month_count,
    AVG(price) as avg_price,
    MIN(price) as min_price,
    MAX(price) as max_price
FROM market_prices
WHERE market_type = 'CAPACITY'
  AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
GROUP BY auction_type
ORDER BY auction_type
"""
df_a8 = con.execute(query_a8).df()
if len(df_a8) > 0:
    print(df_a8.to_string(index=False))
else:
    print("No capacity auction data found")

# ============================================================================
# SECTION B: ENERGY DATA QUERIES
# ============================================================================

print("\n\n" + "=" * 80)
print("SECTION B: ENERGY MARKET DATA")
print("=" * 80)

# Query B1: Recent energy prices (last 7 days or available data)
print("\nB1. Recent Energy Prices (Sample):")
print("-" * 80)
query_b1 = """
SELECT 
    iso_code,
    zone,
    start_time,
    end_time,
    product,
    price,
    unit
FROM market_prices
WHERE market_type = 'ENERGY'
  AND iso_code = 'NYISO'
ORDER BY start_time DESC
LIMIT 20
"""
df_b1 = con.execute(query_b1).df()
if len(df_b1) > 0:
    print(df_b1.to_string(index=False))
    print(f"\nShowing first 20 of available energy records")
else:
    print("No energy data found in database")

# Query B2: Energy summary by zone
print("\n\nB2. Energy Price Summary by Zone:")
print("-" * 80)
query_b2 = """
SELECT 
    zone,
    product,
    COUNT(*) as record_count,
    MIN(price) as min_price,
    MAX(price) as max_price,
    AVG(price) as avg_price,
    MIN(start_time) as earliest_time,
    MAX(start_time) as latest_time
FROM market_prices
WHERE market_type = 'ENERGY'
  AND iso_code = 'NYISO'
GROUP BY zone, product
ORDER BY zone, product
"""
df_b2 = con.execute(query_b2).df()
if len(df_b2) > 0:
    print(df_b2.to_string(index=False))
else:
    print("No energy data found in database")

# Query B3: Energy price trends by hour (NYC, Day-Ahead)
print("\n\nB3. Energy Price Trends by Hour (NYC, Day-Ahead, Recent 24 hours):")
print("-" * 80)
query_b3 = """
SELECT 
    start_time,
    price,
    zone,
    product
FROM market_prices
WHERE market_type = 'ENERGY'
  AND iso_code = 'NYISO'
  AND zone = 'NYC'
  AND product = 'ENERGY_DA'
ORDER BY start_time DESC
LIMIT 24
"""
df_b3 = con.execute(query_b3).df()
if len(df_b3) > 0:
    print(df_b3.to_string(index=False))
else:
    print("No energy data found for NYC Day-Ahead")

# Query B4: Energy price statistics by product
print("\n\nB4. Energy Price Statistics by Product:")
print("-" * 80)
query_b4 = """
SELECT 
    product,
    COUNT(*) as record_count,
    COUNT(DISTINCT zone) as zone_count,
    MIN(price) as min_price,
    MAX(price) as max_price,
    AVG(price) as avg_price,
    STDDEV(price) as stddev_price
FROM market_prices
WHERE market_type = 'ENERGY'
  AND iso_code = 'NYISO'
GROUP BY product
ORDER BY product
"""
df_b4 = con.execute(query_b4).df()
if len(df_b4) > 0:
    print(df_b4.to_string(index=False))
else:
    print("No energy data found in database")

# Query B5: Energy prices by date (daily average)
print("\n\nB5. Daily Average Energy Prices (NYC, Day-Ahead):")
print("-" * 80)
query_b5 = """
SELECT 
    DATE(start_time) as date,
    AVG(price) as avg_price,
    MIN(price) as min_price,
    MAX(price) as max_price,
    COUNT(*) as hour_count
FROM market_prices
WHERE market_type = 'ENERGY'
  AND iso_code = 'NYISO'
  AND zone = 'NYC'
  AND product = 'ENERGY_DA'
GROUP BY DATE(start_time)
ORDER BY date DESC
LIMIT 10
"""
df_b5 = con.execute(query_b5).df()
if len(df_b5) > 0:
    print(df_b5.to_string(index=False))
else:
    print("No energy data found for NYC Day-Ahead")

# ============================================================================
# SECTION C: COMBINED ENERGY + CAPACITY QUERIES
# ============================================================================

print("\n\n" + "=" * 80)
print("SECTION C: COMBINED MARKET DATA")
print("=" * 80)

# Query C1: Data inventory
print("\nC1. Data Inventory Summary:")
print("-" * 80)
query_c1 = """
SELECT 
    market_type,
    iso_code,
    COUNT(*) as total_records,
    COUNT(DISTINCT zone) as zone_count,
    MIN(start_time) as earliest_time,
    MAX(start_time) as latest_time
FROM market_prices
WHERE iso_code = 'NYISO'
GROUP BY market_type, iso_code
ORDER BY market_type
"""
df_c1 = con.execute(query_c1).df()
print(df_c1.to_string(index=False))

# Query C2: All zones across both markets
print("\n\nC2. Zones Available in Each Market Type:")
print("-" * 80)
query_c2 = """
SELECT 
    market_type,
    zone,
    COUNT(*) as record_count,
    AVG(price) as avg_price
FROM market_prices
WHERE iso_code = 'NYISO'
GROUP BY market_type, zone
ORDER BY market_type, zone
"""
df_c2 = con.execute(query_c2).df()
print(df_c2.to_string(index=False))

# Query C3: Price comparison (NYC across markets)
print("\n\nC3. NYC Price Comparison: Energy vs Capacity:")
print("-" * 80)
query_c3 = """
SELECT 
    market_type,
    product,
    AVG(price) as avg_price,
    MIN(price) as min_price,
    MAX(price) as max_price,
    COUNT(*) as record_count
FROM market_prices
WHERE iso_code = 'NYISO'
  AND zone = 'NYC'
GROUP BY market_type, product
ORDER BY market_type, product
"""
df_c3 = con.execute(query_c3).df()
print(df_c3.to_string(index=False))

con.close()

# ============================================================================
# Option 2: Direct Parquet (Alternative - More Control)
# ============================================================================

print("\n\n" + "=" * 80)
print("OPTION 2: Direct Parquet (Alternative)")
print("=" * 80)

# Capacity Parquet files
print("\nC1. Capacity Parquet Files:")
print("-" * 80)
capacity_files = []
for month in ['11', '12']:  # 2023
    capacity_files.extend(list(PARQUET_BASE.glob(f"NYISO/CAPACITY/2023/{month}/*.parquet")))
for month in ['01', '02', '03', '04']:  # 2024
    capacity_files.extend(list(PARQUET_BASE.glob(f"NYISO/CAPACITY/2024/{month}/*.parquet")))

if capacity_files:
    print(f"Found {len(capacity_files)} Capacity Parquet files:")
    for f in capacity_files:
        print(f"  - {f}")
    
    # Load sample
    dfs_cap = []
    for file in capacity_files[:3]:  # Load first 3 as sample
        df = pd.read_parquet(file)
        dfs_cap.append(df)
    
    if dfs_cap:
        df_cap_sample = pd.concat(dfs_cap, ignore_index=True)
        print(f"\nSample capacity data ({len(df_cap_sample)} records):")
        print(df_cap_sample[['delivery_month', 'zone', 'price', 'awarded_mw', 'auction_month']].head(10).to_string(index=False))
else:
    print("No Capacity Parquet files found")

# Energy Parquet files
print("\n\nC2. Energy Parquet Files:")
print("-" * 80)
energy_files = []
for month in ['11', '12']:  # 2023
    energy_files.extend(list(PARQUET_BASE.glob(f"NYISO/ENERGY/2023/{month}/*.parquet")))
for month in ['01', '02', '03', '04']:  # 2024
    energy_files.extend(list(PARQUET_BASE.glob(f"NYISO/ENERGY/2024/{month}/*.parquet")))

if energy_files:
    print(f"Found {len(energy_files)} Energy Parquet files:")
    for f in energy_files:
        print(f"  - {f}")
    
    # Load sample
    dfs_energy = []
    for file in energy_files[:3]:  # Load first 3 as sample
        df = pd.read_parquet(file)
        dfs_energy.append(df)
    
    if dfs_energy:
        df_energy_sample = pd.concat(dfs_energy, ignore_index=True)
        print(f"\nSample energy data ({len(df_energy_sample)} records):")
        print(df_energy_sample[['start_time', 'zone', 'price', 'product']].head(10).to_string(index=False))
else:
    print("No Energy Parquet files found")

# ============================================================================
# Quick Reference Queries
# ============================================================================

print("\n\n" + "=" * 80)
print("QUICK REFERENCE: Common Queries")
print("=" * 80)

queries = {
    # Capacity queries
    "All capacity data": """
        SELECT * FROM market_prices 
        WHERE market_type = 'CAPACITY'
        ORDER BY delivery_month, zone
    """,
    "Capacity: NYC prices only": """
        SELECT delivery_month, price, awarded_mw, auction_type
        FROM market_prices 
        WHERE market_type = 'CAPACITY' AND zone = 'NYC'
        ORDER BY delivery_month, auction_type
    """,
    "Capacity: Average price by zone": """
        SELECT zone, AVG(price) as avg_price 
        FROM market_prices 
        WHERE market_type = 'CAPACITY'
        GROUP BY zone
        ORDER BY avg_price DESC
    """,
    "Capacity: Strip auction data": """
        SELECT zone, delivery_month, price, awarded_mw, capability_period
        FROM market_prices 
        WHERE market_type = 'CAPACITY' AND auction_type = 'STRIP'
        ORDER BY delivery_month, zone
    """,
    "Capacity: MONTHLY vs STRIP comparison": """
        SELECT zone, auction_type, AVG(price) as avg_price, COUNT(*) as records
        FROM market_prices 
        WHERE market_type = 'CAPACITY' AND auction_type IN ('MONTHLY', 'STRIP')
        GROUP BY zone, auction_type
        ORDER BY zone, auction_type
    """,
    
    # Energy queries
    "All energy data": """
        SELECT * FROM market_prices 
        WHERE market_type = 'ENERGY'
        ORDER BY start_time DESC
    """,
    "Energy: NYC Day-Ahead prices": """
        SELECT start_time, price, zone 
        FROM market_prices 
        WHERE market_type = 'ENERGY' 
          AND zone = 'NYC' 
          AND product = 'ENERGY_DA'
        ORDER BY start_time DESC
    """,
    "Energy: Average price by zone": """
        SELECT zone, product, AVG(price) as avg_price 
        FROM market_prices 
        WHERE market_type = 'ENERGY'
        GROUP BY zone, product
        ORDER BY zone, product
    """,
    "Energy: Daily averages": """
        SELECT DATE(start_time) as date, AVG(price) as avg_price
        FROM market_prices 
        WHERE market_type = 'ENERGY' AND zone = 'NYC'
        GROUP BY DATE(start_time)
        ORDER BY date DESC
    """,
    
    # Combined queries
    "Data inventory": """
        SELECT market_type, COUNT(*) as records, COUNT(DISTINCT zone) as zones
        FROM market_prices
        WHERE iso_code = 'NYISO'
        GROUP BY market_type
    """,
    "Count all records": """
        SELECT COUNT(*) as total_records 
        FROM market_prices 
        WHERE iso_code = 'NYISO'
    """
}

print("\nCopy-paste these into DuckDB:")
for name, query in queries.items():
    print(f"\n-- {name}")
    print(query.strip())

print("\n" + "=" * 80)
print("RECOMMENDATION: Use DuckDB for queries (easier, SQL-based)")
print("=" * 80)
