#!/usr/bin/env python3
"""
Prime the url_registry table in metadata/metadata.db with known upstream URLs.

This script is idempotent: running it multiple times will upsert by url_key.

Usage (from project root):
  python scripts/prime_url_registry.py
"""

import sys
import sqlite3
from pathlib import Path

# Add project root to Python path so we can import config module
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from config.url_constants import URL_DEFAULTS


def get_db_path() -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    return base_dir / "metadata" / "metadata.db"


def upsert_url(conn: sqlite3.Connection, url_key: str, url: str, description: str, iso_code: str | None):
    conn.execute(
        """
        INSERT INTO url_registry (url_key, url, description, iso_code, active)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(url_key) DO UPDATE SET
            url = excluded.url,
            description = excluded.description,
            iso_code = excluded.iso_code,
            active = 1,
            updated_at = CURRENT_TIMESTAMP
        """,
        (url_key, url, description, iso_code),
    )


def main() -> None:
    db_path = get_db_path()
    print("=" * 80)
    print("Priming url_registry")
    print("=" * 80)
    print(f"Metadata DB: {db_path}")

    if not db_path.exists():
        print("ERROR: metadata.db not found. Run `python run_pipeline.py --init` first.")
        return

    conn = sqlite3.connect(db_path)
    try:
        for url_key, rec in URL_DEFAULTS.items():
            url = rec["url"]
            desc = rec.get("description", "")
            iso = rec.get("iso_code")
            print(f"Upserting {url_key}: {url}")
            upsert_url(conn, url_key, url, desc, iso)

        conn.commit()
        print("\nurl_registry primed successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

