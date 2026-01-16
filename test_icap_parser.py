"""
Test the ICAP HTML parser with the saved HTML file.
This verifies the parser logic works before testing live scraping.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from adapters.nyiso_capacity import NYISOCapacityAdapter

print("=" * 60)
print("Testing ICAP HTML Parser with Saved HTML File")
print("=" * 60)

# Path to the saved HTML file
html_file = Path(r"C:\Users\rallen\Documents\winter2324.html")

if not html_file.exists():
    print(f"\n[ERROR] HTML file not found: {html_file}")
    print("Please provide the path to the saved HTML file")
    sys.exit(1)

print(f"\nReading HTML from: {html_file}")
html_content = html_file.read_text(encoding='utf-8')
print(f"HTML length: {len(html_content)} characters")

adapter = NYISOCapacityAdapter()
auction_month = "202311"

print(f"\nParsing HTML for auction month: {auction_month}")
parsed_data = adapter._parse_monthly_auction_html(html_content, auction_month)

if parsed_data:
    print("\n[OK] Successfully parsed HTML!")
    print("\n" + "=" * 60)
    print("Parsed Data Summary:")
    print("=" * 60)
    print(f"Auction Month: {parsed_data['auction_month']}")
    print(f"Capability Period: {parsed_data['capability_period']}")
    print(f"Season ID: {parsed_data['season_id']}")
    print(f"Posted At: {parsed_data['posted_at']}")
    print(f"\nZones found: {len(parsed_data['zones'])}")
    
    for zone_name, delivery_data in sorted(parsed_data['zones'].items()):
        delivery_months = sorted(delivery_data.keys())
        print(f"\n{zone_name}:")
        print(f"  Delivery Months: {', '.join(delivery_months)}")
        for dm in delivery_months:
            price = delivery_data[dm].get('price', 0)
            awarded = delivery_data[dm].get('awarded_mw', 0)
            print(f"    {dm}: Price=${price:.2f}, Awarded={awarded:.1f} MW")
    
    # Count total records that would be created
    total_records = sum(len(delivery_data) for delivery_data in parsed_data['zones'].values())
    print(f"\n[OK] Would create {total_records} MarketPriceFact records")
else:
    print("\n[ERROR] Failed to parse HTML")
    print("Check the parser logic")
