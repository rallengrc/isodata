"""Detailed test of ROS parsing."""
import sys
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))

from adapters.nyiso_capacity import NYISOCapacityAdapter

adapter = NYISOCapacityAdapter()
html_file = Path(r"C:\Users\rallen\Documents\winter2324.html")
html = html_file.read_text(encoding='utf-8')

# Parse
result = adapter._parse_monthly_auction_html(html, '202311')

print("=" * 60)
print("ROS Parsing Detailed Test")
print("=" * 60)

if 'ROS' in result['zones']:
    print("\nROS zone data:")
    for delivery_month in sorted(result['zones']['ROS'].keys()):
        data = result['zones']['ROS'][delivery_month]
        print(f"\n  {delivery_month}:")
        print(f"    Price: {data.get('price', 'MISSING')}")
        print(f"    Awarded MW: {data.get('awarded_mw', 'MISSING')}")
        
        # Check what keys are actually present
        print(f"    Keys present: {list(data.keys())}")
else:
    print("\nROS zone NOT found!")

# Also check the raw HTML to see the exact text
soup = BeautifulSoup(html, 'html.parser')
rows = soup.find_all('tr')
for i, row in enumerate(rows):
    cells = row.find_all(['td', 'th'])
    if cells:
        first_cell = cells[0].get_text(strip=True) if cells else ""
        if 'Total ROS Awarded' in first_cell:
            print(f"\nFound 'Total ROS Awarded' row at index {i}:")
            print(f"  First cell text: '{first_cell}'")
            print(f"  Number of cells: {len(cells)}")
            for idx in range(min(4, len(cells))):  # Show first 4 cells
                print(f"    Cell {idx}: '{cells[idx].get_text(strip=True)}'")
