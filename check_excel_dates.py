import openpyxl
import pandas as pd

file_path = r'C:\Users\rallen\isodata\data\excel\nyiso\ICAP Market Report - December 2023.xlsx'

# Check with openpyxl (raw values)
print("=" * 80)
print("Checking with openpyxl (raw Excel values):")
print("=" * 80)
wb = openpyxl.load_workbook(file_path)
ws = wb['MCP Table']

print("\nFirst column raw values (first 25 rows):")
for i, row in enumerate(ws.iter_rows(min_row=1, max_row=26, min_col=1, max_col=1, values_only=True), 1):
    cell_value = row[0]
    cell = ws.cell(row=i, column=1)
    print(f"Row {i}: Value={cell_value}, Type={type(cell_value).__name__}, Number Format={cell.number_format if hasattr(cell, 'number_format') else 'N/A'}")

# Check with pandas (how it interprets)
print("\n" + "=" * 80)
print("Checking with pandas (interpreted values):")
print("=" * 80)
df = pd.read_excel(file_path, sheet_name='MCP Table', nrows=25)
print(f"\nFirst column as pandas sees it:")
print(df.iloc[:25, 0])
