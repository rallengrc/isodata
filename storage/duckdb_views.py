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
        # Use union_by_name to handle schema evolution
        try:
            self.con.execute(f"""
                CREATE OR REPLACE VIEW energy_prices AS
                SELECT *
                FROM read_parquet('{parquet_path}/**/*.parquet', union_by_name=true)
                WHERE market_type = 'ENERGY'
            """)
        except Exception as e:
            # Fallback for older DuckDB versions
            print(f"Warning: Could not create energy_prices view with union_by_name: {e}")
            try:
                self.con.execute(f"""
                    CREATE OR REPLACE VIEW energy_prices AS
                    SELECT *
                    FROM read_parquet('{parquet_path}/**/*.parquet')
                    WHERE market_type = 'ENERGY'
                """)
            except Exception as e2:
                print(f"Warning: Could not create energy_prices view: {e2}")
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
        # Use COALESCE to handle both old schema (price) and new schema (price_energy)
        self.con.execute("""
            CREATE OR REPLACE VIEW energy_prices_by_iso AS
            SELECT 
                iso_code,
                node_id,
                zone,
                start_time,
                end_time,
                COALESCE(price_energy, price) as price,
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
                FROM read_parquet('{parquet_path}/**/*.parquet', union_by_name=true)
                WHERE market_type = 'CAPACITY'
            """)
        except Exception as e:
            # Fallback for older DuckDB versions
            print(f"Warning: Could not create capacity_prices view with union_by_name: {e}")
            try:
                self.con.execute(f"""
                    CREATE OR REPLACE VIEW capacity_prices AS
                    SELECT *
                    FROM read_parquet('{parquet_path}/**/*.parquet')
                    WHERE market_type = 'CAPACITY'
                """)
            except Exception as e2:
                print(f"Warning: Could not create capacity_prices view: {e2}")
    
    def create_unified_view(self):
        """Create unified view across all market types."""
        parquet_path = str(self.parquet_base).replace('\\', '/')
        
        try:
            # Use union_by_name to handle schema evolution (new columns in newer files)
            self.con.execute(f"""
                CREATE OR REPLACE VIEW market_prices AS
                SELECT *
                FROM read_parquet('{parquet_path}/**/*.parquet', union_by_name=true)
            """)
        except Exception as e:
            # Fallback for older DuckDB versions that don't support union_by_name
            print(f"Warning: Could not create market_prices view with union_by_name: {e}")
            try:
                self.con.execute(f"""
                    CREATE OR REPLACE VIEW market_prices AS
                    SELECT *
                    FROM read_parquet('{parquet_path}/**/*.parquet')
                """)
            except Exception as e2:
                print(f"Warning: Could not create market_prices view: {e2}")
    
    def update_view_definitions(self):
        """
        Update DuckDB view definitions to match current Parquet file schema.
        
        IMPORTANT: This does NOT delete or modify any Parquet files!
        It only updates the SQL view definitions (queries) that read from Parquet files.
        Your data in data/parquet/ is safe and accumulates over time.
        """
        # Drop all existing views first to handle schema evolution
        views_to_drop = [
            'market_prices',
            'energy_prices',
            'energy_prices_da',
            'energy_prices_rt',
            'energy_prices_by_iso',
            'capacity_prices',
        ]
        
        for view_name in views_to_drop:
            try:
                self.con.execute(f"DROP VIEW IF EXISTS {view_name}")
            except Exception:
                pass  # View might not exist
        
        # Check if any Parquet files exist before creating views
        parquet_files = list(Path(self.parquet_base).rglob("*.parquet"))
        
        if not parquet_files:
            # No files exist - create empty views that won't error
            print("No Parquet files found - creating empty views")
            self._create_empty_views()
        else:
            # Recreate all views from Parquet files
            try:
                self.create_energy_views()
                self.create_capacity_views()
                self.create_unified_view()
                
                # Verify the view actually has data and can be queried
                # Don't check for specific columns - union_by_name handles schema evolution
                try:
                    row_count = self.con.execute("SELECT COUNT(*) FROM market_prices").fetchone()[0]
                    if row_count == 0:
                        print("Warning: View created but contains no data. This may be normal if Parquet files are empty.")
                    else:
                        print(f"✓ View created successfully with {row_count} rows")
                except Exception as e:
                    print(f"Warning: Could not query view: {e}")
                    # Only recreate empty views if there's an actual error querying
                    # Don't recreate just because schema doesn't match expectations
            except Exception as e:
                print(f"Error creating views from Parquet files: {e}")
                print("Creating empty views as fallback...")
                self._create_empty_views()
    
    def refresh_views(self):
        """
        Alias for update_view_definitions() for backward compatibility.
        
        DEPRECATED: Use update_view_definitions() instead.
        This method name is misleading - it doesn't "refresh" data, it updates SQL view definitions.
        Your Parquet files are never touched by this method.
        """
        return self.update_view_definitions()
    
    def _create_empty_views(self):
        """Create empty views when no Parquet files exist."""
        # Create empty views with a known schema to prevent errors
        # These will return no rows but won't error on queries
        
        # First, try to get schema from a sample file if one exists
        # Otherwise, use a minimal schema
        try:
            # Create a minimal empty view structure with all fields from MarketPriceFact schema
            self.con.execute("""
                CREATE OR REPLACE VIEW market_prices AS
                SELECT 
                    CAST(NULL AS VARCHAR) as iso_code,
                    CAST(NULL AS VARCHAR) as market_type,
                    CAST(NULL AS VARCHAR) as product,
                    CAST(NULL AS VARCHAR) as node_id,
                    CAST(NULL AS VARCHAR) as node_type,
                    CAST(NULL AS VARCHAR) as zone,
                    CAST(NULL AS TIMESTAMP) as start_time,
                    CAST(NULL AS TIMESTAMP) as end_time,
                    CAST(NULL AS VARCHAR) as auction_month,
                    CAST(NULL AS VARCHAR) as delivery_month,
                    CAST(NULL AS VARCHAR) as capability_period,
                    CAST(NULL AS VARCHAR) as auction_type,
                    CAST(NULL AS DOUBLE) as price_energy,
                    CAST(NULL AS DOUBLE) as price_capacity,
                    CAST(NULL AS DOUBLE) as price,
                    CAST(NULL AS VARCHAR) as unit,
                    CAST(NULL AS DOUBLE) as awarded_mw,
                    CAST(NULL AS TIMESTAMP) as posted_at,
                    CAST(NULL AS VARCHAR) as season_id,
                    CAST(NULL AS VARCHAR) as zone_normalized,
                    CAST(NULL AS VARCHAR) as zone_original,
                    CAST(NULL AS DOUBLE) as data_quality_score,
                    CAST(NULL AS VARCHAR) as validation_errors,
                    CAST(NULL AS VARCHAR) as auction_id,
                    CAST(NULL AS VARCHAR) as source_url,
                    CAST(NULL AS TIMESTAMP) as ingested_at
                WHERE FALSE
            """)
            
            # Create dependent views
            self.con.execute("""
                CREATE OR REPLACE VIEW energy_prices AS
                SELECT * FROM market_prices WHERE market_type = 'ENERGY'
            """)
            
            self.con.execute("""
                CREATE OR REPLACE VIEW energy_prices_da AS
                SELECT * FROM energy_prices WHERE product = 'ENERGY_DA'
            """)
            
            self.con.execute("""
                CREATE OR REPLACE VIEW energy_prices_rt AS
                SELECT * FROM energy_prices WHERE product = 'ENERGY_RT'
            """)
            
            self.con.execute("""
                CREATE OR REPLACE VIEW energy_prices_by_iso AS
                SELECT 
                    iso_code,
                    node_id,
                    zone,
                    start_time,
                    end_time,
                    COALESCE(price_energy, price) as price,
                    unit
                FROM energy_prices
                ORDER BY iso_code, start_time
            """)
            
            self.con.execute("""
                CREATE OR REPLACE VIEW capacity_prices AS
                SELECT * FROM market_prices WHERE market_type = 'CAPACITY'
            """)
            
        except Exception as e:
            print(f"Warning: Could not create empty views: {e}")
    
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

