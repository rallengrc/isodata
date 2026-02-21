#!/usr/bin/env python3
"""
Coordinated purge: Delete both Parquet files AND matching SQLite metadata.

This script coordinates between:
- storage/purge_data.py (deletes Parquet files)
- SQLite metadata.db (deletes matching metadata rows)

It ensures Parquet data and metadata stay in sync when purging.

IMPORTANT: url_registry is NEVER purged unless --url flag is explicitly provided.

Usage examples:
    # List all data (read-only)
    python scripts/purge_everything.py --list
    
    # Purge all data (Parquet + metadata) - requires --confirm
    python scripts/purge_everything.py --purge-all --confirm
    
    # Purge NYISO data (Parquet + metadata)
    python scripts/purge_everything.py --purge-iso NYISO --confirm
    
    # Purge January 2024 data (Parquet + metadata)
    python scripts/purge_everything.py --purge-month 202401 --confirm
    
    # Purge January 2024 CAPACITY data for NYISO (Parquet + metadata)
    python scripts/purge_everything.py --purge-month 202401 --iso NYISO --market-type CAPACITY --confirm
    
    # Purge metadata only (no Parquet) - same as purge_metadata_sqlite.py
    python scripts/purge_everything.py --purge-metadata-only --logs-only --yes
"""

import argparse
import sys
import sqlite3
from pathlib import Path
import json
from typing import Optional, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from storage.purge_data import DataPurge
from storage.duckdb_views import DuckDBViews
from run_pipeline import DIRS, DUCKDB_DB, SQLITE_DB


def purge_metadata_by_iso(iso_code: str, include_urls: bool = False) -> dict:
    """
    Purge SQLite metadata for a specific ISO.
    
    Args:
        iso_code: ISO identifier (e.g., "NYISO")
        include_urls: If True, also purge url_registry (default: False)
    
    Returns:
        dict with purge results
    """
    conn = sqlite3.connect(SQLITE_DB)
    try:
        cursor = conn.cursor()
        deleted_counts = {}
        
        # Purge ingestion_log
        cursor.execute("DELETE FROM ingestion_log WHERE iso_code = ?", (iso_code.upper(),))
        deleted_counts['ingestion_log'] = cursor.rowcount
        
        # Purge data_source
        cursor.execute("DELETE FROM data_source WHERE iso_code = ?", (iso_code.upper(),))
        deleted_counts['data_source'] = cursor.rowcount
        
        # Purge dataset_version (if dataset_name matches ISO pattern)
        cursor.execute("DELETE FROM dataset_version WHERE dataset_name LIKE ?", (f'%{iso_code.lower()}%',))
        deleted_counts['dataset_version'] = cursor.rowcount
        
        # Purge url_registry ONLY if explicitly requested
        if include_urls:
            cursor.execute("DELETE FROM url_registry WHERE iso_code = ?", (iso_code.upper(),))
            deleted_counts['url_registry'] = cursor.rowcount
        
        conn.commit()
        
        return {
            "status": "success",
            "iso_code": iso_code,
            "tables_purged": deleted_counts,
        }
    finally:
        conn.close()


def purge_metadata_by_month(
    delivery_month: str,
    iso_code: Optional[str] = None,
    market_type: Optional[str] = None,
    include_urls: bool = False
) -> dict:
    """
    Purge SQLite metadata for a specific delivery month.
    
    This is approximate - we match by dataset_name patterns and ISO code.
    More precise matching would require storing delivery_month in metadata.
    
    Args:
        delivery_month: YYYYMM string (e.g., "202401")
        iso_code: Optional ISO filter
        market_type: Optional market type filter (ENERGY, CAPACITY)
        include_urls: If True, also purge url_registry (default: False)
    
    Returns:
        dict with purge results
    """
    conn = sqlite3.connect(SQLITE_DB)
    try:
        cursor = conn.cursor()
        deleted_counts = {}
        
        # Build WHERE clause
        conditions = []
        params = []
        
        # Match by ISO if provided
        if iso_code:
            conditions.append("iso_code = ?")
            params.append(iso_code.upper())
        
        # Match by dataset_name pattern (e.g., "capacity_excel_nyiso_ICAP_Market_Report_December_2023")
        # Extract year and month from delivery_month
        year = delivery_month[:4]
        month = delivery_month[4:6]
        
        # Try to match dataset names that might contain this date
        # This is approximate - we look for patterns in dataset_name
        if market_type:
            # Match market type in dataset name
            market_pattern = f"%{market_type.lower()}%"
            conditions.append("dataset_name LIKE ?")
            params.append(market_pattern)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Purge ingestion_log
        query = f"DELETE FROM ingestion_log WHERE {where_clause}"
        cursor.execute(query, params)
        deleted_counts['ingestion_log'] = cursor.rowcount
        
        # Purge data_source
        query = f"DELETE FROM data_source WHERE {where_clause}"
        cursor.execute(query, params)
        deleted_counts['data_source'] = cursor.rowcount
        
        # Purge dataset_version (approximate match)
        query = f"DELETE FROM dataset_version WHERE {where_clause}"
        cursor.execute(query, params)
        deleted_counts['dataset_version'] = cursor.rowcount
        
        # Purge url_registry ONLY if explicitly requested
        if include_urls:
            if iso_code:
                cursor.execute("DELETE FROM url_registry WHERE iso_code = ?", (iso_code.upper(),))
                deleted_counts['url_registry'] = cursor.rowcount
        
        conn.commit()
        
        return {
            "status": "success",
            "delivery_month": delivery_month,
            "iso_code": iso_code,
            "market_type": market_type,
            "tables_purged": deleted_counts,
        }
    finally:
        conn.close()


def purge_all_metadata(include_urls: bool = False, logs_only: bool = False) -> dict:
    """
    Purge all SQLite metadata (same as purge_metadata_sqlite.py).
    
    Args:
        include_urls: If True, also purge url_registry (default: False)
        logs_only: If True, only purge ingestion_log and data_source
    
    Returns:
        dict with purge results
    """
    conn = sqlite3.connect(SQLITE_DB)
    try:
        cursor = conn.cursor()
        deleted_counts = {}
        
        if logs_only:
            # Only purge run-level metadata
            cursor.execute("DELETE FROM ingestion_log")
            deleted_counts['ingestion_log'] = cursor.rowcount
            
            cursor.execute("DELETE FROM data_source")
            deleted_counts['data_source'] = cursor.rowcount
        else:
            # Purge all metadata tables (except url_registry unless requested)
            cursor.execute("DELETE FROM ingestion_log")
            deleted_counts['ingestion_log'] = cursor.rowcount
            
            cursor.execute("DELETE FROM data_source")
            deleted_counts['data_source'] = cursor.rowcount
            
            cursor.execute("DELETE FROM dataset_version")
            deleted_counts['dataset_version'] = cursor.rowcount
            
            cursor.execute("DELETE FROM iso")
            deleted_counts['iso'] = cursor.rowcount
            
            cursor.execute("DELETE FROM market_node")
            deleted_counts['market_node'] = cursor.rowcount
        
        # Purge url_registry ONLY if explicitly requested
        if include_urls:
            cursor.execute("DELETE FROM url_registry")
            deleted_counts['url_registry'] = cursor.rowcount
        
        conn.commit()
        
        # Vacuum to reclaim space
        cursor.execute("VACUUM")
        
        return {
            "status": "success",
            "tables_purged": deleted_counts,
        }
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Coordinated purge: Delete Parquet files AND matching SQLite metadata",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    # Action selection
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--list",
        action="store_true",
        help="List all data without deleting anything",
    )
    action_group.add_argument(
        "--purge-all",
        action="store_true",
        help="Purge all Parquet data AND all metadata",
    )
    action_group.add_argument(
        "--purge-iso",
        type=str,
        metavar="ISO_CODE",
        help="Purge data for a specific ISO (Parquet + metadata)",
    )
    action_group.add_argument(
        "--purge-month",
        type=str,
        metavar="YYYYMM",
        help="Purge data for a specific delivery month (Parquet + metadata)",
    )
    action_group.add_argument(
        "--purge-year-range",
        nargs=2,
        metavar=("START_YEAR", "END_YEAR"),
        help="Purge data for a range of years (inclusive), all 12 months each year (Parquet + metadata)",
    )
    action_group.add_argument(
        "--purge-metadata-only",
        action="store_true",
        help="Purge SQLite metadata only (no Parquet files)",
    )
    
    # Filters for purge-month
    parser.add_argument(
        "--iso",
        type=str,
        metavar="ISO_CODE",
        help="Filter by ISO when purging by month",
    )
    parser.add_argument(
        "--market-type",
        type=str,
        choices=["ENERGY", "CAPACITY", "ANCILLARY"],
        help="Filter by market type when purging by month",
    )
    
    # Metadata-only options
    parser.add_argument(
        "--logs-only",
        action="store_true",
        help="When purging metadata, only purge ingestion_log and data_source",
    )
    parser.add_argument(
        "--all-metadata",
        action="store_true",
        help="When purging metadata, purge ALL tables (including iso, market_node)",
    )
    
    # URL registry (protected by default)
    parser.add_argument(
        "--url",
        action="store_true",
        help="Also purge url_registry table (NEVER purged unless this flag is used)",
    )
    
    # Confirmation
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required for all purge operations",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt (same as --confirm for purge operations)",
    )
    
    # Output format
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    
    args = parser.parse_args()
    
    # Combine --yes and --confirm
    confirmed = args.confirm or args.yes
    
    # Initialize purger
    purger = DataPurge(DIRS["parquet"], DUCKDB_DB)
    
    # Execute action
    if args.list:
        result = purger.list_data()
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("=" * 60)
            print("Data Inventory")
            print("=" * 60)
            print(f"\nTotal Parquet files: {result['total_files']}")
            print(f"\nISOs: {len(result['isos'])}")
            
            for iso_code, iso_info in result["isos"].items():
                print(f"\n  {iso_code}:")
                print(f"    Total files: {iso_info['total_files']}")
                
                for market_type, market_info in iso_info["market_types"].items():
                    print(f"    {market_type}: {market_info['total_files']} files")
                    
                    for year, year_info in market_info["years"].items():
                        months = ", ".join([m["month"] for m in year_info["months"]])
                        print(f"      {year}: {year_info['files']} files ({months})")
    
    elif args.purge_metadata_only:
        # Metadata-only purge (no Parquet)
        if not confirmed:
            print("ERROR: --purge-metadata-only requires --confirm or --yes flag")
            return 1
        
        if args.url:
            print("⚠️  WARNING: Purging url_registry (--url flag provided)")
        else:
            print("ℹ️  url_registry will NOT be purged (use --url to include it)")
        
        if not args.yes:
            confirm = input("\nType 'yes' to confirm metadata purge: ").strip().lower()
            if confirm != "yes":
                print("Aborted. No changes made.")
                return 0
        
        result = purge_all_metadata(
            include_urls=args.url,
            logs_only=args.logs_only
        )
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("=" * 60)
            print("Metadata Purge Results")
            print("=" * 60)
            print(f"Status: {result['status']}")
            for table, count in result['tables_purged'].items():
                print(f"  {table}: {count} rows deleted")
    
    elif args.purge_all:
        # Purge ALL Parquet + ALL metadata
        if not confirmed:
            print("ERROR: --purge-all requires --confirm or --yes flag")
            print("This will delete ALL Parquet data AND ALL metadata. Use with caution!")
            return 1
        
        if args.url:
            print("⚠️  WARNING: Purging url_registry (--url flag provided)")
        else:
            print("ℹ️  url_registry will NOT be purged (use --url to include it)")
        
        if not args.yes:
            confirm = input("\nType 'yes' to confirm full purge: ").strip().lower()
            if confirm != "yes":
                print("Aborted. No changes made.")
                return 0
        
        # Purge Parquet
        parquet_result = purger.purge_all(confirm=True)
        
        # Purge metadata
        metadata_result = purge_all_metadata(
            include_urls=args.url,
            logs_only=False  # --purge-all means everything
        )
        
        if args.json:
            print(json.dumps({
                "parquet": parquet_result,
                "metadata": metadata_result,
            }, indent=2))
        else:
            print("=" * 60)
            print("Full Purge Results")
            print("=" * 60)
            print("\nParquet:")
            print(f"  Files deleted: {parquet_result['files_deleted']}")
            print(f"  Views refreshed: {parquet_result['views_refreshed']}")
            print("\nMetadata:")
            for table, count in metadata_result['tables_purged'].items():
                print(f"  {table}: {count} rows deleted")
    
    elif args.purge_iso:
        # Purge ISO (Parquet + metadata)
        if not confirmed:
            print(f"ERROR: --purge-iso requires --confirm or --yes flag")
            print(f"This will delete all data for {args.purge_iso}. Use with caution!")
            return 1
        
        if args.url:
            print("⚠️  WARNING: Purging url_registry for this ISO (--url flag provided)")
        else:
            print("ℹ️  url_registry will NOT be purged (use --url to include it)")
        
        if not args.yes:
            confirm = input(f"\nType 'yes' to confirm purge for {args.purge_iso}: ").strip().lower()
            if confirm != "yes":
                print("Aborted. No changes made.")
                return 0
        
        # Purge Parquet
        parquet_result = purger.purge_by_iso(args.purge_iso, confirm=True)
        
        # Purge metadata
        metadata_result = purge_metadata_by_iso(
            args.purge_iso,
            include_urls=args.url
        )
        
        if args.json:
            print(json.dumps({
                "parquet": parquet_result,
                "metadata": metadata_result,
            }, indent=2))
        else:
            print("=" * 60)
            print(f"Purge ISO: {args.purge_iso}")
            print("=" * 60)
            print("\nParquet:")
            if parquet_result['status'] == 'success':
                print(f"  Files deleted: {parquet_result['files_deleted']}")
                print(f"  Views refreshed: {parquet_result['views_refreshed']}")
            else:
                print(f"  Status: {parquet_result.get('message', 'Unknown')}")
            print("\nMetadata:")
            for table, count in metadata_result['tables_purged'].items():
                print(f"  {table}: {count} rows deleted")
    
    elif args.purge_month or args.purge_year_range:
        # Purge by single month OR by a range of years (12 months each)
        if not confirmed:
            target_desc = (
                f"month {args.purge_month}"
                if args.purge_month
                else f"years {args.purge_year_range[0]}–{args.purge_year_range[1]}"
            )
            print(f"ERROR: purge operation for {target_desc} requires --confirm or --yes flag")
            return 1
        
        if args.url:
            print("⚠️  WARNING: Purging url_registry (--url flag provided)")
        else:
            print("ℹ️  url_registry will NOT be purged (use --url to include it)")
        
        # Build list of YYYYMM strings to purge
        months_to_purge: list[str] = []
        if args.purge_month:
            months_to_purge.append(args.purge_month)
        else:
            # Year range mode
            try:
                start_year = int(args.purge_year_range[0])
                end_year = int(args.purge_year_range[1])
            except ValueError:
                print("ERROR: --purge-year-range requires integer years, e.g. --purge-year-range 2018 2022")
                return 1
            if start_year > end_year:
                print("ERROR: START_YEAR must be <= END_YEAR")
                return 1
            for year in range(start_year, end_year + 1):
                for month in range(1, 13):
                    months_to_purge.append(f"{year}{month:02d}")
        
        # Ask for final confirmation with explicit scope
        if not args.yes:
            filters = []
            if args.iso:
                filters.append(f"ISO={args.iso}")
            if args.market_type:
                filters.append(f"Market={args.market_type}")
            filter_str = f" ({', '.join(filters)})" if filters else ""
            if args.purge_month:
                scope_desc = f"month {args.purge_month}{filter_str}"
            else:
                scope_desc = f"years {start_year}–{end_year}{filter_str}"
            confirm = input(f"\nType 'yes' to confirm purge for {scope_desc}: ").strip().lower()
            if confirm != "yes":
                print("Aborted. No changes made.")
                return 0
        
        total_parquet_deleted = 0
        views_refreshed = False
        metadata_deleted_summary: dict[str, int] = {}
        
        # Loop over months and purge Parquet + metadata
        for yyyymm in months_to_purge:
            # Purge Parquet
            parquet_result = purger.purge_by_yyyymm(
                yyyymm,
                iso_code=args.iso,
                market_type=args.market_type,
                confirm=True,
            )
            total_parquet_deleted += parquet_result["files_deleted"]
            views_refreshed = views_refreshed or parquet_result["views_refreshed"]
            
            # Purge metadata (approximate match)
            metadata_result = purge_metadata_by_month(
                yyyymm,
                iso_code=args.iso,
                market_type=args.market_type,
                include_urls=args.url,
            )
            for table, count in metadata_result["tables_purged"].items():
                metadata_deleted_summary[table] = metadata_deleted_summary.get(table, 0) + count
        
        if args.json:
            print(json.dumps(
                {
                    "months_purged": months_to_purge,
                    "parquet": {
                        "total_files_deleted": total_parquet_deleted,
                        "views_refreshed": views_refreshed,
                    },
                    "metadata": {
                        "tables_purged": metadata_deleted_summary,
                    },
                },
                indent=2,
            ))
        else:
            print("=" * 60)
            if args.purge_month:
                print(f"Purge Month: {args.purge_month}")
            else:
                print(f"Purge Year Range: {start_year}–{end_year}")
            print("=" * 60)
            if args.iso:
                print(f"ISO filter: {args.iso}")
            if args.market_type:
                print(f"Market type filter: {args.market_type}")
            print("\nParquet:")
            print(f"  Total files deleted: {total_parquet_deleted}")
            print(f"  Views refreshed: {views_refreshed}")
            print("\nMetadata:")
            if metadata_deleted_summary:
                for table, count in metadata_deleted_summary.items():
                    print(f"  {table}: {count} rows deleted")
            else:
                print("  No metadata rows matched filters")
    
    return 0


if __name__ == "__main__":
    exit(main())
