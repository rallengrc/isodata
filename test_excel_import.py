"""
Test script for Excel import functionality.

Usage:
    python test_excel_import.py path/to/excel/file.xlsx
"""

import sys
from pathlib import Path
from adapters.nyiso_capacity import NYISOCapacityAdapter

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_excel_import.py <excel_file_path> [auction_types...]")
        print("Example: python test_excel_import.py ICAP-Market-Report-2024.xlsx MONTHLY STRIP")
        return
    
    excel_path = Path(sys.argv[1])
    
    if not excel_path.exists():
        print(f"Error: Excel file not found: {excel_path}")
        return
    
    # Optional: filter by auction types
    auction_types = None
    if len(sys.argv) > 2:
        auction_types = [a.upper() for a in sys.argv[2:]]
        print(f"Filtering by auction types: {auction_types}")
    
    # Create adapter
    adapter = NYISOCapacityAdapter()
    
    # Import from Excel
    print(f"\nImporting from Excel file: {excel_path}")
    print("=" * 80)
    
    try:
        facts = adapter.fetch_capacity_prices_from_excel(
            excel_file_path=excel_path,
            auction_types=auction_types,
        )
        
        print(f"\n✓ Successfully parsed {len(facts)} records")
        
        if facts:
            print("\nSample records:")
            for i, fact in enumerate(facts[:5]):
                print(f"\n  Record {i+1}:")
                print(f"    Zone: {fact.zone}")
                print(f"    Auction Type: {fact.auction_type}")
                print(f"    Auction Month: {fact.auction_month}")
                print(f"    Delivery Month: {fact.delivery_month}")
                print(f"    Price: ${fact.price:.2f} /kW-month")
                if fact.awarded_mw:
                    print(f"    Awarded MW: {fact.awarded_mw:.2f}")
                print(f"    Capability Period: {fact.capability_period}")
            
            if len(facts) > 5:
                print(f"\n  ... and {len(facts) - 5} more records")
            
            # Summary by auction type
            print("\nSummary by auction type:")
            from collections import Counter
            auction_type_counts = Counter(f.auction_type for f in facts if f.auction_type)
            for auction_type, count in auction_type_counts.items():
                print(f"  {auction_type}: {count} records")
            
            # Summary by zone
            print("\nSummary by zone:")
            zone_counts = Counter(f.zone for f in facts if f.zone)
            for zone, count in sorted(zone_counts.items()):
                print(f"  {zone}: {count} records")
        
    except Exception as e:
        print(f"\n✗ Error importing from Excel: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
