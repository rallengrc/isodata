"""Test column mapping for ROS rows."""
import sys
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))

html_file = Path(r"C:\Users\rallen\Documents\winter2324.html")
html = html_file.read_text(encoding='utf-8')
soup = BeautifulSoup(html, 'html.parser')

# Find header row
tables = soup.find_all('table')
data_table = None
month_abbrevs = ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr']

for table in tables:
    headers = table.find_all('th')
    month_headers = [h.get_text(strip=True) for h in headers]
    if any(month in ' '.join(month_headers) for month in month_abbrevs):
        data_table = table
        break

# Find header row
header_row = None
for row in data_table.find_all('tr'):
    cells = row.find_all('th')
    if cells:
        cell_texts = [c.get_text(strip=True) for c in cells]
        if any(month in ' '.join(cell_texts) for month in month_abbrevs):
            header_row = row
            break

# Build delivery_month_cols
month_map = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,
    'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8,
    'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
}

auction_year = 2023
delivery_month_cols = {}

header_cells = header_row.find_all('th')
for idx, cell in enumerate(header_cells):
    text = cell.get_text(strip=True)
    for abbrev, month_num in month_map.items():
        if abbrev in text:
            if month_num >= 11:
                year = auction_year
            else:
                year = auction_year + 1
            delivery_month_cols[idx] = f"{year}{month_num:02d}"
            break

print("delivery_month_cols mapping:")
for idx, month in sorted(delivery_month_cols.items()):
    print(f"  Header index {idx} -> {month}")

# Find ROS row
rows = data_table.find_all('tr')
for i, row in enumerate(rows):
    cells = row.find_all(['td', 'th'])
    if cells:
        first_cell = cells[0].get_text(strip=True) if cells else ""
        if 'Total ROS Awarded (MW)' in first_cell:
            print(f"\nFound ROS row at index {i}:")
            print(f"  Number of cells: {len(cells)}")
            print(f"  Cell values:")
            for idx in range(len(cells)):
                print(f"    cells[{idx}] = '{cells[idx].get_text(strip=True)}'")
            
            print(f"\n  Mapping cells to delivery months:")
            for col_idx, delivery_month in sorted(delivery_month_cols.items()):
                if col_idx < len(cells):
                    cell_value = cells[col_idx].get_text(strip=True)
                    print(f"    cells[{col_idx}] = '{cell_value}' -> {delivery_month}")
            break
