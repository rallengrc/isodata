"""
Parquet writer for canonical market data.
"""

from pathlib import Path
from typing import List
from datetime import datetime
import pandas as pd
from canonical.schemas import MarketPriceFact


class ParquetWriter:
    """
    Writes MarketPriceFact objects to Parquet files with partitioning.
    
    Partitioning structure:
    data/parquet/{iso_code}/{market_type}/{year}/{month}/
    """
    
    def __init__(self, base_dir: Path):
        """
        Initialize Parquet writer.
        
        Args:
            base_dir: Base directory for Parquet files
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def write_facts(
        self,
        facts: List[MarketPriceFact],
        iso_code: str,
        market_type: str,
    ) -> List[Path]:
        """
        Write MarketPriceFact objects to Parquet files.
        
        Partitions by year/month for efficient querying.
        
        Args:
            facts: List of MarketPriceFact objects
            iso_code: ISO identifier
            market_type: Market type (ENERGY, CAPACITY, etc.)
        
        Returns:
            List of written file paths
        """
        if not facts:
            return []
        
        # Convert to DataFrame
        df = pd.DataFrame([fact.dict() for fact in facts])
        
        # Convert datetime columns
        for col in ['start_time', 'end_time', 'ingested_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        
        # Group by year/month for partitioning
        df['year'] = df['start_time'].dt.year
        df['month'] = df['start_time'].dt.month
        
        written_files = []
        
        for (year, month), group in df.groupby(['year', 'month']):
            # Create partition directory
            partition_dir = self.base_dir / iso_code / market_type / str(year) / f"{month:02d}"
            partition_dir.mkdir(parents=True, exist_ok=True)
            
            # Remove partitioning columns before writing
            group_to_write = group.drop(columns=['year', 'month'])
            
            # Write Parquet file
            file_path = partition_dir / f"data_{year}_{month:02d}.parquet"
            group_to_write.to_parquet(
                file_path,
                engine='pyarrow',
                compression='snappy',
                index=False,
            )
            
            written_files.append(file_path)
        
        return written_files
    
    def get_partition_path(
        self,
        iso_code: str,
        market_type: str,
        year: int,
        month: int,
    ) -> Path:
        """
        Get partition path for a specific year/month.
        
        Args:
            iso_code: ISO identifier
            market_type: Market type
            year: Year
            month: Month
        
        Returns:
            Partition directory path
        """
        return self.base_dir / iso_code / market_type / str(year) / f"{month:02d}"

