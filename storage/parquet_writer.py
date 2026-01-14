"""
Parquet writer for canonical market data.
"""

from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd
from canonical.schemas import MarketPriceFact
from canonical.validation import DataValidator


class ParquetWriter:
    """
    Writes MarketPriceFact objects to Parquet files with partitioning.
    
    Partitioning structure:
    data/parquet/{iso_code}/{market_type}/{year}/{month}/
    
    Partitions by delivery_month (YYYYMM) for efficient querying by delivery period.
    """
    
    def __init__(self, base_dir: Path, validate: bool = True):
        """
        Initialize Parquet writer.
        
        Args:
            base_dir: Base directory for Parquet files
            validate: Whether to validate facts before writing
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.validator = DataValidator() if validate else None
    
    def write_facts(
        self,
        facts: List[MarketPriceFact],
        iso_code: str,
        market_type: str,
    ) -> Dict:
        """
        Write MarketPriceFact objects to Parquet files with validation.
        
        Partitions by delivery_month (YYYYMM) for efficient querying.
        
        Args:
            facts: List of MarketPriceFact objects
            iso_code: ISO identifier
            market_type: Market type (ENERGY, CAPACITY, etc.)
        
        Returns:
            dict with 'files', 'rows_written', 'errors', 'warnings'
        """
        if not facts:
            return {'files': [], 'rows_written': 0, 'errors': [], 'warnings': []}
        
        validated_facts = []
        all_errors = []
        all_warnings = []
        
        # Validate and clean each fact
        if self.validator:
            for fact in facts:
                try:
                    cleaned_fact, errors = self.validator.validate_fact(fact)
                    validated_facts.append(cleaned_fact)
                    all_errors.extend(errors)
                    # Warnings are logged but don't block writing
                except Exception as e:
                    all_errors.append(f"Validation error for fact: {str(e)}")
        else:
            validated_facts = facts
        
        if not validated_facts:
            return {'files': [], 'rows_written': 0, 'errors': all_errors, 'warnings': all_warnings}
        
        # Convert to DataFrame
        df = pd.DataFrame([fact.dict() for fact in validated_facts])
        
        # Convert datetime columns
        for col in ['start_time', 'end_time', 'ingested_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        
        # Partition by delivery_month (YYYYMM format)
        # Extract year and month from delivery_month string
        df['delivery_year'] = df['delivery_month'].str[:4].astype(int)
        df['delivery_month_num'] = df['delivery_month'].str[4:6].astype(int)
        
        written_files = []
        total_rows = 0
        
        for (year, month), group in df.groupby(['delivery_year', 'delivery_month_num']):
            # Create partition directory
            partition_dir = self.base_dir / iso_code / market_type / str(year) / f"{month:02d}"
            partition_dir.mkdir(parents=True, exist_ok=True)
            
            # Remove partitioning columns before writing
            group_to_write = group.drop(columns=['delivery_year', 'delivery_month_num'])
            
            # Write Parquet file
            file_path = partition_dir / f"data_{year}_{month:02d}.parquet"
            group_to_write.to_parquet(
                file_path,
                engine='pyarrow',
                compression='snappy',
                index=False,
            )
            
            written_files.append(file_path)
            total_rows += len(group_to_write)
        
        return {
            'files': written_files,
            'rows_written': total_rows,
            'errors': all_errors,
            'warnings': all_warnings,
        }
    
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
    
    def get_partition_path_from_yyyymm(
        self,
        iso_code: str,
        market_type: str,
        delivery_month: str,
    ) -> Path:
        """
        Get partition path from YYYYMM string.
        
        Args:
            iso_code: ISO identifier
            market_type: Market type
            delivery_month: YYYYMM string (e.g., "202401")
        
        Returns:
            Partition directory path
        """
        if len(delivery_month) != 6:
            raise ValueError(f"Invalid delivery_month format: {delivery_month} (must be YYYYMM)")
        year = int(delivery_month[:4])
        month = int(delivery_month[4:6])
        return self.get_partition_path(iso_code, market_type, year, month)

