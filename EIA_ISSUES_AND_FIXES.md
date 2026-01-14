# EIA Data Issues and Fixes

## Issues Identified

### 1. **Price Units Mismatch (CRITICAL)**
- **NYISO**: $20-98/MWh (correct)
- **EIA**: $14,063-20,804/MWh (WRONG - 200x too high!)
- **Root Cause**: EIA API endpoint `/rto/region-data/data/` with `facets[type][]="D"` is likely returning:
  - Load data (MW) instead of price data ($/MWh)
  - OR a different metric that's not price
  - OR needs unit conversion

### 2. **Timezone Offset (5 hours)**
- **NYISO**: Starts at `2024-01-01 05:00:00 UTC` (midnight EST converted to UTC) ✅
- **EIA**: Starts at `2024-01-01 00:00:00 UTC` (treating as UTC, but should be EST)
- **Root Cause**: EIA API returns times in EST/EDT but we're treating them as UTC
- **Impact**: 5-hour misalignment (EST is UTC-5 in winter)

### 3. **Data Granularity Difference**
- **NYISO**: 15 zones (zone-level prices)
- **EIA**: 1 zone (system-wide aggregate)
- **Note**: This is expected - EIA provides system-wide data

### 4. **Data Completeness**
- **NYISO**: 140 timestamps, 2,100 records (15 zones × 140 hours)
- **EIA**: 145 timestamps, 145 records (1 zone × 145 hours)
- **Note**: EIA has slightly more timestamps (covers full range including hour 0)

## Solutions

### Fix 1: Correct EIA Timezone Handling

EIA API returns times in **Eastern Time (EST/EDT)**, not UTC. We need to:
1. Parse the period string as EST/EDT
2. Convert to UTC for storage

**Current Code (WRONG)**:
```python
period_dt = datetime.strptime(period_str, "%Y-%m-%dT%H")
period_dt = pytz.UTC.localize(period_dt)  # ❌ Wrong - treats as UTC
```

**Fixed Code**:
```python
period_dt = datetime.strptime(period_str, "%Y-%m-%dT%H")
# EIA returns times in Eastern Time, localize to EST/EDT then convert to UTC
eastern = pytz.timezone('US/Eastern')
period_dt = eastern.localize(period_dt)
period_dt = period_dt.astimezone(pytz.UTC)  # ✅ Convert to UTC
```

### Fix 2: Investigate and Fix Price Data

The EIA values (14,000-20,000) suggest we're getting the wrong series. Options:

**Option A**: Check if we need a different facet/parameter for price data
- May need `facets[price-type][]` or different endpoint
- EIA v2 API might require specific series IDs for prices

**Option B**: The values might need conversion
- If it's load-weighted price, might need to divide by load
- Or multiply/divide by a factor

**Option C**: Use a different EIA endpoint
- EIA might have a specific wholesale price endpoint
- Or need to use series IDs like `EBA.NYIS-ALL.D.HL` (load-weighted price)

**Immediate Action**: 
1. Check EIA API documentation for correct price endpoint
2. Test with different facets/parameters
3. Verify units in API response metadata

### Fix 3: Ensure Consistent Timezone Storage

Both should store as UTC in Parquet:
- ✅ NYISO: Already correct (stores as UTC)
- ❌ EIA: Currently stores as UTC but from wrong source timezone

After Fix 1, both will correctly store UTC times.

## Recommended Implementation Order

1. **Fix timezone first** (Fix 1) - This is straightforward
2. **Investigate price issue** (Fix 2) - May require API documentation review
3. **Re-download EIA data** with fixes applied
4. **Re-run comparison** to verify alignment

## Testing

After fixes:
- Run `analyze_timezone_issue.py` to verify timezone alignment
- Run `compare_nyiso_eia.py` to verify price alignment
- Check that timestamps align within 1 hour (accounting for any legitimate differences)

