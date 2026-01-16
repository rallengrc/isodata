"""Debug ROS parsing to see what's happening."""
import sys
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))

html_file = Path(r"C:\Users\rallen\Documents\winter2324.html")
html = html_file.read_text(encoding='utf-8')
soup = BeautifulSoup(html, 'html.parser')

# Find the data table
tables = soup.find_all('table')
data_table = None
month_abbrevs = ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct']

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

print("Header row cells:")
header_cells = header_row.find_all('th')
for idx, cell in enumerate(header_cells):
    print(f"  Index {idx}: '{cell.get_text(strip=True)}'")

# Find ROS rows
print("\nROS rows:")
rows = data_table.find_all('tr')
for i, row in enumerate(rows):
    cells = row.find_all(['td', 'th'])
    if cells:
        first_cell = cells[0].get_text(strip=True) if cells else ""
        if 'ROS' in first_cell:
            print(f"\nRow {i}: '{first_cell}'")
            print(f"  Number of cells: {len(cells)}")
            for idx, cell in enumerate(cells):
                print(f"    Cell {idx}: '{cell.get_text(strip=True)}'")
