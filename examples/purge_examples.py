"""
Example usage of data purge utility.

This script demonstrates how to use the purge functions programmatically.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from storage.purge_data import DataPurge, purge_all, purge_by_iso, purge_by_yyyymm
from run_pipeline import DIRS, DUCKDB_DB


def example_list_data():
    """Example: List all data without deleting."""
    print("=" * 60)
    print("Example: List Data")
    print("=" * 60)
    
    purger = DataPurge(DIRS["parquet"], DUCKDB_DB)
    inventory = purger.list_data()
    
    print(f"Total files: {inventory['total_files']}")
    for iso_code, iso_info in inventory["isos"].items():
        print(f"\n{iso_code}: {iso_info['total_files']} files")


def example_purge_by_iso():
    """Example: Purge all NYISO data."""
    print("=" * 60)
    print("Example: Purge by ISO (NYISO)")
    print("=" * 60)
    print("NOTE: This is commented out to prevent accidental deletion.")
    print("Uncomment and set confirm=True to actually run.")
    
    # result = purge_by_iso(
    #     "NYISO",
    #     DIRS["parquet"],
    #     DUCKDB_DB,
    #     confirm=True,  # Must be True to proceed
    # )
    # print(f"Files deleted: {result['files_deleted']}")
    # print(f"Views refreshed: {result['views_refreshed']}")


def example_purge_by_month():
    """Example: Purge January 2024 data."""
    print("=" * 60)
    print("Example: Purge by Month (202401)")
    print("=" * 60)
    print("NOTE: This is commented out to prevent accidental deletion.")
    print("Uncomment and set confirm=True to actually run.")
    
    # result = purge_by_yyyymm(
    #     "202401",
    #     DIRS["parquet"],
    #     DUCKDB_DB,
    #     iso_code="NYISO",  # Optional: filter by ISO
    #     market_type="ENERGY",  # Optional: filter by market type
    #     confirm=True,  # Must be True to proceed
    # )
    # print(f"Files deleted: {result['files_deleted']}")
    # print(f"Views refreshed: {result['views_refreshed']}")


def example_purge_all():
    """Example: Purge all data."""
    print("=" * 60)
    print("Example: Purge All Data")
    print("=" * 60)
    print("NOTE: This is commented out to prevent accidental deletion.")
    print("Uncomment and set confirm=True to actually run.")
    
    # result = purge_all(
    #     DIRS["parquet"],
    #     DUCKDB_DB,
    #     confirm=True,  # Must be True to proceed
    # )
    # print(f"Files deleted: {result['files_deleted']}")
    # print(f"Directories deleted: {result['directories_deleted']}")
    # print(f"Views refreshed: {result['views_refreshed']}")


if __name__ == "__main__":
    example_list_data()
    print("\n")
    example_purge_by_iso()
    print("\n")
    example_purge_by_month()
    print("\n")
    example_purge_all()

