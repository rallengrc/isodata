"""
ISO Statistics - Extended NYISOStat for Any ISO

This module extends NYISOToolkit's NYISOStat to work with any ISO
through the ISODataAdapter compatibility layer.
"""

from typing import Optional
from pathlib import Path
import pandas as pd
from adapters.nyiso_compat import ISODataAdapter, create_iso_data_adapter


class ISOStat:
    """
    Extended statistics class that works with any ISO.
    
    Uses ISODataAdapter to make any ISO data compatible with
    NYISOToolkit's statistical methods.
    
    Usage:
        # For NYISO
        stat = ISOStat(iso_code='NYISO', year=2024)
        
        # For PJM
        stat = ISOStat(iso_code='PJM', year=2024)
        
        # Get hourly dataset
        df = stat.table_hourly_dataset('lbmp_dam_h')
    """
    
    def __init__(
        self,
        iso_code: str,
        year: int,
        parquet_base: Optional[Path] = None,
        duckdb_path: Optional[Path] = None,
    ):
        """
        Initialize ISO statistics.
        
        Args:
            iso_code: ISO identifier (NYISO, PJM, etc.)
            year: Year of data
            parquet_base: Base Parquet directory
            duckdb_path: DuckDB database path
        """
        self.iso_code = iso_code.upper()
        self.year = str(year)
        self.parquet_base = parquet_base
        self.duckdb_path = duckdb_path
    
    def table_hourly_dataset(self, dataset: str) -> pd.DataFrame:
        """
        Convert dataset from power to energy and resample at hourly frequency.
        
        Based on NYISOStat.table_hourly_dataset but works with any ISO.
        
        Args:
            dataset: Dataset name (e.g., 'lbmp_dam_h', 'load_5m')
        
        Returns:
            DataFrame: Energy table [GWh] at hourly frequency
        """
        # Create adapter
        adapter = create_iso_data_adapter(
            iso_code=self.iso_code,
            dataset=dataset,
            year=int(self.year),
            parquet_base=self.parquet_base,
            duckdb_path=self.duckdb_path,
        )
        
        # Get DataFrame in US/Eastern timezone
        df = adapter.df.tz_convert("US/Eastern")
        
        # Convert power to energy based on frequency
        if adapter.f == "5min":
            # 5-minute data: multiply by 1/12 to get MWh, resample to hourly, sum, convert to GWh
            df = (df * 1 / 12).resample("h").sum() / 1000  # MW->MWh->GWh
        elif adapter.f == "h":
            # Hourly data: already in MWh (assuming), convert to GWh
            df = df / 1000  # MWh->GWh
        else:
            raise ValueError(f"Unsupported frequency: {adapter.f}")
        
        return df
    
    def table_average_day_dataset(self, dataset: str) -> pd.DataFrame:
        """
        Get dataset's average hourly value across all days of year.
        
        Args:
            dataset: Dataset name
        
        Returns:
            DataFrame: Average hourly values
        """
        df = self.table_hourly_dataset(dataset)
        
        # Group by hour of day and average
        df['hour'] = df.index.hour
        avg_df = df.groupby('hour').mean()
        avg_df.index.name = 'Hour'
        
        return avg_df
    
    def table_average_day_load(self) -> pd.DataFrame:
        """
        Get total load's average hourly value across all days of year.
        
        Returns:
            DataFrame: Average hourly load [GWh]
        """
        # Try to get load data
        try:
            df = self.table_hourly_dataset("load_5m")
        except:
            # If load_5m not available, try other load datasets
            try:
                df = self.table_hourly_dataset("load_h")
            except:
                raise ValueError("Load data not available for this ISO")
        
        # Get total load (sum across zones if multiple)
        if isinstance(df.columns, pd.MultiIndex):
            # Sum across all zones
            total_load = df.sum(axis=1)
        else:
            total_load = df.sum(axis=1) if len(df.columns) > 1 else df.iloc[:, 0]
        
        # Group by hour of day and average
        total_load_df = pd.DataFrame(total_load, columns=['Load'])
        total_load_df['hour'] = total_load_df.index.hour
        avg_df = total_load_df.groupby('hour')['Load'].mean().to_frame()
        avg_df.index.name = 'Hour'
        
        return avg_df
    
    def get_price_statistics(self, dataset: str = 'lbmp_dam_h') -> pd.DataFrame:
        """
        Get price statistics by zone.
        
        Args:
            dataset: Dataset name
        
        Returns:
            DataFrame: Statistics (mean, min, max, std) by zone
        """
        adapter = create_iso_data_adapter(
            iso_code=self.iso_code,
            dataset=dataset,
            year=int(self.year),
            parquet_base=self.parquet_base,
            duckdb_path=self.duckdb_path,
        )
        
        df = adapter.df
        
        # Calculate statistics for each zone
        stats = []
        for col in df.columns:
            if isinstance(col, tuple):
                metric, zone = col
            else:
                zone = col
                metric = 'Price'
            
            zone_data = df[col].dropna()
            
            if len(zone_data) > 0:
                stats.append({
                    'Zone': zone,
                    'Metric': metric,
                    'Mean': zone_data.mean(),
                    'Min': zone_data.min(),
                    'Max': zone_data.max(),
                    'Std': zone_data.std(),
                    'Count': len(zone_data),
                })
        
        return pd.DataFrame(stats)


def compare_isos(
    iso_codes: list,
    dataset: str,
    year: int,
    metric: str = 'mean',
) -> pd.DataFrame:
    """
    Compare statistics across multiple ISOs.
    
    Args:
        iso_codes: List of ISO identifiers
        dataset: Dataset name
        year: Year
        metric: Metric to compare ('mean', 'min', 'max', 'std')
    
    Returns:
        DataFrame: Comparison table
    """
    results = []
    
    for iso_code in iso_codes:
        stat = ISOStat(iso_code=iso_code, year=year)
        price_stats = stat.get_price_statistics(dataset)
        
        if not price_stats.empty:
            # Get overall statistic (average across zones)
            overall_stat = getattr(price_stats[metric.capitalize()], metric)()
            results.append({
                'ISO': iso_code,
                f'{metric.capitalize()} Price': overall_stat,
            })
    
    return pd.DataFrame(results)

