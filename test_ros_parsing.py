"""Test ROS parsing from HTML."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

from adapters.nyiso_capacity import NYISOCapacityAdapter

adapter = NYISOCapacityAdapter()
html_file = Path(r"C:\Users\rallen\Documents\winter2324.html")

if not html_file.exists():
    print(f"HTML file not found: {html_file}")
    sys.exit(1)

html = html_file.read_text(encoding='utf-8')
result = adapter._parse_monthly_auction_html(html, '202311')

print("=" * 60)
print("ROS Parsing Test")
print("=" * 60)

print(f"\nZones found: {sorted(result['zones'].keys())}")

if 'ROS' in result['zones']:
    print("\n[OK] ROS zone found!")
    print("\nROS data by delivery month:")
    for delivery_month in sorted(result['zones']['ROS'].keys()):
        data = result['zones']['ROS'][delivery_month]
        print(f"  {delivery_month}:")
        print(f"    Price: ${data.get('price', 'N/A')}")
        print(f"    Awarded MW: {data.get('awarded_mw', 'N/A')}")
else:
    print("\n[ERROR] ROS zone NOT found!")

print("\n" + "=" * 60)
print("Sample of other zones (for comparison):")
print("=" * 60)
for zone in ['NYC', 'G-J']:
    if zone in result['zones']:
        print(f"\n{zone}:")
        for delivery_month in sorted(list(result['zones'][zone].keys())[:2]):  # Show first 2
            data = result['zones'][zone][delivery_month]
            print(f"  {delivery_month}: Price=${data.get('price', 'N/A')}, Awarded={data.get('awarded_mw', 'N/A')} MW")
