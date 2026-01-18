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
            for i, fact in enumerate(facts):
                try:
                    cleaned_fact, errors, warnings = self.validator.validate_fact(fact)
                    # Only add to validated_facts if there are no errors
                    # Errors indicate data quality issues that should prevent writing
                    if not errors:
                        validated_facts.append(cleaned_fact)
                        # Collect warnings (they don't block writing)
                        all_warnings.extend(warnings)
                    else:
                        # Log errors but don't include the fact
                        all_errors.extend(errors)
                        # Debug: Show first few errors to understand what's failing
                        if len(all_errors) <= 10:
                            print(f"DEBUG: Fact {i} rejected with errors: {errors[:3]}")
                except Exception as e:
                    all_errors.append(f"Validation error for fact: {str(e)}")
                    if len(all_errors) <= 10:
                        print(f"DEBUG: Fact {i} validation exception: {str(e)}")
        else:
            validated_facts = facts
        
        if not validated_facts:
            if len(facts) > 0:
                print(f"WARNING: All {len(facts)} facts were rejected during validation")
                if all_errors:
                    print(f"  First 5 errors: {all_errors[:5]}")
            return {'files': [], 'rows_written': 0, 'errors': all_errors, 'warnings': all_warnings}
        
        # Convert to DataFrame
        df = pd.DataFrame([fact.dict() for fact in validated_facts])
        
        # Convert datetime columns
        for col in ['start_time', 'end_time', 'ingested_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        
        # Partition by delivery_month (YYYYMM format)
        # Extract year and month from delivery_month string
        # Filter out rows with invalid delivery_month (should have been caught by validation, but be safe)
        if 'delivery_month' not in df.columns or df['delivery_month'].isna().any():
            # If delivery_month is missing or has NaN, try to infer from start_time
            if 'start_time' in df.columns:
                df['delivery_month'] = df['start_time'].dt.strftime('%Y%m')
            else:
                # No way to partition - return error
                all_errors.append("Cannot partition: delivery_month is missing and start_time is not available")
                return {'files': [], 'rows_written': 0, 'errors': all_errors, 'warnings': all_warnings}
        
        # Filter out rows with invalid delivery_month format (should be YYYYMM, 6 characters)
        invalid_mask = df['delivery_month'].isna() | (df['delivery_month'].str.len() != 6)
        if invalid_mask.any():
            invalid_count = invalid_mask.sum()
            all_errors.append(f"Skipping {invalid_count} records with invalid delivery_month format")
            df = df[~invalid_mask]
        
        if len(df) == 0:
            return {'files': [], 'rows_written': 0, 'errors': all_errors, 'warnings': all_warnings}
        
        # Extract year and month from delivery_month string
        df['delivery_year'] = df['delivery_month'].str[:4].astype(int)
        df['delivery_month_num'] = df['delivery_month'].str[4:6].astype(int)
        
        written_files = []
        total_rows = 0
        
        # Group by delivery month AND auction_type to avoid overwriting different auction types
        # For ENERGY market, auction_type may be None, so we'll use a default
        if 'auction_type' in df.columns:
            # Check if auction_type has any non-null values
            non_null_count = df['auction_type'].notna().sum()
            
            # If all values are None/NaN, don't include auction_type in groupby
            # This prevents pandas from creating 0 groups when all values are None
            if non_null_count == 0:
                groupby_cols = ['delivery_year', 'delivery_month_num']
            else:
                # Mix of None and non-None - include in groupby
                groupby_cols = ['delivery_year', 'delivery_month_num', 'auction_type']
        else:
            groupby_cols = ['delivery_year', 'delivery_month_num']
        
        for group_key, group in df.groupby(groupby_cols):
            if 'auction_type' in groupby_cols:
                year, month, auction_type = group_key
            else:
                year, month = group_key
                auction_type = None
            
            # Create partition directory
            partition_dir = self.base_dir / iso_code / market_type / str(year) / f"{month:02d}"
            partition_dir.mkdir(parents=True, exist_ok=True)
            
            # Remove partitioning columns before writing
            group_to_write = group.drop(columns=['delivery_year', 'delivery_month_num'])
            if 'auction_type' in groupby_cols and auction_type is not None:
                # Include auction_type in filename to prevent overwrites
                file_path = partition_dir / f"data_{year}_{month:02d}_{auction_type.lower()}.parquet"
            else:
                # For ENERGY or when auction_type is None, use original filename
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

