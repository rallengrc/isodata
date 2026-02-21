#!/usr/bin/env python3
"""
Prime the iso table in metadata/metadata.db with ISO reference information.

This script seeds the iso table with basic information about ISOs.
It's idempotent: running it multiple times will upsert by iso_code.

Usage (from project root):
  python scripts/prime_iso_registry.py
"""

import sys
import sqlite3
from pathlib import Path

# Add project root to Python path so we can import config module
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))


# ISO reference data - single source of truth
ISO_DATA = {
    "NYISO": {
        "name": "New York Independent System Operator",
        "market_start_year": 1999,
        "notes": "NYISO operates New York's wholesale electricity markets including energy (LBMP) and capacity (ICAP) markets."
    },
    "EIA": {
        "name": "Energy Information Administration",
        "market_start_year": None,
        "notes": "Federal agency providing energy data and statistics. Does not operate markets but provides complementary data."
    },
    # Add more ISOs as they're implemented
    # "PJM": {
    #     "name": "PJM Interconnection",
    #     "market_start_year": 1997,
    #     "notes": "Largest regional transmission organization in the US."
    # },
}


def get_db_path() -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    return base_dir / "metadata" / "metadata.db"


def upsert_iso(conn: sqlite3.Connection, iso_code: str, name: str, market_start_year: int | None, notes: str | None):
    conn.execute(
        """
        INSERT INTO iso (iso_code, name, market_start_year, notes)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(iso_code) DO UPDATE SET
            name = excluded.name,
            market_start_year = excluded.market_start_year,
            notes = excluded.notes
        """,
        (iso_code, name, market_start_year, notes),
    )


def main() -> None:
    db_path = get_db_path()
    print("=" * 80)
    print("Priming iso registry")
    print("=" * 80)
    print(f"Metadata DB: {db_path}")

    if not db_path.exists():
        print("ERROR: metadata.db not found. Run `python run_pipeline.py --init` first.")
        return

    conn = sqlite3.connect(db_path)
    try:
        for iso_code, data in ISO_DATA.items():
            name = data["name"]
            year = data.get("market_start_year")
            notes = data.get("notes")
            print(f"Upserting {iso_code}: {name}")
            upsert_iso(conn, iso_code, name, year, notes)

        conn.commit()
        print(f"\niso registry primed successfully with {len(ISO_DATA)} ISOs.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
