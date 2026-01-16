"""
Test the improved fetch_capacity_prices logic.
"""

import sys
from pathlib import Path
from datetime import datetime
import pytz

sys.path.insert(0, str(Path(__file__).parent))

from adapters.nyiso_capacity import NYISOCapacityAdapter

print("=" * 60)
print("Testing Improved fetch_capacity_prices() Logic")
print("=" * 60)

adapter = NYISOCapacityAdapter()

# Test with date range that includes Winter 2023-2024
# This should only fetch ONE auction (202311) that covers all delivery months
start_date = datetime(2023, 11, 1, tzinfo=pytz.UTC)
end_date = datetime(2024, 4, 30, tzinfo=pytz.UTC)

print(f"\nFetching capacity prices from {start_date.date()} to {end_date.date()}")
print("Expected: Should fetch ONE auction (202311) that covers all 6 delivery months\n")

facts = adapter.fetch_capacity_prices(
    start_date=start_date,
    end_date=end_date,
    nodes=None,
    auction_type="MONTHLY",
)

print(f"\n[OK] Fetched {len(facts)} total records")

# Group by auction_month to see how many auctions were fetched
auctions = {}
for fact in facts:
    if fact.auction_month not in auctions:
        auctions[fact.auction_month] = []
    auctions[fact.auction_month].append(fact)

print(f"\nAuctions fetched: {len(auctions)}")
for auction_month in sorted(auctions.keys()):
    auction_facts = auctions[auction_month]
    zones = sorted(set(f.zone for f in auction_facts))
    delivery_months = sorted(set(f.delivery_month for f in auction_facts))
    print(f"\n  Auction {auction_month}:")
    print(f"    Records: {len(auction_facts)}")
    print(f"    Zones: {', '.join(zones)}")
    print(f"    Delivery Months: {', '.join(delivery_months)}")

print("\n" + "=" * 60)
if len(auctions) == 1:
    print("[OK] Correctly fetched only ONE auction for the capability period!")
else:
    print(f"[WARNING] Fetched {len(auctions)} auctions - expected 1")
