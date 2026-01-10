# Beginner's Guide: What We're Building & How to Verify It Works

## 🎯 The Big Picture

We're building a **power market data pipeline** that:
1. **Downloads** electricity price data from NYISO (New York's power grid)
2. **Stores** it in an organized way (Parquet files)
3. **Lets you analyze** it with SQL queries (DuckDB)
4. **Creates charts** and visualizations (Jupyter notebooks)

Think of it like a data collection and analysis system for electricity prices.

---

## 📁 Where Things Are Stored

After running the pipeline, here's where to find your data:

### 1. **Raw Data Files** (Parquet format)
```
data/parquet/
  └── NYISO/
      └── ENERGY/
          └── 2024/
              └── 01/
                  └── data_2024_01.parquet  ← Your actual data is here!
```

### 2. **Database Files**
```
duckdb/
  └── analytics.duckdb  ← SQL database for querying

metadata/
  └── metadata.db  ← Logs of what was downloaded
```

### 3. **Charts/Visualizations**
```
visualizations/
  └── test_price_pdf.png  ← Charts you generate
  └── test_timeseries.png
```

---

## ✅ Step-by-Step: How to Verify Everything Works

### Step 1: Load Some Data

Run this command to download 1 week of NYISO data:

```bash
python run_pipeline.py --energy --iso NYISO --start-date 2024-01-01 --end-date 2024-01-07 --product DA
```

**What to look for:**
- ✅ You should see: "Fetched X price records"
- ✅ You should see: "Wrote X Parquet files"
- ✅ You should see: "Refreshed DuckDB views"
- ✅ You should see: "Pipeline completed: Status: success"

**If it fails:** Check the error message and let me know!

---

### Step 2: Check That Data Files Were Created

```bash
# Windows PowerShell
dir data\parquet\NYISO\ENERGY\2024\01

# Or check if files exist
python -c "from pathlib import Path; files = list(Path('data/parquet/NYISO/ENERGY/2024/01').glob('*.parquet')); print(f'Found {len(files)} data files'); [print(f'  - {f.name}') for f in files[:5]]"
```

**What to look for:**
- ✅ You should see at least one `.parquet` file
- ✅ File should have a name like `data_2024_01.parquet`

---

### Step 3: Check the Database

```bash
python -c "import duckdb; con = duckdb.connect('duckdb/analytics.duckdb'); result = con.execute('SELECT COUNT(*) as total FROM market_prices WHERE iso_code = \\'NYISO\\'').fetchone(); print(f'NYISO records in database: {result[0]}'); con.close()"
```

**What to look for:**
- ✅ You should see a number > 0 (like "NYISO records in database: 168")
- This means data is in the database and ready to query

---

### Step 4: Test a Simple Query

```bash
python -c "import duckdb; con = duckdb.connect('duckdb/analytics.duckdb'); df = con.execute('SELECT zone, AVG(price) as avg_price FROM market_prices WHERE iso_code = \\'NYISO\\' GROUP BY zone LIMIT 5').df(); print(df); con.close()"
```

**What to look for:**
- ✅ You should see a table with zone names and average prices
- ✅ Example output:
```
    zone  avg_price
0    NYC      45.23
1     LI      44.87
2   WEST      42.15
```

---

### Step 5: Test the Compatibility Layer (NYISOToolkit Integration)

```bash
python test_refresh_views.py
```

**What to look for:**
- ✅ You should see: "✓ Views refreshed"
- ✅ No error messages

Then test the adapter:

```bash
python -c "from adapters.nyiso_compat import ISODataAdapter; from pathlib import Path; adapter = ISODataAdapter('NYISO', 'lbmp_dam_h', 2024, parquet_base=Path('data/parquet'), duckdb_path=Path('duckdb/analytics.duckdb')); df = adapter.df; print(f'✓ Data loaded: {df.shape[0]} rows, {df.shape[1]} zones'); print(f'✓ Date range: {df.index.min()} to {df.index.max()}')"
```

**What to look for:**
- ✅ You should see: "✓ Data loaded: X rows, Y zones"
- ✅ You should see a date range showing 2024 dates

---

### Step 6: Generate a Chart (Visual Proof!)

```bash
python -c "from visualization.iso_vis import ISOVis; from pathlib import Path; vis = ISOVis('NYISO', 2024, out_dir=Path('visualizations'), parquet_base=Path('data/parquet'), duckdb_path=Path('duckdb/analytics.duckdb')); fig = vis.fig_price_pdf('lbmp_dam_h', zones=['NYC', 'LI', 'WEST']); vis.save_figure(fig, 'my_first_chart', 'png'); print('✓ Chart saved to visualizations/my_first_chart.png')"
```

**What to look for:**
- ✅ You should see: "✓ Chart saved to visualizations/my_first_chart.png"
- ✅ Go to the `visualizations/` folder and open `my_first_chart.png`
- ✅ You should see a chart showing price distributions!

---

## 🎓 Understanding Jupyter

**Jupyter Notebooks** are like interactive documents where you can:
- Write code
- See results immediately
- Create charts
- Add explanations

Think of them as a combination of:
- A Word document (for writing)
- A calculator (for calculations)
- A graphing tool (for charts)

### How to Use Jupyter

1. **Start Jupyter:**
   ```bash
   jupyter notebook
   ```
   This opens a web browser with a file browser.

2. **Open a notebook:**
   - Click on `notebooks/phase2_demo.ipynb`
   - Or `notebooks/nyiso_compat_demo.ipynb`

3. **Run cells:**
   - Click on a cell (gray box with code)
   - Press `Shift + Enter` to run it
   - See results below the cell

4. **What you'll see:**
   - Code cells (gray boxes)
   - Output cells (results appear here)
   - Markdown cells (explanations in plain text)

---

## 🧪 Quick Verification Checklist

Run these in order and check off as you go:

- [ ] **Data loaded:** `python run_pipeline.py --energy --iso NYISO --start-date 2024-01-01 --end-date 2024-01-07 --product DA` succeeds
- [ ] **Files created:** Check `data/parquet/NYISO/ENERGY/2024/01/` has `.parquet` files
- [ ] **Database works:** Query returns record count > 0
- [ ] **Simple query works:** Can see zone names and prices
- [ ] **Views refreshed:** `python test_refresh_views.py` succeeds
- [ ] **Adapter works:** Can load data through compatibility layer
- [ ] **Chart created:** `visualizations/` folder has a PNG file you can open

---

## 🎯 What Success Looks Like

When everything is working, you should be able to:

1. ✅ Download NYISO data with one command
2. ✅ See data files in `data/parquet/`
3. ✅ Query data with SQL
4. ✅ Generate charts automatically
5. ✅ Use the same tools for other ISOs (PJM, ISO-NE, etc.) once we add them

---

## 🆘 Common Issues & Solutions

### "No data found" or "0 records"
- **Problem:** Data wasn't downloaded yet
- **Solution:** Run Step 1 (load data) first

### "File not found" errors
- **Problem:** Wrong path or files don't exist
- **Solution:** Check that `data/parquet/NYISO/ENERGY/2024/01/` exists

### "Import errors"
- **Problem:** Missing Python packages
- **Solution:** Run `pip install -r requirements.txt`

### Charts don't appear
- **Problem:** Matplotlib backend issue
- **Solution:** Check `visualizations/` folder for saved PNG files

---

## 📚 Next Steps

Once you've verified everything works:

1. **Try Jupyter:** Open `notebooks/phase2_demo.ipynb` and run the cells
2. **Explore data:** Try different date ranges and zones
3. **Generate more charts:** Experiment with different visualizations
4. **Load more data:** Try backfilling a full year

---

## 💡 Remember

- **Data files** = Your downloaded electricity prices (Parquet format)
- **Database** = Fast way to query the data (DuckDB)
- **Charts** = Visual representation of the data (PNG files)
- **Jupyter** = Interactive way to explore and analyze

You're building a complete data analysis system! 🎉

