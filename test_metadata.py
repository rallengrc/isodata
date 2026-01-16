"""Quick test to verify SQLite metadata logging."""
import sqlite3

conn = sqlite3.connect('metadata/metadata.db')
cursor = conn.execute('''
    SELECT dataset_name, iso_code, status, row_count, start_time 
    FROM ingestion_log 
    ORDER BY start_time DESC 
    LIMIT 5
''')

print('Recent ingestion logs:')
for row in cursor:
    print(f'  {row[0]}: {row[1]} - {row[2]} - {row[3]} rows - {row[4]}')

conn.close()
