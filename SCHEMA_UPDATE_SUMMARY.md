# Schema Update Summary

## Overview
Updated the data pipeline to include YYYYMM month tracking, zone normalization, and data validation. This enables proper temporal analysis across energy and capacity markets, especially for ICAP capability periods.

## Key Changes

### 1. Zone Normalization System (`canonical/zone_normalization.py`)
- **Purpose**: Normalize zone name variations (e.g., "N.Y.C." → "NYC")
- **Features**:
  - Direct mapping for known variations
  - Case-insensitive matching
  - Automatic cleaning (remove periods, normalize spaces)
  - Preserves original names for traceability

### 2. Temporal Utilities (`canonical/temporal_utils.py`)
- **YYYYMM Format**: String format for month-level aggregation (e.g., "202401" for January 2024)
- **Functions**:
  - `datetime_to_yyyymm(dt)`: Convert datetime to YYYYMM
  - `yyyymm_to_datetime(yyyymm)`: Convert YYYYMM to datetime
  - `validate_yyyymm(yyyymm)`: Validate YYYYMM format
  - `get_capability_period(delivery_month)`: Determine SUMMER/WINTER from delivery month
  - `get_delivery_months_for_strip()`: Get all months in a capability period

### 3. Enhanced Schema (`canonical/schemas.py`)
**New Required Fields**:
- `auction_month` (str, YYYYMM): When auction/market cleared
- `delivery_month` (str, YYYYMM): When price/capacity applies

**New Optional Fields**:
- `capability_period` (str): "SUMMER" or "WINTER" for capacity markets
- `auction_type` (str): "MONTHLY", "STRIP", or "SPOT" for capacity markets
- `zone_normalized` (str): Normalized zone name
- `zone_original` (str): Original zone name from source
- `data_quality_score` (float): Quality score 0-1
- `validation_errors` (List[str]): List of validation errors

**Preserved Fields**:
- `start_time` / `end_time`: Full datetime precision (preserved from source)

### 4. Data Validation (`canonical/validation.py`)
- **DataValidator Class**: Validates and cleans MarketPriceFact objects
- **Validations**:
  - Zone name normalization
  - YYYYMM format validation
  - Price range checks
  - Timestamp validation
  - Unit consistency
  - Capability period matching
  - Auction/delivery month relationships
- **Returns**: Cleaned fact + list of errors

### 5. Updated Normalization Functions (`canonical/normalize.py`)
- **normalize_energy_price()**:
  - Extracts `auction_month` and `delivery_month` from timestamps
  - For DA markets: auction typically day before delivery
  - For RT markets: auction and delivery same hour
  - Normalizes zone names automatically
  
- **normalize_capacity_price()**:
  - Extracts `auction_month` from auction time
  - Extracts `delivery_month` from delivery period
  - Infers `capability_period` if not provided
  - Normalizes zone names automatically

### 6. Enhanced ParquetWriter (`storage/parquet_writer.py`)
- **Partitioning**: Now partitions by `delivery_month` (not `start_time`)
- **Validation**: Optional validation during write
- **Return Format**: Returns dict with:
  - `files`: List of written file paths
  - `rows_written`: Number of rows written
  - `errors`: List of validation errors
  - `warnings`: List of validation warnings

### 7. Updated Pipeline (`pipelines/energy_pipeline.py`)
- Uses new ParquetWriter return format
- Displays validation errors and warnings
- Tracks validation metrics in results

## Temporal Model

### Energy Markets (DAM/HAM)
- **auction_month**: When market cleared (typically same month or previous month)
- **delivery_month**: When price applies (typically same month)
- **Example**: DAM clears Jan 1, 2024 for Jan 2, 2024 delivery
  - `auction_month` = "202401"
  - `delivery_month` = "202401"

### Capacity Markets (ICAP)
- **auction_month**: When auction ran (can be months before delivery)
- **delivery_month**: When capacity applies (capability period month)
- **capability_period**: "SUMMER" (May-Oct) or "WINTER" (Nov-Apr)
- **Example**: Monthly auction runs March 2024, clears capacity for May 2024
  - `auction_month` = "202403"
  - `delivery_month` = "202405"
  - `capability_period` = "SUMMER"

## Benefits

1. **Unified Temporal Model**: Same structure for energy and capacity markets
2. **Efficient Queries**: Month-level aggregation without datetime complexity
3. **Capability Period Support**: Handles Winter period crossing calendar years
4. **Data Quality**: Validation and quality scoring built-in
5. **Zone Consistency**: Automatic normalization fixes "N.Y.C." vs "NYC" issues
6. **Traceability**: Original values preserved for debugging

## Testing

Run `test_new_schema.py` to verify:
- Zone normalization
- Temporal utilities
- Energy normalization
- Data validation

All tests pass ✓

## Next Steps

1. **Load Test Data**: Run pipeline with real data to verify end-to-end
2. **Data Quality Report**: Generate reports on zone variations, temporal coverage
3. **ICAP Adapter**: Implement capacity market adapter with proper month tracking
4. **Visualizations**: Build charts using YYYYMM fields for month-level analysis

