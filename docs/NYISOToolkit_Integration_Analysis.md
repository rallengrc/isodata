# NYISOToolkit Integration Analysis

## Executive Summary

**YES, it is absolutely possible to make other ISO data "look like" NYISO data** and leverage NYISOToolkit's analytics and visualization tools for all ISOs. This would be a powerful feature that significantly extends the value of the pipeline.

## Deep Analysis of NYISOToolkit

### 1. Architecture Overview

NYISOToolkit has three main classes:

#### **NYISOData** (Data Access Layer)
- **Purpose**: Downloads and structures NYISO data
- **Key Attributes**:
  - `.df`: Pandas DataFrame with the actual data
  - `.dataset`: Dataset name (e.g., 'lbmp_dam_h', 'load_5m')
  - `.year`: Year of data
  - `.f`: Frequency attribute ('5min' or 'h')
- **DataFrame Structure**:
  - **Index**: DatetimeIndex with timezone (UTC, converted to US/Eastern)
  - **Columns**: MultiIndex tuples like `('LBMP ($/MWHr)', 'CAPITL')`
  - **Format**: Wide format (zones as columns, time as rows)
  - **Example**:
    ```
    Time Stamp                    ('LBMP ($/MWHr)', 'CAPITL')  ('LBMP ($/MWHr)', 'CENTRL')  ...
    2024-01-01 05:00:00+00:00    25.02                        24.25                        ...
    ```

#### **NYISOStat** (Analytics Layer)
- **Purpose**: Statistical analysis and data transformation
- **Initialization**: `NYISOStat(year=2024)`
- **Key Methods**:
  - `table_hourly_dataset(dataset, year)`: Converts power to energy, resamples hourly
  - `table_average_day_load()`: Average hourly load across year
  - `table_average_day_dataset()`: Average hourly values for any dataset
  - `table_annual_energy()`: Annual energy summary
  - `table_instate_flow()`: Flow between upstate/downstate
- **How It Works**: 
  - Internally creates `NYISOData(dataset=..., year=...)` objects
  - Accesses `.df` attribute
  - Performs transformations and aggregations

#### **NYISOVis** (Visualization Layer)
- **Purpose**: Creates publication-quality visualizations
- **Initialization**: `NYISOVis(year=2024, out_dir=Path(...))`
- **Key Methods**:
  - `fig_energy_generation()`: Stacked area chart of generation by fuel type
  - `fig_price_pdf()`: Price distribution PDF
  - `fig_price_difference_pdf()`: Price difference distributions
  - `fig_carbon_free_timeseries()`: Carbon-free energy trends
  - `fig_decarbonization_clock()`: Circular decarbonization visualization
  - `fig_demand_pdf()`: Load distribution
  - `tables_energy_generation()`: Prepares data for energy charts
- **How It Works**:
  - Creates `NYISOData` objects internally
  - Accesses `.df` attributes
  - Uses matplotlib/seaborn for visualization
  - **Works in Jupyter**: Yes! All visualization methods return matplotlib figures

### 2. Data Format Requirements

For other ISOs to work with NYISOStat and NYISOVis, we need to create DataFrames that match this structure:

**Required Structure:**
```python
# Index: DatetimeIndex with timezone
index = pd.DatetimeIndex([...], tz='UTC')  # or 'US/Eastern'

# Columns: MultiIndex (metric, zone)
columns = pd.MultiIndex.from_tuples([
    ('LBMP ($/MWHr)', 'NYC'),
    ('LBMP ($/MWHr)', 'LI'),
    ...
])

# Data: Wide format (time x zones)
df = pd.DataFrame(data, index=index, columns=columns)

# Frequency attribute (for resampling)
df.f = 'h'  # or '5min'
```

### 3. Integration Strategy

#### Option A: Adapter Pattern (Recommended)

Create adapter classes that mimic `NYISOData` interface:

```python
class ISODataAdapter:
    """Adapter to make any ISO data look like NYISOData"""
    
    def __init__(self, iso_code, dataset_type, year):
        self.iso_code = iso_code
        self.dataset_type = dataset_type
        self.year = year
        self._df = None  # Will be populated
    
    @property
    def df(self):
        """Return DataFrame in NYISO format"""
        if self._df is None:
            self._df = self._load_and_transform()
        return self._df
    
    def _load_and_transform(self):
        """Load from our canonical schema and transform to NYISO format"""
        # 1. Load from Parquet (our canonical format)
        # 2. Pivot to wide format (zones as columns)
        # 3. Create MultiIndex columns
        # 4. Set timezone
        # 5. Add frequency attribute
        pass
```

#### Option B: Wrapper Functions

Create wrapper functions that transform our canonical data:

```python
def canonical_to_nyiso_format(canonical_df, iso_code):
    """
    Transform canonical MarketPriceFact DataFrame to NYISO format
    
    Args:
        canonical_df: DataFrame from our Parquet storage
        iso_code: ISO identifier
    
    Returns:
        DataFrame in NYISO format (ready for NYISOStat/NYISOVis)
    """
    # Pivot: time x zones
    # Create MultiIndex columns
    # Set timezone
    # Add .f attribute
    pass
```

### 4. Implementation Plan

#### Phase 1: NYISO Compatibility Layer

1. **Create `adapters/nyiso_compat.py`**:
   - `ISODataAdapter` class that mimics `NYISOData`
   - Transforms canonical schema → NYISO format
   - Handles different ISOs (PJM, ISO-NE, etc.)

2. **Create `analytics/iso_stat.py`**:
   - Wrapper around `NYISOStat` that works with `ISODataAdapter`
   - Extends functionality for multi-ISO comparisons

3. **Create `visualization/iso_vis.py`**:
   - Wrapper around `NYISOVis` that works with `ISODataAdapter`
   - Adds cross-ISO comparison charts

#### Phase 2: Enhanced Features

1. **Multi-ISO Comparisons**:
   - Side-by-side charts
   - Normalized comparisons
   - Regional analysis

2. **Unified Analytics**:
   - Cross-ISO statistics
   - National trends
   - Market comparisons

### 5. Code Example

```python
from adapters.nyiso_compat import ISODataAdapter
from nyisotoolkit import NYISOStat, NYISOVis

# Create adapter for PJM data
pjm_data = ISODataAdapter(
    iso_code='PJM',
    dataset_type='lbmp_dam_h',  # Day-ahead LMP
    year=2024
)

# Now use NYISOStat with PJM data!
pjm_stat = NYISOStat(year=2024)
# We'd need to modify NYISOStat to accept custom data sources
# OR create our own wrapper

# Use NYISOVis with PJM data
pjm_vis = NYISOVis(year=2024)
# Similar modification needed

# Or better: Create unified wrapper
from analytics.iso_stat import ISOStat
from visualization.iso_vis import ISOVis

# Works with any ISO!
iso_stat = ISOStat(iso_code='PJM', year=2024)
iso_vis = ISOVis(iso_code='PJM', year=2024)

# Generate charts
fig = iso_vis.fig_price_pdf()  # Works for PJM!
```

### 6. Challenges & Solutions

#### Challenge 1: Column Naming
- **NYISO**: `('LBMP ($/MWHr)', 'NYC')`
- **Other ISOs**: Different naming conventions
- **Solution**: Create mapping/translation layer

#### Challenge 2: Zone Differences
- **NYISO**: Specific zones (NYC, LI, etc.)
- **Other ISOs**: Different zone structures
- **Solution**: Normalize zone names or create zone mapping

#### Challenge 3: Frequency Differences
- **NYISO**: 5-minute or hourly
- **Other ISOs**: May have different frequencies
- **Solution**: Resample to match (5min or hourly)

#### Challenge 4: Timezone Handling
- **NYISO**: US/Eastern
- **Other ISOs**: May use different timezones
- **Solution**: Convert all to UTC, then to target timezone

### 7. Benefits

✅ **Reuse Existing Analytics**: All NYISOStat methods work for other ISOs
✅ **Reuse Visualizations**: All NYISOVis charts work for other ISOs
✅ **Jupyter Integration**: Works seamlessly in notebooks
✅ **Consistent Interface**: Same API for all ISOs
✅ **Extensibility**: Easy to add new ISOs
✅ **Comparison Capabilities**: Side-by-side ISO analysis

### 8. Jupyter Integration

**Yes, NYISOToolkit is designed for Jupyter!**

- All visualization methods return matplotlib figures
- Can be displayed inline in notebooks
- Interactive exploration
- Perfect for our Phase 4 goals

### 9. Recommended Next Steps

1. **Create compatibility layer** (`adapters/nyiso_compat.py`)
2. **Test with NYISO data first** (verify transformation works)
3. **Extend to one other ISO** (PJM as proof of concept)
4. **Create wrapper classes** for NYISOStat/NYISOVis
5. **Build multi-ISO comparison tools**
6. **Add to Jupyter notebooks**

### 10. Conclusion

This integration is not only possible but **highly recommended**. It would:
- Dramatically accelerate analytics development
- Provide professional visualizations out of the box
- Enable powerful cross-ISO comparisons
- Leverage existing, tested code
- Work seamlessly with Jupyter

The key is creating a clean adapter layer that transforms our canonical schema into NYISO's expected format. This is a well-understood pattern and should be straightforward to implement.

