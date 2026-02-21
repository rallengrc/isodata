"""
NYISO energy price adapter using NYISOToolkit.
"""

from typing import List, Optional
from datetime import datetime, timedelta
import pandas as pd
import pytz
from adapters.base import ISOAdapter
from canonical.schemas import MarketPriceFact
from canonical.normalize import normalize_energy_price
from config.url_constants import NYISO_ENERGY_BASE_URL

try:
    from nyisotoolkit import NYISOData
except ImportError:
    NYISOData = None


class NYISOEnergyAdapter(ISOAdapter):
    """
    NYISO energy price adapter using NYISOToolkit.
    
    Fetches LBMP (Locational Based Marginal Price) data for day-ahead
    and real-time markets.
    """
    
    def __init__(self):
        """Initialize NYISO adapter."""
        super().__init__("NYISO")
        if NYISOData is None:
            raise ImportError(
                "NYISOToolkit not installed. Install with: pip install git+https://github.com/m4rz910/NYISOToolkit#egg=nyisotoolkit"
            )
    
    def fetch_energy_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        nodes: Optional[List[str]] = None,
        product: str = "DA",
    ) -> List[MarketPriceFact]:
        """
        Fetch NYISO LBMP energy prices.
        
        Args:
            start_date: Start date/time
            end_date: End date/time
            nodes: Optional list of specific nodes (zones) to fetch
            product: "DA" for day-ahead, "RT" for real-time
        
        Returns:
            List of normalized MarketPriceFact objects
        """
        facts = []
        
        # NYISOToolkit uses NYISOData with dataset and year
        # Day-ahead: 'lbmp_dam_h' (hourly)
        # Real-time: 'lbmp_rt_5m' (5-minute) or 'lbmp_rt_h' (hourly)
        
        try:
            # Determine dataset based on product
            if product.upper() in ("DA", "DAY_AHEAD", "DAM"):
                dataset = "lbmp_dam_h"  # Day-ahead hourly
            else:
                dataset = "lbmp_rt_5m"  # Real-time 5-minute (can also use lbmp_rt_h for hourly)
            
            # Process year by year (NYISOData requires a year)
            current_year = start_date.year
            end_year = end_date.year
            
            while current_year <= end_year:
                # Create NYISOData instance for this year
                nyiso_data = NYISOData(dataset=dataset, year=current_year)
                
                # Get the data (NYISOData has .df attribute)
                df = nyiso_data.df
                
                if df is not None and not df.empty:
                    # NYISOData returns DataFrame with MultiIndex columns
                    # Format: Index is DatetimeIndex, Columns are ('LBMP ($/MWHr)', 'ZONE_NAME')
                    # Filter by date range (index is already DatetimeIndex with timezone)
                    # Make sure start_date and end_date are timezone-aware for comparison
                    if df.index.tz is not None:
                        # DataFrame has timezone, ensure dates are timezone-aware
                        if start_date.tzinfo is None:
                            start_date = pytz.UTC.localize(start_date)
                        if end_date.tzinfo is None:
                            end_date = pytz.UTC.localize(end_date)
                        # Convert to same timezone as DataFrame index
                        start_date = start_date.astimezone(df.index.tz)
                        end_date = end_date.astimezone(df.index.tz)
                    
                    df = df[(df.index >= start_date) & (df.index <= end_date)]
                    
                    # Extract LBMP columns (first level of MultiIndex)
                    lbmp_cols = [col for col in df.columns if 'LBMP' in str(col[0])]
                    
                    if not lbmp_cols:
                        current_year += 1
                        continue
                    
                    # Convert wide format to long format for processing
                    for timestamp in df.index:
                        for col in lbmp_cols:
                            # col is a tuple like ('LBMP ($/MWHr)', 'NYC')
                            metric_name = col[0]
                            zone_name = col[1]
                            
                            # Filter by nodes if specified
                            if nodes and zone_name not in nodes:
                                continue
                            
                            price = df.loc[timestamp, col]
                            
                            # Skip NaN values
                            if pd.isna(price):
                                continue
                            
                            # Determine end_time based on dataset frequency
                            if dataset == "lbmp_rt_5m":
                                end_time = timestamp + timedelta(minutes=5)
                            else:
                                end_time = timestamp + timedelta(hours=1)
                            
                            fact = normalize_energy_price(
                                iso_code=self.iso_code,
                                node_id=str(zone_name),
                                node_type="ZONE",
                                start_time=timestamp,
                                end_time=end_time,
                                price=float(price),
                                product=product,
                                zone=str(zone_name),
                                source_url=NYISO_ENERGY_BASE_URL,
                            )
                            facts.append(fact)
                
                current_year += 1
        
        except Exception as e:
            print(f"Error fetching NYISO data: {e}")
            raise
        
        return facts
    
    def fetch_energy_prices_raw(
        self,
        start_date: datetime,
        end_date: datetime,
        nodes: Optional[List[str]] = None,
        product: str = "DA",
    ) -> pd.DataFrame:
        """
        Fetch raw NYISO energy prices as DataFrame (before normalization).
        
        Returns:
            DataFrame with MultiIndex columns: ('LBMP ($/MWHr)', 'ZONE_NAME')
        """
        # Determine dataset based on product
        if product.upper() in ("DA", "DAY_AHEAD", "DAM"):
            dataset = "lbmp_dam_h"
        else:
            dataset = "lbmp_rt_5m"
        
        dfs = []
        current_year = start_date.year
        end_year = end_date.year
        
        while current_year <= end_year:
            try:
                nyiso_data = NYISOData(dataset=dataset, year=current_year)
                df = nyiso_data.df
                
                if df is not None and not df.empty:
                    # Filter by date range - make local copies for this iteration
                    start_dt = start_date
                    end_dt = end_date
                    
                    if df.index.tz is not None:
                        # Ensure dates are timezone-aware and in same timezone as DataFrame
                        if start_dt.tzinfo is None:
                            start_dt = pytz.UTC.localize(start_dt)
                        if end_dt.tzinfo is None:
                            end_dt = pytz.UTC.localize(end_dt)
                        start_dt = start_dt.astimezone(df.index.tz)
                        end_dt = end_dt.astimezone(df.index.tz)
                    
                    df = df[(df.index >= start_dt) & (df.index <= end_dt)]
                    
                    if not df.empty:
                        dfs.append(df)
            except Exception as e:
                print(f"Error fetching NYISO raw data for year {current_year}: {e}")
            
            current_year += 1
        
        if dfs:
            return pd.concat(dfs).sort_index()
        return pd.DataFrame()
    
    def fetch_capacity_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        nodes: Optional[List[str]] = None,
    ) -> List[MarketPriceFact]:
        """
        Fetch NYISO ICAP capacity prices.
        
        Note: NYISOToolkit doesn't directly support ICAP.
        This will be implemented in Phase 3 with direct scraping.
        """
        # Phase 3: Implement ICAP scraping
        return []
    
    def fetch_nodes(self) -> List[dict]:
        """
        Fetch available NYISO market nodes/zones.
        
        Returns:
            List of node dictionaries
        """
        # NYISO zones (common ones)
        zones = [
            {"node_id": "NYCA", "node_type": "ZONE", "zone": "NYCA", "name": "New York Control Area"},
            {"node_id": "NYC", "node_type": "ZONE", "zone": "NYC", "name": "New York City"},
            {"node_id": "LI", "node_type": "ZONE", "zone": "LI", "name": "Long Island"},
            {"node_id": "G-J", "node_type": "ZONE", "zone": "G-J", "name": "Genesee-Jamestown"},
            {"node_id": "WEST", "node_type": "ZONE", "zone": "WEST", "name": "West"},
            {"node_id": "CENTRL", "node_type": "ZONE", "zone": "CENTRL", "name": "Central"},
            {"node_id": "NORTH", "node_type": "ZONE", "zone": "NORTH", "name": "North"},
            {"node_id": "MILLWD", "node_type": "ZONE", "zone": "MILLWD", "name": "Millwood"},
            {"node_id": "DUNWOD", "node_type": "ZONE", "zone": "DUNWOD", "name": "Dunwoodie"},
            {"node_id": "CAPITL", "node_type": "ZONE", "zone": "CAPITL", "name": "Capital"},
        ]
        
        return zones

