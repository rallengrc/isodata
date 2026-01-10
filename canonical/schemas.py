"""
Canonical data schemas for power market data.

These schemas normalize data from all ISOs into a unified format.
"""

from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


class MarketType(str, Enum):
    """Type of market."""
    ENERGY = "ENERGY"
    CAPACITY = "CAPACITY"
    ANCILLARY = "ANCILLARY"


class Product(str, Enum):
    """Market product type."""
    # Energy products
    ENERGY_DA = "ENERGY_DA"  # Day-ahead energy
    ENERGY_RT = "ENERGY_RT"  # Real-time energy
    
    # Capacity products
    CAPACITY_MONTHLY = "CAPACITY_MONTHLY"
    CAPACITY_SEASONAL = "CAPACITY_SEASONAL"
    CAPACITY_ANNUAL = "CAPACITY_ANNUAL"
    
    # Ancillary services
    ANCILLARY_RESERVE = "ANCILLARY_RESERVE"
    ANCILLARY_REGULATION = "ANCILLARY_REGULATION"


class NodeType(str, Enum):
    """Type of market node."""
    NODE = "NODE"  # Specific pricing node
    ZONE = "ZONE"  # Pricing zone
    HUB = "HUB"  # Trading hub


class MarketPriceFact(BaseModel):
    """
    Canonical market price fact.
    
    This is the unified schema for all ISO market data.
    """
    iso_code: str = Field(..., description="ISO identifier (NYISO, PJM, etc.)")
    market_type: MarketType = Field(..., description="Type of market")
    product: Product = Field(..., description="Market product")
    node_id: str = Field(..., description="Node/zone identifier")
    node_type: NodeType = Field(..., description="Type of node")
    zone: Optional[str] = Field(None, description="Zone name if applicable")
    start_time: datetime = Field(..., description="Period start time")
    end_time: datetime = Field(..., description="Period end time")
    price: float = Field(..., description="Price value")
    unit: str = Field(..., description="Price unit ($/MWh, $/kW-month, etc.)")
    auction_id: Optional[str] = Field(None, description="Auction identifier if applicable")
    source_url: Optional[str] = Field(None, description="Source URL")
    ingested_at: datetime = Field(default_factory=datetime.utcnow, description="Ingestion timestamp")
    
    class Config:
        use_enum_values = True

