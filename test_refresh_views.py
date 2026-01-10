#!/usr/bin/env python3
"""Quick script to refresh DuckDB views."""

from storage.duckdb_views import DuckDBViews
from pathlib import Path

views = DuckDBViews(Path('analytics_db/analytics.duckdb'), Path('data/parquet'))
views.refresh_views()
views.close()
print('✓ Views refreshed')

