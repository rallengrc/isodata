"""
Test script for NYISO ICAP screen scraping.

This script tests the ICAP adapter by fetching data directly from the NYISO portal.
"""

import sys
from pathlib import Path
from datetime import datetime
import pytz

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from adapters.nyiso_capacity import NYISOCapacityAdapter
from canonical.schemas import MarketPriceFact


def test_fetch_monthly_auction():
    """Test fetching a specific monthly auction."""
    print("=" * 60)
    print("Testing NYISO ICAP Monthly Auction Scraping")
    print("=" * 60)
    
    adapter = NYISOCapacityAdapter()
    
    # Test with Winter 2023-2024 auction (November 2023)
    # This is the auction_month from your example
    auction_month = "202311"
    
    print(f"\nFetching auction month: {auction_month}")
    print(f"URL: {adapter.BASE_URL}/auc_view_monthly_detail.do")
    print("\nThis will fetch the Winter 2023-2024 monthly auction...")
    print("(One auction can produce multiple records - one per delivery month)\n")
    
    try:
        facts = adapter._fetch_monthly_auction(
            auction_month=auction_month,
            season_id=None,  # Will be extracted from HTML
            nodes=None,  # Fetch all zones
        )
        
        print(f"\n✓ Successfully fetched {len(facts)} records")
        
        if facts:
            print("\n" + "=" * 60)
            print("Sample Records:")
            print("=" * 60)
            
            # Show first few records
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
            
            # Summary by zone
            print("\n" + "=" * 60)
            print("Summary by Zone:")
            print("=" * 60)
            zones = {}
            for fact in facts:
                if fact.zone not in zones:
                    zones[fact.zone] = []
                zones[fact.zone].append(fact)
            
            for zone, zone_facts in sorted(zones.items()):
                delivery_months = sorted(set(f.delivery_month for f in zone_facts))
                print(f"\n{zone}:")
                print(f"  Records: {len(zone_facts)}")
                print(f"  Delivery Months: {', '.join(delivery_months)}")
                avg_price = sum(f.price for f in zone_facts) / len(zone_facts)
                print(f"  Avg Price: ${avg_price:.2f} {zone_facts[0].unit}")
        else:
            print("\n[WARNING] No records returned. Check:")
            print("  - Is the auction month valid?")
            print("  - Is the NYISO portal accessible?")
            print("  - Check the HTML parsing logic")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_fetch_capacity_prices():
    """Test fetching capacity prices using the main method."""
    print("\n" + "=" * 60)
    print("Testing fetch_capacity_prices() method")
    print("=" * 60)
    
    adapter = NYISOCapacityAdapter()
    
    # Test with date range that includes Winter 2023-2024
    # November 2023 to April 2024
    start_date = datetime(2023, 11, 1, tzinfo=pytz.UTC)
    end_date = datetime(2024, 4, 30, tzinfo=pytz.UTC)
    
    print(f"\nFetching capacity prices from {start_date.date()} to {end_date.date()}")
    print("This will fetch monthly auctions for the delivery period...\n")
    
    try:
        facts = adapter.fetch_capacity_prices(
            start_date=start_date,
            end_date=end_date,
            nodes=None,  # All zones
            auction_type="MONTHLY",  # Only monthly auctions
        )
        
        print(f"\n✓ Successfully fetched {len(facts)} records")
        
        if facts:
            # Group by auction_month
            auctions = {}
            for fact in facts:
                if fact.auction_month not in auctions:
                    auctions[fact.auction_month] = []
                auctions[fact.auction_month].append(fact)
            
            print("\n" + "=" * 60)
            print("Summary by Auction Month:")
            print("=" * 60)
            for auction_month in sorted(auctions.keys()):
                auction_facts = auctions[auction_month]
                zones = sorted(set(f.zone for f in auction_facts))
                delivery_months = sorted(set(f.delivery_month for f in auction_facts))
                print(f"\nAuction Month: {auction_month}")
                print(f"  Records: {len(auction_facts)}")
                print(f"  Zones: {', '.join(zones)}")
                print(f"  Delivery Months: {', '.join(delivery_months)}")
        else:
            print("\n[WARNING] No records returned")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test NYISO ICAP screen scraping")
    parser.add_argument(
        "--method",
        choices=["auction", "prices", "both"],
        default="auction",
        help="Which method to test (default: auction)",
    )
    parser.add_argument(
        "--auction-month",
        type=str,
        default="202311",
        help="Auction month to test (YYYYMM format, default: 202311)",
    )
    
    args = parser.parse_args()
    
    if args.method in ["auction", "both"]:
        # Override auction_month if provided
        if args.auction_month != "202311":
            # Modify the function to use the provided auction_month
            adapter = NYISOCapacityAdapter()
            print(f"Testing with auction_month: {args.auction_month}")
            facts = adapter._fetch_monthly_auction(
                auction_month=args.auction_month,
                season_id=None,
                nodes=None,
            )
            print(f"\n[OK] Fetched {len(facts)} records")
            if facts:
                for i, fact in enumerate(facts[:3], 1):
                    print(f"\nRecord {i}: {fact.zone}, {fact.delivery_month}, ${fact.price:.2f}")
        else:
            test_fetch_monthly_auction()
    
    if args.method in ["prices", "both"]:
        test_fetch_capacity_prices()
