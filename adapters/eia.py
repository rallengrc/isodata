"""
EIA API adapter for cross-ISO energy data.
"""

from typing import List, Optional
from datetime import datetime, timedelta
import requests
from adapters.base import ISOAdapter
from canonical.schemas import MarketPriceFact
from canonical.normalize import normalize_energy_price


class EIAAdapter(ISOAdapter):
    """
    EIA API adapter for energy data.
    
    EIA provides aggregated hourly electricity operating data from multiple ISOs.
    This is useful for cross-ISO comparisons and standardized data access.
    """
    
    BASE_URL = "https://api.eia.gov/v2/electricity/"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize EIA adapter.
        
        Args:
            api_key: EIA API key (optional but recommended for higher rate limits)
        """
        super().__init__("EIA")
        self.api_key = api_key
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
        Fetch energy prices from EIA.
        
        Note: EIA doesn't directly provide LMP data in the same format as ISOs.
        EIA provides hourly operating data, generation, demand, etc.
        
        For LMP data, we'll need to use ISO-specific adapters.
        This adapter can be used for complementary data like:
        - Hourly generation by fuel type
        - System demand
        - Inter-system power flows
        
        Args:
            start_date: Start date/time
            end_date: End date/time
            nodes: Not applicable for EIA (aggregated data)
            product: "DA" or "RT" (EIA provides actuals, not market prices)
        
        Returns:
            List of normalized MarketPriceFact objects (empty for now)
        """
        # EIA doesn't provide LMP data directly
        # This adapter is reserved for future use with EIA's other datasets
        # For now, return empty list
        # In future phases, we can add:
        # - Generation by fuel type
        # - System demand
        # - Inter-system flows
        
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
    
    def fetch_hourly_generation(
        self,
        start_date: datetime,
        end_date: datetime,
        region: str = "NYISO",
    ) -> dict:
        """
        Fetch hourly generation data from EIA.
        
        This is a helper method for complementary data (not prices).
        Can be used in future phases for fuel mix analysis.
        
        Args:
            start_date: Start date/time
            end_date: End date/time
            region: Region identifier
        
        Returns:
            Dictionary with generation data
        """
        # Placeholder for future implementation
        # EIA API endpoint: /rto/region-data/data/
        # Requires specific series IDs for each region
        return {}

