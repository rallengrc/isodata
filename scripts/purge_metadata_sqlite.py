#!/usr/bin/env python3
"""
Purge metadata from the SQLite metadata database.

This is useful when you've done a lot of test runs and want to start
fresh with a clean set of ingestion logs and related metadata.

By default this script clears:
- ingestion_log
- data_source
- dataset_version

It does NOT touch:
- url_registry (URL registry - NEVER purged unless --url flag is included)
- Static reference tables (iso, market_node) unless you use --all

Usage (from project root):
  python scripts/purge_metadata_sqlite.py           # purge logs + data sources + versions
  python scripts/purge_metadata_sqlite.py --all     # purge EVERYTHING except URLs (including iso, nodes)
  python scripts/purge_metadata_sqlite.py --all --url  # purge EVERYTHING including URLs
  python scripts/purge_metadata_sqlite.py --logs-only
  python scripts/purge_metadata_sqlite.py --url      # purge only url_registry
  python scripts/purge_metadata_sqlite.py --yes     # skip confirmation
"""

import argparse
import sqlite3
from pathlib import Path
from typing import Optional


def get_db_path() -> Path:
    """Return path to metadata.db relative to project root."""
    # scripts/ -> project root is parent
    base_dir = Path(__file__).resolve().parent.parent
    return base_dir / "metadata" / "metadata.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Purge metadata tables from SQLite metadata.db"
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--logs-only",
        action="store_true",
        help="Purge ingestion_log and data_source tables (run-level metadata)",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Purge ALL metadata tables (including iso and market_node)",
    )

    parser.add_argument(
        "--include-iso",
        action="store_true",
        help="Also purge iso table (normally kept as reference data)",
    )
    parser.add_argument(
        "--include-nodes",
        action="store_true",
        help="Also purge market_node table (normally kept as reference data)",
    )
    parser.add_argument(
        "--url",
        action="store_true",
        help="Also purge url_registry table (URLs are never purged unless this flag is used)",
    )
    parser.add_argument(
        "--iso",
        type=str,
        metavar="ISO_CODE",
        help="Filter by ISO code (only purge metadata for this ISO)",
    )
    parser.add_argument(
        "--dataset-prefix",
        type=str,
        metavar="PREFIX",
        help="Filter by dataset name prefix (e.g., 'capacity_excel_nyiso_' to purge only Excel capacity metadata)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        metavar="DATASET_NAME",
        help="Filter by exact dataset name",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )

    return parser.parse_args()


def purge_tables(
    conn: sqlite3.Connection,
    tables: list[str],
    iso_code: Optional[str] = None,
    dataset_prefix: Optional[str] = None,
    dataset_name: Optional[str] = None,
) -> None:
    """
    Purge tables with optional filters.
    
    Args:
        conn: SQLite connection
        tables: List of table names to purge
        iso_code: Optional ISO filter
        dataset_prefix: Optional dataset name prefix filter
        dataset_name: Optional exact dataset name filter
    """
    cursor = conn.cursor()
    
    for table in tables:
        # Build WHERE clause based on filters
        conditions = []
        params = []
        
        # Apply filters based on table structure
        if iso_code and table in ['ingestion_log', 'data_source', 'url_registry']:
            conditions.append("iso_code = ?")
            params.append(iso_code.upper())
        
        if dataset_prefix and table in ['ingestion_log', 'data_source', 'dataset_version']:
            conditions.append("dataset_name LIKE ?")
            params.append(f"{dataset_prefix}%")
        
        if dataset_name and table in ['ingestion_log', 'data_source', 'dataset_version']:
            conditions.append("dataset_name = ?")
            params.append(dataset_name)
        
        # Build query
        if conditions:
            where_clause = " AND ".join(conditions)
            query = f"DELETE FROM {table} WHERE {where_clause}"
            print(f"Purging table: {table} (filtered: {where_clause})")
            cursor.execute(query, params)
        else:
            # No filters - purge entire table
            print(f"Purging table: {table} (all rows)")
            cursor.execute(f"DELETE FROM {table}")
    
    conn.commit()


def main() -> None:
    args = parse_args()
    db_path = get_db_path()

    print("=" * 80)
    print(f"SQLite metadata purge utility")
    print("=" * 80)
    print(f"Metadata DB: {db_path}")

    if not db_path.exists():
        print(f"ERROR: metadata DB not found at {db_path}")
        return

    # Decide which tables to purge
    if args.all:
        # Purge EVERYTHING except url_registry (unless --url flag is used)
        tables_to_purge = ["ingestion_log", "data_source", "dataset_version", "iso", "market_node"]
    elif args.logs_only:
        # Purge only run-level metadata (logs and data sources)
        tables_to_purge = ["ingestion_log", "data_source"]
    else:
        # Default: purge dynamic/run-level metadata, keep url_registry and reference tables
        tables_to_purge = ["ingestion_log", "data_source", "dataset_version"]
        if args.include_iso:
            tables_to_purge.append("iso")
        if args.include_nodes:
            tables_to_purge.append("market_node")
    
    # Add url_registry ONLY if --url flag is explicitly provided
    if args.url:
        if "url_registry" not in tables_to_purge:
            tables_to_purge.append("url_registry")

    # Show what will be purged
    print("\nThe following tables will be PURGED:")
    for t in tables_to_purge:
        print(f"  - {t}")
    
    # Show filters if any
    filters = []
    if args.iso:
        filters.append(f"ISO={args.iso}")
    if args.dataset_prefix:
        filters.append(f"dataset_name LIKE '{args.dataset_prefix}%'")
    if args.dataset:
        filters.append(f"dataset_name='{args.dataset}'")
    
    if filters:
        print("\nFilters applied:")
        for f in filters:
            print(f"  - {f}")
    else:
        print("\n⚠️  WARNING: All rows will be deleted from these tables!")
    
    if args.url:
        print("\n⚠️  WARNING: url_registry will be purged (--url flag provided)")
    else:
        print("\nℹ️  url_registry will NOT be purged (use --url to include it)")

    if not args.yes:
        confirm = input("\nType 'yes' to confirm purge: ").strip().lower()
        if confirm != "yes":
            print("Aborted. No changes made.")
            return

    conn = sqlite3.connect(db_path)
    try:
        purge_tables(
            conn,
            tables_to_purge,
            iso_code=args.iso,
            dataset_prefix=args.dataset_prefix,
            dataset_name=args.dataset,
        )
        # Optional vacuum to reclaim space
        print("\nRunning VACUUM to compact database...")
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()

    print("\nPurge completed successfully.")
    print("=" * 80)


if __name__ == "__main__":
    main()

