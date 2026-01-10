@echo off
REM Quick test script for Windows - Run all verification steps

echo ==========================================
echo Power Market Pipeline - Quick Test
echo ==========================================
echo.

echo Step 1: Loading test data...
python run_pipeline.py --energy --iso NYISO --start-date 2024-01-01 --end-date 2024-01-07 --product DA
echo.

echo Step 2: Checking data files...
python -c "from pathlib import Path; files = list(Path('data/parquet/NYISO/ENERGY/2024/01').glob('*.parquet')); print(f'Found {len(files)} data files'); [print(f'  - {f.name}') for f in files[:5]]"
echo.

echo Step 3: Checking database...
python -c "import duckdb; con = duckdb.connect('analytics_db/analytics.duckdb'); result = con.execute(\"SELECT COUNT(*) as total FROM market_prices WHERE iso_code = 'NYISO'\").fetchone(); print(f'NYISO records in database: {result[0]}'); con.close()"
echo.

echo Step 4: Testing query...
python -c "import duckdb; con = duckdb.connect('analytics_db/analytics.duckdb'); df = con.execute(\"SELECT zone, AVG(price) as avg_price FROM market_prices WHERE iso_code = 'NYISO' GROUP BY zone LIMIT 5\").df(); print(df); con.close()"
echo.

echo Step 5: Refreshing views...
python test_refresh_views.py
echo.

echo Step 6: Testing compatibility layer...
python -c "from adapters.nyiso_compat import ISODataAdapter; from pathlib import Path; adapter = ISODataAdapter('NYISO', 'lbmp_dam_h', 2024, parquet_base=Path('data/parquet'), duckdb_path=Path('analytics_db/analytics.duckdb')); df = adapter.df; print(f'✓ Data loaded: {df.shape[0]} rows, {df.shape[1]} zones'); print(f'✓ Date range: {df.index.min()} to {df.index.max()}')"
echo.

echo Step 7: Generating test chart...
python -c "from visualization.iso_vis import ISOVis; from pathlib import Path; vis = ISOVis('NYISO', 2024, out_dir=Path('visualizations'), parquet_base=Path('data/parquet'), duckdb_path=Path('analytics_db/analytics.duckdb')); fig = vis.fig_price_pdf('lbmp_dam_h', zones=['NYC', 'LI', 'WEST']); vis.save_figure(fig, 'test_chart', 'png'); print('✓ Chart saved to visualizations/test_chart.png')"
echo.

echo ==========================================
echo Test Complete!
echo ==========================================
echo Check the visualizations\ folder for your chart!
echo.
pause

