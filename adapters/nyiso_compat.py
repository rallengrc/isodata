"""
NYISOToolkit Compatibility Layer

This module provides adapters to make any ISO data compatible with NYISOToolkit's
analytics and visualization tools (NYISOStat, NYISOVis).

The key is transforming our canonical schema into NYISO's expected DataFrame format:
- MultiIndex columns: ('Metric Name', 'Zone Name')
- DatetimeIndex with timezone
- Wide format (time x zones)
"""

from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime
import pandas as pd
import pytz
import duckdb
from canonical.schemas import MarketType, Product


class ISODataAdapter:
    """
    Adapter to make any ISO data look like NYISOData.
    
    This class transforms data from our canonical schema (Parquet) into
    the format expected by NYISOToolkit's NYISOStat and NYISOVis classes.
    
    Usage:
        # For NYISO (direct compatibility)
        nyiso = ISODataAdapter('NYISO', 'lbmp_dam_h', 2024)
        
        # For other ISOs (transformed to NYISO format)
        pjm = ISODataAdapter('PJM', 'lmp_dam_h', 2024)
        
        # Use with NYISOStat/NYISOVis
        from nyisotoolkit import NYISOStat
        stat = NYISOStat(2024)
        # (would need custom wrapper to use ISODataAdapter)
    """
    
    def __init__(
        self,
        iso_code: str,
        dataset_type: str,
        year: int,
        parquet_base: Optional[Path] = None,
        duckdb_path: Optional[Path] = None,
    ):
        """
        Initialize ISO data adapter.
        
        Args:
            iso_code: ISO identifier (NYISO, PJM, etc.)
            dataset_type: Dataset type ('lbmp_dam_h', 'lmp_dam_h', etc.)
            year: Year of data
            parquet_base: Base directory for Parquet files (defaults to data/parquet)
            duckdb_path: Path to DuckDB database (optional, for faster queries)
        """
        self.iso_code = iso_code.upper()
        self.dataset_type = dataset_type
        self.year = str(year)
        self.parquet_base = parquet_base or Path("data/parquet")
        self.duckdb_path = duckdb_path
        
        # Cache for DataFrame
        self._df = None
        self._frequency = None
        
        # Dataset type mapping (canonical -> NYISO format)
        self.dataset_map = {
            # Energy datasets
            'lbmp_dam_h': ('ENERGY', 'ENERGY_DA'),  # NYISO day-ahead
            'lbmp_rt_5m': ('ENERGY', 'ENERGY_RT'),  # NYISO real-time
            'lmp_dam_h': ('ENERGY', 'ENERGY_DA'),   # Other ISOs day-ahead
            'lmp_rt_5m': ('ENERGY', 'ENERGY_RT'),  # Other ISOs real-time
            # Capacity datasets
            'capacity_monthly': ('CAPACITY', 'CAPACITY_MONTHLY'),  # Monthly capacity auctions
            'capacity_strip': ('CAPACITY', 'CAPACITY_SEASONAL'),  # Strip/seasonal capacity auctions
            'icap_monthly': ('CAPACITY', 'CAPACITY_MONTHLY'),  # Alias for capacity_monthly
            'icap_strip': ('CAPACITY', 'CAPACITY_SEASONAL'),  # Alias for capacity_strip
            # Other datasets
            'load_5m': ('LOAD', None),              # Load data
            'fuel_mix_5m': ('FUEL_MIX', None),      # Fuel mix
        }
    
    @property
    def df(self) -> pd.DataFrame:
        """
        Get DataFrame in NYISO format.
        
        Returns:
            DataFrame with:
            - DatetimeIndex (timezone-aware)
            - MultiIndex columns: ('Metric Name', 'Zone Name')
            - Wide format (time x zones)
        """
        if self._df is None:
            self._df = self._load_and_transform()
        return self._df
    
    @property
    def f(self) -> str:
        """
        Get frequency attribute (like NYISOData).
        
        Returns:
            'h' for hourly, '5min' for 5-minute
        """
        if self._frequency is None:
            # Determine from dataset type
            if '5m' in self.dataset_type or '5min' in self.dataset_type:
                self._frequency = '5min'
            else:
                self._frequency = 'h'
        return self._frequency
    
    def _load_and_transform(self) -> pd.DataFrame:
        """
        Load data from canonical schema and transform to NYISO format.
        
        Returns:
            DataFrame in NYISO format
        """
        # Determine market type and product from dataset
        market_type, product = self.dataset_map.get(
            self.dataset_type,
            ('ENERGY', 'ENERGY_DA')
        )
        
        # Load data from Parquet
        if self.duckdb_path and self.duckdb_path.exists():
            df = self._load_from_duckdb(market_type, product)
        else:
            df = self._load_from_parquet(market_type, product)
        
        if df is None or df.empty:
            # Return empty DataFrame with correct structure
            return pd.DataFrame(
                index=pd.DatetimeIndex([], tz='UTC'),
                columns=pd.MultiIndex.from_tuples([], names=['Metric', 'Zone'])
            )
        
        # Transform to NYISO format
        return self._transform_to_nyiso_format(df, market_type)
    
    def _load_from_duckdb(
        self,
        market_type: str,
        product: Optional[str]
    ) -> pd.DataFrame:
        """Load data from DuckDB."""
        try:
            con = duckdb.connect(str(self.duckdb_path))
            
            # Build query - different for CAPACITY vs ENERGY
            if market_type == 'CAPACITY':
                # For capacity, use delivery_month to filter by year
                query = f"""
                SELECT 
                    iso_code,
                    node_id,
                    zone,
                    delivery_month,
                    price_capacity as price
                FROM market_prices
                WHERE iso_code = '{self.iso_code}'
                  AND market_type = '{market_type}'
                  AND delivery_month LIKE '{self.year}%'
                """
            else:
                # For energy, use start_time
                query = f"""
                SELECT 
                    iso_code,
                    node_id,
                    zone,
                    start_time,
                    price_energy as price
                FROM market_prices
                WHERE iso_code = '{self.iso_code}'
                  AND market_type = '{market_type}'
                  AND EXTRACT(YEAR FROM start_time) = {self.year}
                """
            
            if product:
                query += f" AND product = '{product}'"
            
            if market_type == 'CAPACITY':
                query += " ORDER BY delivery_month, zone"
            else:
                query += " ORDER BY start_time, zone"
            
            df = con.execute(query).df()
            con.close()
            
            if df.empty:
                return None
            
            # Convert start_time to datetime for energy, delivery_month stays as string for capacity
            if market_type != 'CAPACITY' and 'start_time' in df.columns:
                df['start_time'] = pd.to_datetime(df['start_time'])
            
            return df
            
        except Exception as e:
            print(f"Error loading from DuckDB: {e}")
            return self._load_from_parquet(market_type, product)
    
    def _load_from_parquet(
        self,
        market_type: str,
        product: Optional[str]
    ) -> pd.DataFrame:
        """Load data from Parquet files."""
        try:
            # Find Parquet files for this ISO/year
            # For capacity, we need to search across all months since delivery_month spans years
            if market_type == 'CAPACITY':
                # Search in all subdirectories for this ISO/market_type
                parquet_path = self.parquet_base / self.iso_code / market_type
                if not parquet_path.exists():
                    return None
                # Load all parquet files and filter by delivery_month year
                parquet_files = list(parquet_path.glob("**/*.parquet"))
            else:
                parquet_path = self.parquet_base / self.iso_code / market_type / self.year
                if not parquet_path.exists():
                    return None
                parquet_files = list(parquet_path.glob("**/*.parquet"))
            
            if not parquet_files:
                return None
            
            # Read and concatenate
            dfs = []
            for file in parquet_files:
                df = pd.read_parquet(file)
                # Filter by product if specified
                if product and 'product' in df.columns:
                    df = df[df['product'] == product]
                # For capacity, filter by delivery_month year
                if market_type == 'CAPACITY' and 'delivery_month' in df.columns:
                    df = df[df['delivery_month'].str.startswith(self.year)]
                dfs.append(df)
            
            if not dfs:
                return None
            
            df = pd.concat(dfs, ignore_index=True)
            
            # Ensure start_time is datetime (for energy)
            if 'start_time' in df.columns:
                df['start_time'] = pd.to_datetime(df['start_time'])
            
            return df
            
        except Exception as e:
            print(f"Error loading from Parquet: {e}")
            return None
    
    def _transform_to_nyiso_format(
        self,
        df: pd.DataFrame,
        market_type: str
    ) -> pd.DataFrame:
        """
        Transform canonical DataFrame to NYISO format.
        
        NYISO format:
        - Index: DatetimeIndex (timezone-aware, UTC or US/Eastern)
        - Columns: MultiIndex [('Metric Name', 'Zone Name')]
        - Wide format: one row per timestamp, one column per zone
        
        For CAPACITY market type:
        - Uses delivery_month as time index (first day of month)
        - Creates monthly time series compatible with NYISOToolkit
        """
        if df is None or df.empty:
            return pd.DataFrame()
        
        # Special handling for CAPACITY market type
        if market_type == 'CAPACITY':
            return self._transform_capacity_to_nyiso_format(df)
        
        # Standard transformation for ENERGY and other market types
        # Determine metric name based on dataset type
        metric_name = self._get_metric_name(market_type)
        
        # Ensure we have required columns
        # For ENERGY, we need price_energy (aliased as price in query)
        required_cols = ['start_time', 'zone', 'price']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # Use zone if available, otherwise node_id
        if 'zone' in df.columns and df['zone'].notna().any():
            zone_col = 'zone'
        elif 'node_id' in df.columns:
            zone_col = 'node_id'
        else:
            raise ValueError("No zone or node_id column found")
        
        # Create pivot table: time x zones
        pivot_df = df.pivot_table(
            index='start_time',
            columns=zone_col,
            values='price',
            aggfunc='mean'  # In case of duplicates
        )
        
        # Convert index to DatetimeIndex with timezone
        if not isinstance(pivot_df.index, pd.DatetimeIndex):
            pivot_df.index = pd.to_datetime(pivot_df.index)
        
        # Ensure timezone (convert to UTC if not set, then to US/Eastern for NYISO compatibility)
        if pivot_df.index.tz is None:
            pivot_df.index = pivot_df.index.tz_localize('UTC')
        elif pivot_df.index.tz != pytz.UTC:
            pivot_df.index = pivot_df.index.tz_convert('UTC')
        
        # Convert to US/Eastern (NYISO standard)
        pivot_df.index = pivot_df.index.tz_convert('US/Eastern')
        
        # Create MultiIndex columns
        multi_cols = pd.MultiIndex.from_tuples(
            [(metric_name, zone) for zone in pivot_df.columns],
            names=['Metric', 'Zone']
        )
        pivot_df.columns = multi_cols
        
        # Sort by time
        pivot_df = pivot_df.sort_index()
        
        return pivot_df
    
    def _transform_capacity_to_nyiso_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform ICAP capacity data to NYISO format.
        
        Uses delivery_month as time index (first day of month) to create
        monthly time series compatible with NYISOToolkit visualizations.
        
        Args:
            df: DataFrame with capacity data (must have delivery_month column)
        
        Returns:
            DataFrame in NYISO format with monthly time series
        """
        if df is None or df.empty:
            return pd.DataFrame()
        
        # Ensure we have required columns
        required_cols = ['delivery_month', 'zone', 'price']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns for capacity data: {missing}")
        
        # Use zone if available, otherwise node_id
        if 'zone' in df.columns and df['zone'].notna().any():
            zone_col = 'zone'
        elif 'node_id' in df.columns:
            zone_col = 'node_id'
        else:
            raise ValueError("No zone or node_id column found for capacity data")
        
        # Convert delivery_month (YYYYMM string) to datetime (first day of month)
        df['delivery_datetime'] = pd.to_datetime(df['delivery_month'], format='%Y%m')
        
        # Create pivot table: delivery_datetime x zones → price
        pivot_df = df.pivot_table(
            index='delivery_datetime',
            columns=zone_col,
            values='price',
            aggfunc='mean'  # In case of duplicates (shouldn't happen, but safe)
        )
        
        # Set timezone to US/Eastern (NYISO standard)
        pivot_df.index = pivot_df.index.tz_localize('US/Eastern')
        
        # Determine metric name
        metric_name = self._get_metric_name('CAPACITY')
        
        # Create MultiIndex columns
        multi_cols = pd.MultiIndex.from_tuples(
            [(metric_name, zone) for zone in pivot_df.columns],
            names=['Metric', 'Zone']
        )
        pivot_df.columns = multi_cols
        
        # Sort by time
        pivot_df = pivot_df.sort_index()
        
        return pivot_df
    
    def _get_metric_name(self, market_type: str) -> str:
        """Get metric name for MultiIndex column."""
        metric_map = {
            'ENERGY': 'LBMP ($/MWHr)' if self.iso_code == 'NYISO' else 'LMP ($/MWHr)',
            'LOAD': 'Load (MW)',
            'FUEL_MIX': 'Generation (MW)',
            'CAPACITY': 'Capacity Price ($/kW-month)',
        }
        return metric_map.get(market_type, 'Price ($/MWHr)')
    
    def tz_convert(self, tz: str) -> pd.DataFrame:
        """
        Convert timezone (like NYISOData method).
        
        Args:
            tz: Target timezone (e.g., 'US/Eastern', 'UTC')
        
        Returns:
            DataFrame with converted timezone
        """
        df = self.df.copy()
        df.index = df.index.tz_convert(tz)
        return df


def create_iso_data_adapter(
    iso_code: str,
    dataset: str,
    year: int,
    parquet_base: Optional[Path] = None,
    duckdb_path: Optional[Path] = None,
) -> ISODataAdapter:
    """
    Factory function to create ISODataAdapter.
    
    Args:
        iso_code: ISO identifier
        dataset: Dataset name (NYISO format: 'lbmp_dam_h', etc.)
        year: Year
        parquet_base: Base Parquet directory
        duckdb_path: DuckDB database path
    
    Returns:
        ISODataAdapter instance
    """
    return ISODataAdapter(
        iso_code=iso_code,
        dataset_type=dataset,
        year=year,
        parquet_base=parquet_base,
        duckdb_path=duckdb_path,
    )

