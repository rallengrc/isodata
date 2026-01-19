"""
Capacity price data pipeline.
"""

from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
from adapters.base import ISOAdapter
from storage.parquet_writer import ParquetWriter
from storage.duckdb_views import DuckDBViews
from run_pipeline import SQLITE_DB, DUCKDB_DB, DIRS, log_ingestion


def run_capacity_pipeline(
    adapter: ISOAdapter,
    start_date: datetime,
    end_date: datetime,
    nodes: Optional[list] = None,
    auction_type: Optional[str] = None,
) -> dict:
    """
    Run capacity price pipeline.
    
    Args:
        adapter: ISO adapter instance
        start_date: Start date/time (for delivery period)
        end_date: End date/time (for delivery period)
        nodes: Optional list of nodes to fetch
        auction_type: "MONTHLY", "STRIP", or None for all
    
    Returns:
        Dictionary with pipeline results
    """
    iso_code = adapter.get_iso_code()
    auction_type_str = auction_type.lower() if auction_type else "all"
    dataset_name = f"capacity_{auction_type_str}_{iso_code.lower()}"
    
    # Track start time
    start_time = datetime.utcnow()
    
    try:
        # Fetch data
        print(f"Fetching {iso_code} capacity prices ({auction_type or 'all types'}) from {start_date.date()} to {end_date.date()}...")
        facts = adapter.fetch_capacity_prices(
            start_date=start_date,
            end_date=end_date,
            nodes=nodes,
            auction_type=auction_type,
        )
        
        if not facts:
            print(f"No data fetched for {iso_code}")
            log_ingestion(
                dataset=dataset_name,
                iso=iso_code,
                status="NO_DATA",
                rows=0,
            )
            return {"status": "no_data", "rows": 0}
        
        print(f"Fetched {len(facts)} capacity price records")
        
        # Write to Parquet (with validation)
        parquet_writer = ParquetWriter(DIRS["parquet"], validate=True)
        write_result = parquet_writer.write_facts(
            facts=facts,
            iso_code=iso_code,
            market_type="CAPACITY",
        )
        
        written_files = write_result['files']
        rows_written = write_result['rows_written']
        errors = write_result['errors']
        warnings = write_result['warnings']
        
        print(f"Wrote {len(written_files)} Parquet files ({rows_written} rows)")
        
        if errors:
            print(f"⚠ Validation errors: {len(errors)}")
            for error in errors[:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(errors) > 5:
                print(f"  ... and {len(errors) - 5} more errors")
        
        if warnings:
            print(f"ℹ Validation warnings: {len(warnings)}")
            for warning in warnings[:5]:  # Show first 5 warnings
                print(f"  - {warning}")
            if len(warnings) > 5:
                print(f"  ... and {len(warnings) - 5} more warnings")
        
        # Refresh DuckDB views
        duckdb_views = DuckDBViews(DUCKDB_DB, DIRS["parquet"])
        duckdb_views.refresh_views()
        duckdb_views.close()
        
        print("Refreshed DuckDB views")
        
        # Log successful ingestion
        end_time = datetime.utcnow()
        log_ingestion(
            dataset=dataset_name,
            iso=iso_code,
            status="SUCCESS",
            rows=len(facts),
            start_time=start_time,
            end_time=end_time,
        )
        
        return {
            "status": "success",
            "rows": rows_written,
            "files": len(written_files),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "validation_errors": len(errors),
            "validation_warnings": len(warnings),
        }
    
    except Exception as e:
        # Log error
        error_msg = str(e)
        print(f"Error in capacity pipeline: {error_msg}")
        log_ingestion(
            dataset=dataset_name,
            iso=iso_code,
            status="ERROR",
            error=error_msg,
            start_time=start_time,
            end_time=datetime.utcnow(),
        )
        raise


def backfill_capacity_data(
    adapter: ISOAdapter,
    start_year: int,
    end_year: Optional[int] = None,
    auction_type: Optional[str] = None,
    batch_size_months: int = 6,  # Process capability periods (6 months)
) -> dict:
    """
    Backfill historical capacity data.
    
    Args:
        adapter: ISO adapter instance
        start_year: Start year
        end_year: End year (defaults to current year)
        auction_type: "MONTHLY", "STRIP", or None for all
        batch_size_months: Number of months per batch (default 6 for capability periods)
    
    Returns:
        Dictionary with backfill results
    """
    if end_year is None:
        end_year = datetime.now().year
    
    print(f"Backfilling {adapter.get_iso_code()} capacity data from {start_year} to {end_year}")
    
    total_rows = 0
    total_files = 0
    errors = []
    
    # Process by capability periods (Winter: Nov-Apr, Summer: May-Oct)
    current_year = start_year
    
    while current_year <= end_year:
        # Winter period: Nov (current_year) to Apr (current_year + 1)
        winter_start = datetime(current_year, 11, 1)
        winter_end = datetime(current_year + 1, 4, 30, 23, 59, 59)
        
        # Summer period: May to Oct (current_year)
        summer_start = datetime(current_year, 5, 1)
        summer_end = datetime(current_year, 10, 31, 23, 59, 59)
        
        # Process Winter period
        if winter_start.year <= end_year + 1:  # Winter crosses year boundary
            try:
                result = run_capacity_pipeline(
                    adapter=adapter,
                    start_date=winter_start,
                    end_date=winter_end,
                    auction_type=auction_type,
                )
                
                if result["status"] == "success":
                    total_rows += result["rows"]
                    total_files += result.get("files", 0)
                    print(f"✓ Winter {current_year}-{current_year + 1}: {result['rows']} rows")
                else:
                    errors.append(f"Winter {current_year}-{current_year + 1}: {result.get('status', 'unknown')}")
            
            except Exception as e:
                error_msg = f"Winter {current_year}-{current_year + 1}: {str(e)}"
                errors.append(error_msg)
                print(f"✗ {error_msg}")
        
        # Process Summer period
        if summer_start.year <= end_year:
            try:
                result = run_capacity_pipeline(
                    adapter=adapter,
                    start_date=summer_start,
                    end_date=summer_end,
                    auction_type=auction_type,
                )
                
                if result["status"] == "success":
                    total_rows += result["rows"]
                    total_files += result.get("files", 0)
                    print(f"✓ Summer {current_year}: {result['rows']} rows")
                else:
                    errors.append(f"Summer {current_year}: {result.get('status', 'unknown')}")
            
            except Exception as e:
                error_msg = f"Summer {current_year}: {str(e)}"
                errors.append(error_msg)
                print(f"✗ {error_msg}")
        
        current_year += 1
    
    return {
        "status": "completed",
        "total_rows": total_rows,
        "total_files": total_files,
        "errors": errors,
        "error_count": len(errors),
    }


def import_capacity_from_excel(
    adapter: ISOAdapter,
    excel_file_path: Path,
    auction_types: Optional[List[str]] = None,
) -> dict:
    """
    Import capacity prices from Excel Market Report file.
    
    Args:
        adapter: ISO adapter instance (must be NYISOCapacityAdapter)
        excel_file_path: Path to Excel file
        auction_types: Which auction types to parse (None = all: MONTHLY, STRIP, SPOT)
    
    Returns:
        Dictionary with import results
    """
    iso_code = adapter.get_iso_code()
    dataset_name = f"capacity_excel_{iso_code.lower()}"
    
    # Track start time
    start_time = datetime.utcnow()
    
    try:
        # Check if adapter has Excel import method
        if not hasattr(adapter, 'fetch_capacity_prices_from_excel'):
            raise ValueError(f"Adapter {type(adapter).__name__} does not support Excel import")
        
        # Fetch data from Excel
        print(f"Importing {iso_code} capacity prices from Excel file: {excel_file_path}")
        facts = adapter.fetch_capacity_prices_from_excel(
            excel_file_path=excel_file_path,
            auction_types=auction_types,
        )
        
        if not facts:
            print(f"No data found in Excel file")
            log_ingestion(
                dataset=dataset_name,
                iso=iso_code,
                status="NO_DATA",
                rows=0,
            )
            return {"status": "no_data", "rows": 0}
        
        print(f"Parsed {len(facts)} capacity price records from Excel")
        
        # Write to Parquet (with validation)
        parquet_writer = ParquetWriter(DIRS["parquet"], validate=True)
        write_result = parquet_writer.write_facts(
            facts=facts,
            iso_code=iso_code,
            market_type="CAPACITY",
        )
        
        written_files = write_result['files']
        rows_written = write_result['rows_written']
        errors = write_result['errors']
        warnings = write_result['warnings']
        
        print(f"Wrote {len(written_files)} Parquet files ({rows_written} rows)")
        
        if errors:
            print(f"⚠ Validation errors: {len(errors)}")
            for error in errors[:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(errors) > 5:
                print(f"  ... and {len(errors) - 5} more errors")
        
        if warnings:
            print(f"ℹ Validation warnings: {len(warnings)}")
            for warning in warnings[:5]:  # Show first 5 warnings
                print(f"  - {warning}")
            if len(warnings) > 5:
                print(f"  ... and {len(warnings) - 5} more warnings")
        
        # Refresh DuckDB views
        duckdb_views = DuckDBViews(DUCKDB_DB, DIRS["parquet"])
        duckdb_views.refresh_views()
        duckdb_views.close()
        
        print("Refreshed DuckDB views")
        
        # Log successful ingestion
        end_time = datetime.utcnow()
        log_ingestion(
            dataset=dataset_name,
            iso=iso_code,
            status="SUCCESS",
            rows=len(facts),
            start_time=start_time,
            end_time=end_time,
        )
        
        return {
            "status": "success",
            "rows": rows_written,
            "files": len(written_files),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "validation_errors": len(errors),
            "validation_warnings": len(warnings),
        }
    
    except Exception as e:
        # Log error
        error_msg = str(e)
        print(f"Error importing from Excel: {error_msg}")
        log_ingestion(
            dataset=dataset_name,
            iso=iso_code,
            status="ERROR",
            error=error_msg,
            start_time=start_time,
            end_time=datetime.utcnow(),
        )
        raise
