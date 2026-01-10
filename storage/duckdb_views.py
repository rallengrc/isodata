"""
DuckDB views over Parquet files.
"""

from pathlib import Path
import duckdb
from typing import Optional


class DuckDBViews:
    """
    Manages DuckDB views over Parquet files.
    """
    
    def __init__(self, db_path: Path, parquet_base: Path):
        """
        Initialize DuckDB views manager.
        
        Args:
            db_path: Path to DuckDB database
            parquet_base: Base directory for Parquet files
        """
        self.db_path = Path(db_path)
        self.parquet_base = Path(parquet_base)
        self.con = duckdb.connect(str(self.db_path))
    
    def create_energy_views(self):
        """Create views for energy price data."""
        # Use glob pattern that works cross-platform
        parquet_path = str(self.parquet_base).replace('\\', '/')
        
        # Create view for all energy prices
        # Note: DuckDB's read_parquet with glob may need adjustment based on actual file structure
        # For now, we'll create a view that can be updated as files are added
        try:
            self.con.execute(f"""
                CREATE OR REPLACE VIEW energy_prices AS
                SELECT *
                FROM read_parquet('{parquet_path}/**/*.parquet')
                WHERE market_type = 'ENERGY'
            """)
        except Exception as e:
            # If glob doesn't work, try alternative approach
            print(f"Warning: Could not create energy_prices view with glob: {e}")
            print("Views will be created when data is available")
        
        # Create view for day-ahead prices
        self.con.execute("""
            CREATE OR REPLACE VIEW energy_prices_da AS
            SELECT *
            FROM energy_prices
            WHERE product = 'ENERGY_DA'
        """)
        
        # Create view for real-time prices
        self.con.execute("""
            CREATE OR REPLACE VIEW energy_prices_rt AS
            SELECT *
            FROM energy_prices
            WHERE product = 'ENERGY_RT'
        """)
        
        # Create view by ISO
        self.con.execute("""
            CREATE OR REPLACE VIEW energy_prices_by_iso AS
            SELECT 
                iso_code,
                node_id,
                zone,
                start_time,
                end_time,
                price,
                unit
            FROM energy_prices
            ORDER BY iso_code, start_time
        """)
    
    def create_capacity_views(self):
        """Create views for capacity price data."""
        parquet_path = str(self.parquet_base).replace('\\', '/')
        
        try:
            self.con.execute(f"""
                CREATE OR REPLACE VIEW capacity_prices AS
                SELECT *
                FROM read_parquet('{parquet_path}/**/*.parquet')
                WHERE market_type = 'CAPACITY'
            """)
        except Exception as e:
            print(f"Warning: Could not create capacity_prices view with glob: {e}")
    
    def create_unified_view(self):
        """Create unified view across all market types."""
        parquet_path = str(self.parquet_base).replace('\\', '/')
        
        try:
            self.con.execute(f"""
                CREATE OR REPLACE VIEW market_prices AS
                SELECT *
                FROM read_parquet('{parquet_path}/**/*.parquet')
            """)
        except Exception as e:
            print(f"Warning: Could not create market_prices view with glob: {e}")
    
    def refresh_views(self):
        """Refresh all views."""
        self.create_energy_views()
        self.create_capacity_views()
        self.create_unified_view()
    
    def query(self, sql: str) -> list:
        """
        Execute SQL query.
        
        Args:
            sql: SQL query string
        
        Returns:
            Query results
        """
        return self.con.execute(sql).fetchall()
    
    def query_df(self, sql: str):
        """
        Execute SQL query and return DataFrame.
        
        Args:
            sql: SQL query string
        
        Returns:
            Pandas DataFrame
        """
        return self.con.execute(sql).df()
    
    def close(self):
        """Close database connection."""
        self.con.close()

