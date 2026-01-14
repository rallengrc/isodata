"""
Energy price data pipeline.
"""

from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import sqlite3
from adapters.base import ISOAdapter
from storage.parquet_writer import ParquetWriter
from storage.duckdb_views import DuckDBViews
from run_pipeline import SQLITE_DB, DUCKDB_DB, DIRS, log_ingestion


def run_energy_pipeline(
    adapter: ISOAdapter,
    start_date: datetime,
    end_date: datetime,
    nodes: Optional[list] = None,
    product: str = "DA",
) -> dict:
    """
    Run energy price pipeline.
    
    Args:
        adapter: ISO adapter instance
        start_date: Start date/time
        end_date: End date/time
        nodes: Optional list of nodes to fetch
        product: "DA" or "RT"
    
    Returns:
        Dictionary with pipeline results
    """
    iso_code = adapter.get_iso_code()
    dataset_name = f"energy_{product.lower()}_{iso_code.lower()}"
    
    # Track start time
    start_time = datetime.utcnow()
    
    try:
        # Fetch data
        print(f"Fetching {iso_code} energy prices ({product}) from {start_date} to {end_date}...")
        facts = adapter.fetch_energy_prices(
            start_date=start_date,
            end_date=end_date,
            nodes=nodes,
            product=product,
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
        
        print(f"Fetched {len(facts)} price records")
        
        # Write to Parquet (with validation)
        parquet_writer = ParquetWriter(DIRS["parquet"], validate=True)
        write_result = parquet_writer.write_facts(
            facts=facts,
            iso_code=iso_code,
            market_type="ENERGY",
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
        print(f"Error in energy pipeline: {error_msg}")
        log_ingestion(
            dataset=dataset_name,
            iso=iso_code,
            status="ERROR",
            error=error_msg,
        )
        raise


def backfill_energy_data(
    adapter: ISOAdapter,
    start_year: int,
    end_year: Optional[int] = None,
    product: str = "DA",
    batch_size_days: int = 30,
) -> dict:
    """
    Backfill historical energy data.
    
    Args:
        adapter: ISO adapter instance
        start_year: Start year
        end_year: End year (defaults to current year)
        product: "DA" or "RT"
        batch_size_days: Number of days per batch
    
    Returns:
        Dictionary with backfill results
    """
    if end_year is None:
        end_year = datetime.now().year
    
    print(f"Backfilling {adapter.get_iso_code()} energy data from {start_year} to {end_year}")
    
    total_rows = 0
    total_files = 0
    errors = []
    
    current_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31, 23, 59, 59)
    
    while current_date < end_date:
        batch_end = min(
            current_date + timedelta(days=batch_size_days),
            end_date
        )
        
        try:
            result = run_energy_pipeline(
                adapter=adapter,
                start_date=current_date,
                end_date=batch_end,
                product=product,
            )
            
            if result["status"] == "success":
                total_rows += result["rows"]
                total_files += result.get("files", 0)
                print(f"✓ {current_date.date()} to {batch_end.date()}: {result['rows']} rows")
            else:
                errors.append(f"{current_date.date()} to {batch_end.date()}: {result.get('status', 'unknown')}")
        
        except Exception as e:
            error_msg = f"{current_date.date()} to {batch_end.date()}: {str(e)}"
            errors.append(error_msg)
            print(f"✗ {error_msg}")
        
        current_date = batch_end + timedelta(seconds=1)
    
    return {
        "status": "completed",
        "total_rows": total_rows,
        "total_files": total_files,
        "errors": errors,
        "error_count": len(errors),
    }

