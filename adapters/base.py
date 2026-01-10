"""
Base adapter interface for ISO data sources.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from canonical.schemas import MarketPriceFact


class ISOAdapter(ABC):
    """
    Base class for ISO data adapters.
    
    All ISO adapters must implement this interface to ensure
    consistent data extraction across different sources.
    """
    
    def __init__(self, iso_code: str):
        """
        Initialize adapter.
        
        Args:
            iso_code: ISO identifier (e.g., "NYISO", "PJM")
        """
        self.iso_code = iso_code.upper()
    
    @abstractmethod
    def fetch_energy_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        nodes: Optional[List[str]] = None,
        product: str = "DA",  # "DA" or "RT"
    ) -> List[MarketPriceFact]:
        """
        Fetch energy prices (LMP/LBMP).
        
        Args:
            start_date: Start date/time
            end_date: End date/time
            nodes: Optional list of specific nodes to fetch
            product: "DA" for day-ahead, "RT" for real-time
        
        Returns:
            List of normalized MarketPriceFact objects
        """
        pass
    
    @abstractmethod
    def fetch_capacity_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        nodes: Optional[List[str]] = None,
    ) -> List[MarketPriceFact]:
        """
        Fetch capacity market prices.
        
        Args:
            start_date: Start date/time
            end_date: End date/time
            nodes: Optional list of specific nodes/zones to fetch
        
        Returns:
            List of normalized MarketPriceFact objects
        """
        pass
    
    @abstractmethod
    def fetch_nodes(self) -> List[dict]:
        """
        Fetch available market nodes.
        
        Returns:
            List of node dictionaries with keys:
            - node_id: Node identifier
            - node_type: NODE, ZONE, or HUB
            - zone: Zone name (if applicable)
            - name: Human-readable name
        """
        pass
    
    def get_iso_code(self) -> str:
        """Get ISO code."""
        return self.iso_code

