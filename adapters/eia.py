"""
EIA API adapter for complementary electricity data (demand, generation, fuel mix).

NOTE: EIA does NOT provide hourly wholesale electricity prices.
For price data, use direct ISO sources (NYISO, PJM, etc.).
EIA is kept for complementary data like demand and generation.
"""

import os
from typing import List, Optional, Dict
from datetime import datetime
import requests
import pandas as pd
from adapters.base import ISOAdapter
from canonical.schemas import MarketPriceFact


class EIAAdapter(ISOAdapter):
    """
    EIA API adapter for complementary electricity data.
    
    IMPORTANT: EIA does NOT provide hourly wholesale electricity prices.
    This adapter is kept for future use with complementary data:
    - System demand/load
    - Generation by fuel type
    - Transmission flows
    
    For price data, use direct ISO sources (NYISO, PJM, ISO-NE, etc.).
    """
    
    # BASE_URL retained as a default; when available, url_registry should
    # provide the actual base URL via key 'eia_v2_base'.
    BASE_URL = "https://api.eia.gov/v2/electricity/"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize EIA adapter.
        
        Args:
            api_key: EIA API key (optional, will use EIA_API_KEY env var if not provided)
        """
        super().__init__("EIA")
        # Use provided API key, or fall back to environment variable
        self.api_key = api_key or os.getenv("EIA_API_KEY")
        if not self.api_key:
            print("Warning: No EIA API key provided. Set EIA_API_KEY environment variable for higher rate limits.")
        self.session = requests.Session()
    
    def _make_request(self, endpoint: str, params: dict) -> dict:
        """
        Make API request to EIA.
        
        Args:
            endpoint: API endpoint
            params: Request parameters
        
        Returns:
            JSON response
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        if self.api_key:
            params['api_key'] = self.api_key
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def fetch_energy_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        nodes: Optional[List[str]] = None,
        product: str = "DA",
    ) -> List[MarketPriceFact]:
        """
        EIA does NOT provide hourly wholesale electricity prices.
        
        This method returns an empty list. For price data, use direct ISO sources:
        - NYISO: Use NYISOEnergyAdapter
        - PJM: Use PJM adapter (when implemented)
        - Other ISOs: Use their respective adapters
        
        Args:
            start_date: Start date/time (not used)
            end_date: End date/time (not used)
            nodes: Not applicable
            product: Not applicable
        
        Returns:
            Empty list (EIA doesn't provide price data)
        """
        print("WARNING: EIA does not provide hourly wholesale electricity prices.")
        print("         Use direct ISO sources (NYISO, PJM, etc.) for price data.")
        return []
    
    def fetch_capacity_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        nodes: Optional[List[str]] = None,
    ) -> List[MarketPriceFact]:
        """EIA doesn't provide capacity market data."""
        return []
    
    def fetch_nodes(self) -> List[dict]:
        """
        Fetch available regions from EIA.
        
        Returns:
            List of region dictionaries
        """
        # EIA regions (balancing authorities)
        # This is a simplified list - EIA has many more
        regions = [
            {"node_id": "NYISO", "node_type": "ZONE", "zone": "NYISO", "name": "New York ISO"},
            {"node_id": "PJM", "node_type": "ZONE", "zone": "PJM", "name": "PJM Interconnection"},
            {"node_id": "ISO-NE", "node_type": "ZONE", "zone": "ISO-NE", "name": "ISO New England"},
            {"node_id": "MISO", "node_type": "ZONE", "zone": "MISO", "name": "Midcontinent ISO"},
            {"node_id": "CAISO", "node_type": "ZONE", "zone": "CAISO", "name": "California ISO"},
            {"node_id": "ERCOT", "node_type": "ZONE", "zone": "ERCOT", "name": "Electric Reliability Council of Texas"},
            {"node_id": "SPP", "node_type": "ZONE", "zone": "SPP", "name": "Southwest Power Pool"},
        ]
        
        return regions
    
    def fetch_demand(
        self,
        start_date: datetime,
        end_date: datetime,
        region: str = "NYISO",
    ) -> pd.DataFrame:
        """
        Fetch hourly demand/load data from EIA.
        
        This is complementary data (not prices).
        EIA provides system-wide demand in megawatthours.
        
        Args:
            start_date: Start date/time
            end_date: End date/time
            region: Region identifier (NYISO, PJM, etc.)
        
        Returns:
            DataFrame with demand data
        """
        # Placeholder for future implementation
        # EIA API endpoint: /rto/region-data/data/
        # Use facets[type][]="D" for day-ahead demand
        return pd.DataFrame()
    
    def fetch_hourly_generation(
        self,
        start_date: datetime,
        end_date: datetime,
        region: str = "NYISO",
    ) -> Dict:
        """
        Fetch hourly generation data from EIA.
        
        This is a helper method for complementary data (not prices).
        Can be used in future phases for fuel mix analysis.
        
        Args:
            start_date: Start date/time
            end_date: End date/time
            region: Region identifier (NYISO, PJM, etc.)
        
        Returns:
            Dictionary with generation data
        """
        # Placeholder for future implementation
        # EIA API endpoint: /rto/region-data/data/
        # Requires specific series IDs for each region
        return {}

