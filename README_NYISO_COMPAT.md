# NYISOToolkit Compatibility Layer

## Overview

This compatibility layer allows you to use **NYISOToolkit's analytics and visualization tools with any ISO**, not just NYISO!

## What It Does

The compatibility layer transforms data from our canonical schema (stored in Parquet) into the format expected by NYISOToolkit's `NYISOStat` and `NYISOVis` classes. This means:

- ✅ **Reuse NYISOStat analytics** for any ISO (PJM, ISO-NE, MISO, etc.)
- ✅ **Reuse NYISOVis visualizations** for any ISO
- ✅ **Compare multiple ISOs** side-by-side
- ✅ **Work in Jupyter notebooks** seamlessly

## Quick Start

### 1. Statistics (NYISOStat-style)

```python
from analytics.iso_stat import ISOStat

# For NYISO
nyiso_stat = ISOStat(iso_code='NYISO', year=2024)
price_stats = nyiso_stat.get_price_statistics('lbmp_dam_h')

# For PJM (once data is loaded)
pjm_stat = ISOStat(iso_code='PJM', year=2024)
pjm_price_stats = pjm_stat.get_price_statistics('lmp_dam_h')
```

### 2. Visualizations (NYISOVis-style)

```python
from visualization.iso_vis import ISOVis

# Create visualization object
nyiso_vis = ISOVis(iso_code='NYISO', year=2024)

# Generate price PDF
fig = nyiso_vis.fig_price_pdf(dataset='lbmp_dam_h', zones=['NYC', 'LI'])
plt.show()

# Generate time series
fig = nyiso_vis.fig_price_timeseries(
    dataset='lbmp_dam_h',
    zones=['NYC', 'LI'],
    start_date='2024-01-01',
    end_date='2024-01-07'
)
plt.show()
```

### 3. Multi-ISO Comparison

```python
from analytics.iso_stat import compare_isos
from visualization.iso_vis import compare_isos_visualization

# Compare statistics
comparison = compare_isos(
    iso_codes=['NYISO', 'PJM', 'ISO-NE'],
    dataset='lbmp_dam_h',
    year=2024,
    metric='mean'
)

# Visualize comparison
fig = compare_isos_visualization(
    iso_codes=['NYISO', 'PJM', 'ISO-NE'],
    dataset='lbmp_dam_h',
    year=2024
)
plt.show()
```

## Architecture

### ISODataAdapter

The core adapter class that transforms canonical schema → NYISO format:

```python
from adapters.nyiso_compat import ISODataAdapter

adapter = ISODataAdapter(
    iso_code='PJM',
    dataset_type='lmp_dam_h',
    year=2024
)

# Get DataFrame in NYISO format
df = adapter.df  # MultiIndex columns, DatetimeIndex
```

### Transformation Process

1. **Load** data from Parquet (canonical schema)
2. **Pivot** to wide format (time × zones)
3. **Create MultiIndex** columns: `('Metric Name', 'Zone Name')`
4. **Set timezone** (UTC → US/Eastern)
5. **Add frequency** attribute (`'h'` or `'5min'`)

## Available Methods

### ISOStat Methods

- `table_hourly_dataset(dataset)`: Convert to hourly energy [GWh]
- `table_average_day_dataset(dataset)`: Average hourly values across year
- `table_average_day_load()`: Average daily load pattern
- `get_price_statistics(dataset)`: Price stats by zone

### ISOVis Methods

- `fig_price_pdf(dataset, zones)`: Price probability density function
- `fig_price_timeseries(dataset, zones, dates)`: Price time series
- `fig_zone_comparison(dataset, zones)`: Box plot comparing zones
- `save_figure(fig, filename)`: Save figure to file

## Demo Notebook

See `notebooks/nyiso_compat_demo.ipynb` for a complete example.

## Benefits

1. **Code Reuse**: Leverage NYISOToolkit's tested analytics
2. **Consistency**: Same interface for all ISOs
3. **Extensibility**: Easy to add new ISOs
4. **Comparison**: Built-in multi-ISO comparison tools
5. **Jupyter**: Works seamlessly in notebooks

## Future Enhancements

- Direct integration with NYISOToolkit's NYISOStat/NYISOVis (requires modification)
- Additional visualization types
- More statistical methods
- Real-time data support

