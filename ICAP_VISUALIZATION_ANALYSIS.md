# ICAP Data Visualization Analysis & Recommendations

## Executive Summary

**Goal**: Maximize ICAP data graphability using NYISOToolkit (designed for energy data) while maintaining data integrity and proper metadata tracking.

**Key Challenge**: ICAP has **monthly/seasonal granularity** and **one-to-many auction→delivery relationship**, while NYISOToolkit expects **hourly time series**.

**Recommendation**: Use **delivery_month as time index** (first day of month) to create monthly time series compatible with NYISOToolkit visualizations.

---

## 1. Data Structure Comparison

### Energy Market Data
- **Granularity**: Hourly (or 5-minute for RT)
- **Temporal Structure**: 
  - `auction_month` ≈ `delivery_month` (day-ahead auction happens day before)
  - Continuous time series: 8,760 hours/year
- **Time Index**: `start_time` (hourly timestamps)
- **Example**: 
  ```
  start_time: 2024-01-01 00:00:00 UTC → price: $50.25
  start_time: 2024-01-01 01:00:00 UTC → price: $48.30
  ```

### ICAP Capacity Data
- **Granularity**: Monthly/seasonal
- **Temporal Structure**:
  - `auction_month` ≠ `delivery_month` (one auction covers multiple delivery months)
  - Discrete monthly data: 12 months/year
  - **One auction → Multiple records** (one per delivery month)
- **Time Index**: `start_time` (first day of delivery month)
- **Example**:
  ```
  auction_month: 202311, delivery_month: 202311 → price: $13.04, awarded_mw: 656.9
  auction_month: 202311, delivery_month: 202312 → price: $13.04, awarded_mw: 545.0
  auction_month: 202311, delivery_month: 202401 → price: $13.06, awarded_mw: 505.5
  ```

---

## 2. NYISOToolkit Visualization Compatibility

### ✅ **Works Well with ICAP**

#### 1. **Price PDF (Distribution)**
- **Method**: `fig_price_pdf()`
- **Why it works**: Distribution doesn't care about time granularity
- **ICAP adaptation**: Shows distribution of capacity prices across zones/months
- **Example**: "What's the distribution of NYC capacity prices?"

#### 2. **Zone Comparison**
- **Method**: `fig_zone_comparison()`
- **Why it works**: Compares zones at same time points
- **ICAP adaptation**: Compare zones for same delivery month
- **Example**: "NYC vs LI capacity prices for January 2024"

#### 3. **Price Statistics**
- **Method**: `get_price_statistics()`
- **Why it works**: Statistical aggregations work on any time series
- **ICAP adaptation**: Mean, median, min, max of capacity prices

### ⚠️ **Needs Adaptation for ICAP**

#### 1. **Time Series Charts**
- **Method**: `fig_price_timeseries()`
- **Challenge**: Monthly granularity vs hourly
- **Solution**: Use `delivery_month` as time index (first day of month)
- **Example**: Monthly time series showing capacity price trends
- **Limitation**: Can't show intra-day patterns (not applicable to ICAP anyway)

#### 2. **Heatmaps**
- **Method**: (Not yet implemented, but common in NYISOToolkit)
- **Challenge**: Monthly data creates sparse heatmaps
- **Solution**: Use delivery_month for rows, zones for columns
- **Example**: Heatmap of capacity prices by zone and delivery month

### ❌ **Doesn't Apply to ICAP**

#### 1. **Hourly Patterns**
- **Method**: `table_average_day_dataset()` (average hourly patterns)
- **Why not**: ICAP is monthly, not hourly
- **Alternative**: Could create "average month" patterns (seasonal)

#### 2. **Real-time vs Day-ahead Comparisons**
- **Why not**: ICAP doesn't have RT/DA split
- **Alternative**: Compare auction types (MONTHLY vs STRIP)

---

## 3. Schema & Metadata Recommendations

### Current Schema Status
✅ **Already supports ICAP**:
- `auction_month` (YYYYMM)
- `delivery_month` (YYYYMM)
- `capability_period` (SUMMER/WINTER)
- `auction_type` (MONTHLY/STRIP/SPOT)
- `awarded_mw` (cleared quantity)
- `posted_at` (auction posting time)
- `season_id` (NYISO season ID)

### Metadata in SQLite
**Current**: `ingestion_log` table tracks:
- `dataset_name` (e.g., "energy_da_nyiso")
- `iso_code`
- `status` (SUCCESS/ERROR/NO_DATA)
- `row_count`
- `start_time`, `end_time`

**Recommendation**: 
- ✅ **No schema changes needed** - current structure works
- ✅ **Use dataset_name**: `"capacity_monthly_nyiso"` or `"capacity_strip_nyiso"`
- ✅ **Log both energy and capacity** using same `log_ingestion()` function

---

## 4. Data Transformation Strategy

### For NYISOToolkit Compatibility

#### Option 1: Delivery Month as Time Index (RECOMMENDED)
```python
# Transform ICAP data to NYISO format
# Use delivery_month as time index (first day of month)
df.index = pd.to_datetime(delivery_month, format='%Y%m')  # 202311 → 2023-11-01
df.index = df.index.tz_localize('US/Eastern')

# Columns: MultiIndex [('Capacity Price ($/kW-month)', 'NYC'), ...]
# Result: Monthly time series compatible with NYISOToolkit
```

**Pros**:
- ✅ Creates continuous monthly time series
- ✅ Compatible with NYISOToolkit time series methods
- ✅ Natural representation (delivery month is when capacity applies)
- ✅ Can show trends over time

**Cons**:
- ⚠️ One auction month appears multiple times (once per delivery month)
- ⚠️ Monthly granularity (not hourly)

#### Option 2: Auction Month as Time Index
```python
# Use auction_month as time index
df.index = pd.to_datetime(auction_month, format='%Y%m')
```

**Pros**:
- ✅ One timestamp per auction

**Cons**:
- ❌ Multiple delivery months per timestamp (can't pivot properly)
- ❌ Doesn't represent when capacity is delivered
- ❌ Breaks time series continuity

**Recommendation**: **Use Option 1** (delivery_month as time index)

---

## 5. Implementation Plan

### Phase 1: Capacity Pipeline Integration ✅ (Current)
- [x] Create `pipelines/capacity_pipeline.py`
- [x] Add `--capacity` flag to `run_pipeline.py`
- [x] Log to SQLite metadata
- [x] Write to Parquet
- [x] Refresh DuckDB views

### Phase 2: ICAP Visualization Adapter
- [ ] Extend `ISODataAdapter` to handle CAPACITY market type
- [ ] Transform ICAP data using delivery_month as time index
- [ ] Create dataset type: `"icap_monthly"` or `"capacity_monthly"`

### Phase 3: ICAP-Specific Visualizations
- [ ] `fig_capacity_timeseries()` - Monthly capacity price trends
- [ ] `fig_capacity_by_auction()` - Group by auction_month
- [ ] `fig_capacity_heatmap()` - Zone × Delivery Month heatmap
- [ ] `fig_awarded_mw_timeseries()` - Cleared quantity trends

### Phase 4: Hybrid Visualizations
- [ ] Energy + Capacity comparison charts
- [ ] Price correlation analysis
- [ ] Seasonal patterns (SUMMER vs WINTER)

---

## 6. Code Changes Required

### 6.1 Extend `ISODataAdapter` for CAPACITY
```python
# In adapters/nyiso_compat.py
def _transform_capacity_to_nyiso_format(self, df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform ICAP data to NYISO format.
    Uses delivery_month as time index (first day of month).
    """
    # Convert delivery_month (YYYYMM) to datetime
    df['delivery_datetime'] = pd.to_datetime(
        df['delivery_month'], 
        format='%Y%m'
    )
    
    # Pivot: delivery_datetime × zone → price
    pivot_df = df.pivot_table(
        index='delivery_datetime',
        columns='zone',
        values='price',
        aggfunc='mean'
    )
    
    # Set timezone
    pivot_df.index = pivot_df.index.tz_localize('US/Eastern')
    
    # Create MultiIndex columns
    multi_cols = pd.MultiIndex.from_tuples(
        [('Capacity Price ($/kW-month)', zone) for zone in pivot_df.columns],
        names=['Metric', 'Zone']
    )
    pivot_df.columns = multi_cols
    
    return pivot_df
```

### 6.2 Add Capacity Pipeline
```python
# In pipelines/capacity_pipeline.py
def run_capacity_pipeline(
    adapter: ISOAdapter,
    start_date: datetime,
    end_date: datetime,
    auction_type: Optional[str] = None,
) -> dict:
    """Run capacity price pipeline."""
    iso_code = adapter.get_iso_code()
    dataset_name = f"capacity_{auction_type.lower() if auction_type else 'all'}_{iso_code.lower()}"
    
    # Fetch data
    facts = adapter.fetch_capacity_prices(
        start_date=start_date,
        end_date=end_date,
        auction_type=auction_type,
    )
    
    # Write to Parquet
    writer = ParquetWriter(DIRS["parquet"], validate=True)
    result = writer.write_facts(
        facts=facts,
        iso_code=iso_code,
        market_type="CAPACITY",
    )
    
    # Log to SQLite
    log_ingestion(
        dataset=dataset_name,
        iso=iso_code,
        status="SUCCESS",
        rows=len(facts),
    )
    
    # Refresh DuckDB views
    duckdb_views = DuckDBViews(DUCKDB_DB, DIRS["parquet"])
    duckdb_views.refresh_views()
    
    return result
```

### 6.3 Extend `ISOVis` for Capacity
```python
# In visualization/iso_vis.py
def fig_capacity_timeseries(
    self,
    zones: Optional[list] = None,
    start_month: Optional[str] = None,  # YYYYMM
    end_month: Optional[str] = None,
) -> plt.Figure:
    """Monthly capacity price time series."""
    # Load capacity data using ISODataAdapter
    adapter = create_iso_data_adapter(
        iso_code=self.iso_code,
        dataset='capacity_monthly',
        year=int(self.year),
        parquet_base=self.parquet_base,
        duckdb_path=self.duckdb_path,
    )
    
    df = adapter.df
    
    # Filter by zones and date range
    # ... visualization logic ...
```

---

## 7. Recommendations Summary

### ✅ **Do This**

1. **Use delivery_month as time index** for ICAP visualizations
2. **Create capacity pipeline** similar to energy pipeline
3. **Log to SQLite** using same `log_ingestion()` function
4. **Extend ISODataAdapter** to handle CAPACITY market type
5. **Create ICAP-specific dataset type**: `"capacity_monthly"` or `"icap_monthly"`

### ⚠️ **Consider This**

1. **Monthly granularity limitation**: Some NYISOToolkit methods assume hourly data
2. **One-to-many relationship**: One auction → multiple delivery months needs careful handling
3. **Auction vs Delivery views**: May want both (by auction_month and by delivery_month)

### ❌ **Don't Do This**

1. **Don't force hourly structure** on monthly ICAP data
2. **Don't lose auction_month information** when pivoting
3. **Don't mix auction_month and delivery_month** in same time series

---

## 8. Next Steps

1. **Create capacity pipeline** (`pipelines/capacity_pipeline.py`)
2. **Add `--capacity` flag** to `run_pipeline.py`
3. **Extend ISODataAdapter** for CAPACITY market type
4. **Test with real ICAP data** (Winter 2023-2024)
5. **Create ICAP visualizations** using adapted NYISOToolkit methods
6. **Document usage** in `DATA_COMMANDS_REFERENCE.md`

---

## 9. Example Usage (Future)

```python
# Fetch ICAP data
python run_pipeline.py --capacity --iso NYISO --start-date 2023-11-01 --end-date 2024-04-30

# Visualize in Jupyter
from visualization.iso_vis import ISOVis

vis = ISOVis(iso_code='NYISO', year=2024)

# Monthly capacity price time series
fig = vis.fig_capacity_timeseries(zones=['NYC', 'LI'])
plt.show()

# Capacity price distribution
fig = vis.fig_price_pdf(dataset='capacity_monthly', zones=['NYC'])
plt.show()

# Zone comparison
fig = vis.fig_zone_comparison(dataset='capacity_monthly', zones=['NYC', 'LI', 'G-J'])
plt.show()
```
