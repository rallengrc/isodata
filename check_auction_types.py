"""Quick script to check what auction types are in the database."""
import duckdb
from pathlib import Path

con = duckdb.connect(str(Path("analytics_db/analytics.duckdb")))

# Check capacity data by auction type
print("=" * 80)
print("Capacity Data by Auction Type (Winter 2023-2024)")
print("=" * 80)

df = con.execute("""
    SELECT 
        auction_type,
        COUNT(*) as record_count,
        COUNT(DISTINCT zone) as zone_count,
        MIN(price) as min_price,
        MAX(price) as max_price,
        AVG(price) as avg_price
    FROM market_prices
    WHERE market_type = 'CAPACITY'
      AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
    GROUP BY auction_type
    ORDER BY auction_type
""").df()

print(df.to_string(index=False))

# Check if we have both MONTHLY and STRIP
print("\n" + "=" * 80)
print("Summary")
print("=" * 80)
monthly_count = con.execute("""
    SELECT COUNT(*) 
    FROM market_prices
    WHERE market_type = 'CAPACITY'
      AND auction_type = 'MONTHLY'
      AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
""").fetchone()[0]

strip_count = con.execute("""
    SELECT COUNT(*) 
    FROM market_prices
    WHERE market_type = 'CAPACITY'
      AND auction_type = 'STRIP'
      AND delivery_month IN ('202311', '202312', '202401', '202402', '202403', '202404')
""").fetchone()[0]

print(f"MONTHLY records: {monthly_count}")
print(f"STRIP records: {strip_count}")

if monthly_count == 0:
    print("\n⚠ WARNING: No MONTHLY data found - it may have been overwritten!")
if strip_count == 0:
    print("\n⚠ WARNING: No STRIP data found!")

con.close()
