"""
Canonical data schemas for power market data.

These schemas normalize data from all ISOs into a unified format.
"""

from datetime import datetime
from typing import Optional, List
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
    zone: Optional[str] = Field(None, description="Zone name if applicable (normalized)")
    
    # Temporal fields - full precision (preserved from source)
    start_time: datetime = Field(..., description="Period start time (exact timestamp)")
    end_time: datetime = Field(..., description="Period end time (exact timestamp)")
    
    # Temporal fields - month-level aggregation (YYYYMM strings)
    auction_month: str = Field(..., description="Auction/market clearing month (YYYYMM format, e.g., '202401')")
    delivery_month: str = Field(..., description="Delivery/application month (YYYYMM format, e.g., '202401')")
    
    # Capacity market specific
    capability_period: Optional[str] = Field(None, description="SUMMER or WINTER for capacity markets")
    auction_type: Optional[str] = Field(None, description="MONTHLY, STRIP, or SPOT for capacity markets")
    
    # Price fields - separate by market type to prevent Power/Energy mixing
    price_energy: Optional[float] = Field(
        None,
        description="Energy price in $/MWh (only for ENERGY market_type)"
    )
    price_capacity: Optional[float] = Field(
        None,
        description="Capacity price in $/kW-month (only for CAPACITY market_type)"
    )
    unit: str = Field(..., description="Price unit metadata ($/MWh, $/kW-month, etc.)")
    
    # Capacity market specific - cleared quantities
    awarded_mw: Optional[float] = Field(None, description="Awarded/cleared quantity in MW (for capacity markets)")
    
    # Capacity market specific - auction metadata
    posted_at: Optional[datetime] = Field(None, description="When auction results were posted/published")
    season_id: Optional[str] = Field(None, description="NYISO season/capability period ID (e.g., '702409')")
    
    # Zone normalization tracking
    zone_normalized: Optional[str] = Field(None, description="Normalized zone name")
    zone_original: Optional[str] = Field(None, description="Original zone name from source")
    
    # Data quality tracking
    data_quality_score: Optional[float] = Field(None, description="Data quality score 0-1")
    validation_errors: Optional[List[str]] = Field(None, description="Validation errors if any")
    
    # Metadata
    auction_id: Optional[str] = Field(None, description="Auction identifier if applicable")
    source_url: Optional[str] = Field(None, description="Source URL")
    ingested_at: datetime = Field(default_factory=datetime.utcnow, description="Ingestion timestamp")
    
    class Config:
        use_enum_values = True

