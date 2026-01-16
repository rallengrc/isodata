"""
Simple test script for NYISO ICAP screen scraping.
Tests fetching data from the NYISO portal.
"""

import sys
from pathlib import Path
from datetime import datetime
import pytz

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from adapters.nyiso_capacity import NYISOCapacityAdapter

print("=" * 60)
print("Testing NYISO ICAP Monthly Auction Scraping")
print("=" * 60)

adapter = NYISOCapacityAdapter()

# Test with Winter 2023-2024 auction (November 2023)
auction_month = "202311"

print(f"\nFetching auction month: {auction_month}")
print(f"URL: {adapter.BASE_URL}/auc_view_monthly_detail.do")
print("\nFetching from NYISO portal...\n")

try:
    facts = adapter._fetch_monthly_auction(
        auction_month=auction_month,
        season_id=None,
        nodes=None,
    )
    
    print(f"\n[OK] Successfully fetched {len(facts)} records")
    
    if facts:
        print("\n" + "=" * 60)
        print("Sample Records (first 5):")
        print("=" * 60)
        
        for i, fact in enumerate(facts[:5], 1):
            print(f"\nRecord {i}:")
            print(f"  Zone: {fact.zone}")
            print(f"  Auction Month: {fact.auction_month}")
            print(f"  Delivery Month: {fact.delivery_month}")
            print(f"  Capability Period: {fact.capability_period}")
            print(f"  Price: ${fact.price:.2f} {fact.unit}")
            if fact.awarded_mw:
                print(f"  Awarded MW: {fact.awarded_mw:.1f}")
            if fact.posted_at:
                print(f"  Posted At: {fact.posted_at}")
            if fact.season_id:
                print(f"  Season ID: {fact.season_id}")
        
        if len(facts) > 5:
            print(f"\n... and {len(facts) - 5} more records")
        
        # Summary
        print("\n" + "=" * 60)
        print("Summary:")
        print("=" * 60)
        zones = sorted(set(f.zone for f in facts))
        delivery_months = sorted(set(f.delivery_month for f in facts))
        print(f"Total records: {len(facts)}")
        print(f"Zones: {', '.join(zones)}")
        print(f"Delivery months: {', '.join(delivery_months)}")
    else:
        print("\n[WARNING] No records returned")
        print("\nPossible issues:")
        print("  1. The POST request parameters might be incorrect")
        print("  2. The HTML structure might have changed")
        print("  3. Check debug_icap_202311.html if it was created")
        
except Exception as e:
    print(f"\n[ERROR] Error: {e}")
    import traceback
    traceback.print_exc()
