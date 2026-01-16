"""
Query ICAP CAPACITY Winter 2023-2024 data.

Demonstrates both DuckDB (recommended) and Parquet (direct) approaches.
"""

import duckdb
import pandas as pd
from pathlib import Path

# Paths
DUCKDB_PATH = Path("analytics_db/analytics.duckdb")
PARQUET_BASE = Path("data/parquet")

print("=" * 80)
print("ICAP CAPACITY Winter 2023-2024 Data Query")
print("=" * 80)

# ============================================================================
# Option 1: DuckDB (RECOMMENDED - Easier, SQL-based)
# ============================================================================

print("\n" + "=" * 80)
print("OPTION 1: DuckDB (Recommended)")
print("=" * 80)

con = duckdb.connect(str(DUCKDB_PATH))

# Query 1: All Winter 2023-2024 capacity data
print("\n1. All Winter 2023-2024 Capacity Data:")
print("-" * 80)
query1 = """
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
df1 = con.execute(query1).df()
print(df1.to_string(index=False))
print(f"\nTotal records: {len(df1)}")

# Query 2: Summary by zone
print("\n\n2. Summary by Zone:")
print("-" * 80)
query2 = """
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
df2 = con.execute(query2).df()
print(df2.to_string(index=False))

# Query 3: Price trends by delivery month
print("\n\n3. Price Trends by Delivery Month (NYC):")
print("-" * 80)
query3 = """
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
df3 = con.execute(query3).df()
print(df3.to_string(index=False))

# Query 4: All zones, all delivery months (pivot view)
print("\n\n4. Price Matrix: Zones × Delivery Months:")
print("-" * 80)
query4 = """
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
df4 = con.execute(query4).df()
print(df4.to_string(index=False))

# Query 5: Detailed view with all metadata
print("\n\n5. Detailed View (All Fields):")
print("-" * 80)
query5 = """
SELECT 
    delivery_month,
    zone,
    price as "Price ($/kW-month)",
    awarded_mw as "Awarded (MW)",
    auction_month,
    capability_period,
    auction_type,
    posted_at,
    season_id
FROM market_prices
WHERE market_type = 'CAPACITY'
  AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
ORDER BY delivery_month, zone
LIMIT 20
"""
df5 = con.execute(query5).df()
print(df5.to_string(index=False))

con.close()

# ============================================================================
# Option 2: Direct Parquet (Alternative - More Control)
# ============================================================================

print("\n\n" + "=" * 80)
print("OPTION 2: Direct Parquet (Alternative)")
print("=" * 80)

print("\n6. Loading from Parquet files directly:")
print("-" * 80)

# Find all capacity parquet files for Winter 2023-2024
parquet_files = []
for month in ['11', '12']:  # 2023
    file_path = PARQUET_BASE / "NYISO" / "CAPACITY" / "2023" / month / "data_2023_*.parquet"
    parquet_files.extend(list(PARQUET_BASE.glob(f"NYISO/CAPACITY/2023/{month}/*.parquet")))
for month in ['01', '02', '03', '04']:  # 2024
    parquet_files.extend(list(PARQUET_BASE.glob(f"NYISO/CAPACITY/2024/{month}/*.parquet")))

if parquet_files:
    print(f"Found {len(parquet_files)} Parquet files:")
    for f in parquet_files:
        print(f"  - {f}")
    
    # Load and concatenate
    dfs = []
    for file in parquet_files:
        df = pd.read_parquet(file)
        # Filter for Winter 2023-2024 delivery months
        df = df[df['delivery_month'].isin(['202311', '202312', '202401', '202402', '202403', '202404'])]
        dfs.append(df)
    
    if dfs:
        df_parquet = pd.concat(dfs, ignore_index=True)
        print(f"\nLoaded {len(df_parquet)} records from Parquet")
        print("\nSample data:")
        print(df_parquet[['delivery_month', 'zone', 'price', 'awarded_mw', 'auction_month']].head(10).to_string(index=False))
else:
    print("No Parquet files found")

# ============================================================================
# Quick Reference Queries
# ============================================================================

print("\n\n" + "=" * 80)
print("QUICK REFERENCE: Common Queries")
print("=" * 80)

queries = {
    "All capacity data": """
        SELECT * FROM market_prices 
        WHERE market_type = 'CAPACITY'
        ORDER BY delivery_month, zone
    """,
    "NYC prices only": """
        SELECT delivery_month, price, awarded_mw 
        FROM market_prices 
        WHERE market_type = 'CAPACITY' AND zone = 'NYC'
        ORDER BY delivery_month
    """,
    "Average price by zone": """
        SELECT zone, AVG(price) as avg_price 
        FROM market_prices 
        WHERE market_type = 'CAPACITY'
        GROUP BY zone
        ORDER BY avg_price DESC
    """,
    "Count records": """
        SELECT COUNT(*) as total_records 
        FROM market_prices 
        WHERE market_type = 'CAPACITY'
    """
}

print("\nCopy-paste these into DuckDB:")
for name, query in queries.items():
    print(f"\n-- {name}")
    print(query.strip())

print("\n" + "=" * 80)
print("RECOMMENDATION: Use DuckDB for queries (easier, SQL-based)")
print("=" * 80)
