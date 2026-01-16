"""Final test of ROS parsing with debug output."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from adapters.nyiso_capacity import NYISOCapacityAdapter

adapter = NYISOCapacityAdapter()
html_file = Path("debug_icap_202311.html")

if not html_file.exists():
    print(f"HTML file not found: {html_file}")
    sys.exit(1)

html = html_file.read_text(encoding='utf-8')
result = adapter._parse_monthly_auction_html(html, '202311')

print("=" * 60)
print("ROS Final Test")
print("=" * 60)

if 'ROS' in result['zones']:
    print("\nROS zone data:")
    for delivery_month in sorted(result['zones']['ROS'].keys()):
        data = result['zones']['ROS'][delivery_month]
        print(f"\n  {delivery_month}:")
        print(f"    Price: {data.get('price', 'MISSING')}")
        print(f"    Awarded MW: {data.get('awarded_mw', 'MISSING')}")
        print(f"    All keys: {list(data.keys())}")
        
        # Expected values from HTML
        expected = {
            '202311': {'price': 3.66, 'awarded_mw': 2650.3},
            '202312': {'price': 3.85, 'awarded_mw': 1207.2},
            '202401': {'price': 4.80, 'awarded_mw': 346.7},
            '202402': {'price': 4.80, 'awarded_mw': 341.7},
            '202403': {'price': 3.60, 'awarded_mw': 480.6},
            '202404': {'price': 3.28, 'awarded_mw': 391.8},
        }
        
        if delivery_month in expected:
            exp = expected[delivery_month]
            print(f"    Expected: Price={exp['price']}, Awarded={exp['awarded_mw']}")
            if data.get('price') == exp['price']:
                print(f"    [OK] Price matches")
            else:
                print(f"    [ERROR] Price mismatch: got {data.get('price')}, expected {exp['price']}")
            if data.get('awarded_mw') == exp['awarded_mw']:
                print(f"    [OK] Awarded MW matches")
            else:
                print(f"    [ERROR] Awarded MW mismatch: got {data.get('awarded_mw')}, expected {exp['awarded_mw']}")
else:
    print("\n[ERROR] ROS zone NOT found!")
