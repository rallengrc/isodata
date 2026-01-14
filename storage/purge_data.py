"""
Data purge utility to keep DuckDB views and Parquet files in sync.

Provides functions to purge data with different granularity:
1. Purge all data
2. Purge by ISO/provider (e.g., NYISO, PJM)
3. Purge by YYYYMM delivery month
"""

from pathlib import Path
from typing import Optional, List
import shutil
from storage.duckdb_views import DuckDBViews


class DataPurge:
    """
    Utility class for purging Parquet data and refreshing DuckDB views.
    """
    
    def __init__(self, parquet_base: Path, duckdb_path: Path):
        """
        Initialize data purge utility.
        
        Args:
            parquet_base: Base directory for Parquet files
            duckdb_path: Path to DuckDB database
        """
        self.parquet_base = Path(parquet_base)
        self.duckdb_path = Path(duckdb_path)
    
    def purge_all(self, confirm: bool = False) -> dict:
        """
        Purge all Parquet data and refresh DuckDB views.
        
        Args:
            confirm: If False, raises error requiring explicit confirmation
        
        Returns:
            dict with purge results
        """
        if not confirm:
            raise ValueError(
                "purge_all() requires confirm=True. "
                "This will delete ALL Parquet data. Use with caution!"
            )
        
        deleted_files = []
        deleted_dirs = []
        
        # Delete all Parquet files
        for parquet_file in self.parquet_base.rglob("*.parquet"):
            deleted_files.append(str(parquet_file))
            parquet_file.unlink()
        
        # Remove empty directories
        for iso_dir in self.parquet_base.iterdir():
            if iso_dir.is_dir():
                try:
                    shutil.rmtree(iso_dir)
                    deleted_dirs.append(str(iso_dir))
                except Exception as e:
                    print(f"Warning: Could not remove directory {iso_dir}: {e}")
        
        # Refresh DuckDB views
        try:
            views = DuckDBViews(self.duckdb_path, self.parquet_base)
            views.refresh_views()
            views.close()
            views_refreshed = True
        except Exception as e:
            print(f"Warning: Could not refresh DuckDB views: {e}")
            views_refreshed = False
        
        return {
            "status": "success",
            "files_deleted": len(deleted_files),
            "directories_deleted": len(deleted_dirs),
            "views_refreshed": views_refreshed,
        }
    
    def purge_by_iso(self, iso_code: str, confirm: bool = False) -> dict:
        """
        Purge all data for a specific ISO/provider.
        
        Args:
            iso_code: ISO identifier (e.g., "NYISO", "PJM")
            confirm: If False, raises error requiring explicit confirmation
        
        Returns:
            dict with purge results
        """
        if not confirm:
            raise ValueError(
                f"purge_by_iso() requires confirm=True. "
                f"This will delete all data for {iso_code}. Use with caution!"
            )
        
        iso_code = iso_code.upper()
        iso_dir = self.parquet_base / iso_code
        
        if not iso_dir.exists():
            return {
                "status": "no_data",
                "message": f"No data found for {iso_code}",
                "files_deleted": 0,
            }
        
        deleted_files = []
        
        # Delete all Parquet files for this ISO
        for parquet_file in iso_dir.rglob("*.parquet"):
            deleted_files.append(str(parquet_file))
            parquet_file.unlink()
        
        # Remove empty directories
        try:
            shutil.rmtree(iso_dir)
        except Exception as e:
            print(f"Warning: Could not remove directory {iso_dir}: {e}")
        
        # Refresh DuckDB views
        try:
            views = DuckDBViews(self.duckdb_path, self.parquet_base)
            views.refresh_views()
            views.close()
            views_refreshed = True
        except Exception as e:
            print(f"Warning: Could not refresh DuckDB views: {e}")
            views_refreshed = False
        
        return {
            "status": "success",
            "iso_code": iso_code,
            "files_deleted": len(deleted_files),
            "views_refreshed": views_refreshed,
        }
    
    def purge_by_yyyymm(
        self,
        delivery_month: str,
        iso_code: Optional[str] = None,
        market_type: Optional[str] = None,
        confirm: bool = False,
    ) -> dict:
        """
        Purge data for a specific delivery month (YYYYMM).
        
        Args:
            delivery_month: YYYYMM string (e.g., "202401" for January 2024)
            iso_code: Optional ISO filter (e.g., "NYISO"). If None, purges for all ISOs
            market_type: Optional market type filter (e.g., "ENERGY", "CAPACITY"). If None, purges all types
            confirm: If False, raises error requiring explicit confirmation
        
        Returns:
            dict with purge results
        """
        if not confirm:
            raise ValueError(
                f"purge_by_yyyymm() requires confirm=True. "
                f"This will delete data for delivery_month={delivery_month}. Use with caution!"
            )
        
        # Validate YYYYMM format
        if len(delivery_month) != 6 or not delivery_month.isdigit():
            raise ValueError(f"Invalid delivery_month format: {delivery_month}. Must be YYYYMM (e.g., '202401')")
        
        year = int(delivery_month[:4])
        month = int(delivery_month[4:6])
        
        if month < 1 or month > 12:
            raise ValueError(f"Invalid month in delivery_month: {delivery_month}")
        
        deleted_files = []
        
        # Determine which directories to search
        if iso_code:
            iso_codes = [iso_code.upper()]
        else:
            # Search all ISOs
            iso_codes = [d.name for d in self.parquet_base.iterdir() if d.is_dir()]
        
        for iso in iso_codes:
            iso_dir = self.parquet_base / iso
            
            if not iso_dir.exists():
                continue
            
            # Determine which market types to search
            if market_type:
                market_types = [market_type.upper()]
            else:
                market_types = [d.name for d in iso_dir.iterdir() if d.is_dir()]
            
            for market in market_types:
                market_dir = iso_dir / market
                
                if not market_dir.exists():
                    continue
                
                # Look for year/month directory
                year_dir = market_dir / str(year)
                if year_dir.exists():
                    month_dir = year_dir / f"{month:02d}"
                    if month_dir.exists():
                        # Delete all Parquet files in this month directory
                        for parquet_file in month_dir.glob("*.parquet"):
                            deleted_files.append(str(parquet_file))
                            parquet_file.unlink()
                        
                        # Remove month directory if empty
                        try:
                            if not any(month_dir.iterdir()):
                                month_dir.rmdir()
                        except Exception:
                            pass
                        
                        # Remove year directory if empty
                        try:
                            if not any(year_dir.iterdir()):
                                year_dir.rmdir()
                        except Exception:
                            pass
        
        # Refresh DuckDB views
        try:
            views = DuckDBViews(self.duckdb_path, self.parquet_base)
            views.refresh_views()
            views.close()
            views_refreshed = True
        except Exception as e:
            print(f"Warning: Could not refresh DuckDB views: {e}")
            views_refreshed = False
        
        return {
            "status": "success",
            "delivery_month": delivery_month,
            "iso_code": iso_code,
            "market_type": market_type,
            "files_deleted": len(deleted_files),
            "views_refreshed": views_refreshed,
        }
    
    def list_data(self) -> dict:
        """
        List all data currently stored (without deleting anything).
        
        Returns:
            dict with data inventory
        """
        inventory = {
            "isos": {},
            "total_files": 0,
            "total_rows": 0,
        }
        
        for iso_dir in self.parquet_base.iterdir():
            if not iso_dir.is_dir():
                continue
            
            iso_code = iso_dir.name
            iso_info = {
                "market_types": {},
                "total_files": 0,
            }
            
            for market_dir in iso_dir.iterdir():
                if not market_dir.is_dir():
                    continue
                
                market_type = market_dir.name
                market_info = {
                    "years": {},
                    "total_files": 0,
                }
                
                for year_dir in market_dir.iterdir():
                    if not year_dir.is_dir():
                        continue
                    
                    year = year_dir.name
                    year_info = {
                        "months": [],
                        "files": 0,
                    }
                    
                    for month_dir in year_dir.iterdir():
                        if not month_dir.is_dir():
                            continue
                        
                        month = month_dir.name
                        parquet_files = list(month_dir.glob("*.parquet"))
                        
                        if parquet_files:
                            year_info["months"].append({
                                "month": month,
                                "files": len(parquet_files),
                            })
                            year_info["files"] += len(parquet_files)
                            market_info["total_files"] += len(parquet_files)
                            iso_info["total_files"] += len(parquet_files)
                            inventory["total_files"] += len(parquet_files)
                    
                    if year_info["months"]:
                        market_info["years"][year] = year_info
                
                if market_info["years"]:
                    iso_info["market_types"][market_type] = market_info
            
            if iso_info["market_types"]:
                inventory["isos"][iso_code] = iso_info
        
        return inventory


def purge_all(parquet_base: Path, duckdb_path: Path, confirm: bool = False) -> dict:
    """
    Convenience function to purge all data.
    
    Args:
        parquet_base: Base directory for Parquet files
        duckdb_path: Path to DuckDB database
        confirm: Must be True to proceed
    
    Returns:
        dict with purge results
    """
    purger = DataPurge(parquet_base, duckdb_path)
    return purger.purge_all(confirm=confirm)


def purge_by_iso(
    iso_code: str,
    parquet_base: Path,
    duckdb_path: Path,
    confirm: bool = False,
) -> dict:
    """
    Convenience function to purge data for a specific ISO.
    
    Args:
        iso_code: ISO identifier (e.g., "NYISO", "PJM")
        parquet_base: Base directory for Parquet files
        duckdb_path: Path to DuckDB database
        confirm: Must be True to proceed
    
    Returns:
        dict with purge results
    """
    purger = DataPurge(parquet_base, duckdb_path)
    return purger.purge_by_iso(iso_code, confirm=confirm)


def purge_by_yyyymm(
    delivery_month: str,
    parquet_base: Path,
    duckdb_path: Path,
    iso_code: Optional[str] = None,
    market_type: Optional[str] = None,
    confirm: bool = False,
) -> dict:
    """
    Convenience function to purge data for a specific delivery month.
    
    Args:
        delivery_month: YYYYMM string (e.g., "202401")
        parquet_base: Base directory for Parquet files
        duckdb_path: Path to DuckDB database
        iso_code: Optional ISO filter
        market_type: Optional market type filter
        confirm: Must be True to proceed
    
    Returns:
        dict with purge results
    """
    purger = DataPurge(parquet_base, duckdb_path)
    return purger.purge_by_yyyymm(
        delivery_month,
        iso_code=iso_code,
        market_type=market_type,
        confirm=confirm,
    )

