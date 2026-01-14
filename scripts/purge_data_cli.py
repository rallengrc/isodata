"""
Command-line interface for data purge utility.

Usage examples:
    # List all data
    python scripts/purge_data_cli.py --list
    
    # Purge all data (requires --confirm)
    python scripts/purge_data_cli.py --purge-all --confirm
    
    # Purge NYISO data
    python scripts/purge_data_cli.py --purge-iso NYISO --confirm
    
    # Purge January 2024 data
    python scripts/purge_data_cli.py --purge-month 202401 --confirm
    
    # Purge January 2024 data for NYISO only
    python scripts/purge_data_cli.py --purge-month 202401 --iso NYISO --confirm
    
    # Purge January 2024 ENERGY data for NYISO
    python scripts/purge_data_cli.py --purge-month 202401 --iso NYISO --market-type ENERGY --confirm
"""

import argparse
import sys
from pathlib import Path
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from storage.purge_data import DataPurge
from run_pipeline import DIRS, DUCKDB_DB


def main():
    parser = argparse.ArgumentParser(
        description="Purge Parquet data and refresh DuckDB views",
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
        help="Purge all Parquet data",
    )
    action_group.add_argument(
        "--purge-iso",
        type=str,
        metavar="ISO_CODE",
        help="Purge data for a specific ISO (e.g., NYISO, PJM)",
    )
    action_group.add_argument(
        "--purge-month",
        type=str,
        metavar="YYYYMM",
        help="Purge data for a specific delivery month (e.g., 202401)",
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
    
    # Confirmation
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required for all purge operations",
    )
    
    # Output format
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    
    args = parser.parse_args()
    
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
    
    elif args.purge_all:
        if not args.confirm:
            print("ERROR: --purge-all requires --confirm flag")
            print("This will delete ALL Parquet data. Use with caution!")
            return 1
        
        result = purger.purge_all(confirm=True)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("=" * 60)
            print("Purge All Results")
            print("=" * 60)
            print(f"Status: {result['status']}")
            print(f"Files deleted: {result['files_deleted']}")
            print(f"Directories deleted: {result['directories_deleted']}")
            print(f"Views refreshed: {result['views_refreshed']}")
    
    elif args.purge_iso:
        if not args.confirm:
            print(f"ERROR: --purge-iso requires --confirm flag")
            print(f"This will delete all data for {args.purge_iso}. Use with caution!")
            return 1
        
        result = purger.purge_by_iso(args.purge_iso, confirm=True)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("=" * 60)
            print(f"Purge ISO: {args.purge_iso}")
            print("=" * 60)
            print(f"Status: {result['status']}")
            if result['status'] == 'success':
                print(f"Files deleted: {result['files_deleted']}")
                print(f"Views refreshed: {result['views_refreshed']}")
            else:
                print(f"Message: {result.get('message', 'Unknown')}")
    
    elif args.purge_month:
        if not args.confirm:
            print(f"ERROR: --purge-month requires --confirm flag")
            print(f"This will delete data for delivery_month={args.purge_month}. Use with caution!")
            return 1
        
        result = purger.purge_by_yyyymm(
            args.purge_month,
            iso_code=args.iso,
            market_type=args.market_type,
            confirm=True,
        )
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("=" * 60)
            print(f"Purge Month: {args.purge_month}")
            print("=" * 60)
            if args.iso:
                print(f"ISO filter: {args.iso}")
            if args.market_type:
                print(f"Market type filter: {args.market_type}")
            print(f"Status: {result['status']}")
            print(f"Files deleted: {result['files_deleted']}")
            print(f"Views refreshed: {result['views_refreshed']}")
    
    return 0


if __name__ == "__main__":
    exit(main())

