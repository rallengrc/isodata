"""
Normalization utilities for converting ISO-specific data to canonical schema.
"""

from typing import List, Dict, Any
from datetime import datetime
from canonical.schemas import MarketPriceFact, MarketType, Product, NodeType


def normalize_energy_price(
    iso_code: str,
    node_id: str,
    node_type: str,
    start_time: datetime,
    end_time: datetime,
    price: float,
    product: str,  # "DA" or "RT"
    zone: str = None,
    source_url: str = None,
) -> MarketPriceFact:
    """
    Normalize energy price data to canonical schema.
    
    Args:
        iso_code: ISO identifier
        node_id: Node identifier
        node_type: Type of node (NODE, ZONE, HUB)
        start_time: Period start
        end_time: Period end
        price: Price value
        product: "DA" or "RT"
        zone: Zone name (optional)
        source_url: Source URL (optional)
    
    Returns:
        Normalized MarketPriceFact
    """
    product_enum = Product.ENERGY_DA if product.upper() in ("DA", "DAY_AHEAD", "DAM") else Product.ENERGY_RT
    
    node_type_enum = NodeType(node_type.upper()) if isinstance(node_type, str) else node_type
    
    return MarketPriceFact(
        iso_code=iso_code.upper(),
        market_type=MarketType.ENERGY,
        product=product_enum,
        node_id=str(node_id),
        node_type=node_type_enum,
        zone=zone,
        start_time=start_time,
        end_time=end_time,
        price=float(price),
        unit="$/MWh",
        source_url=source_url,
    )


def normalize_capacity_price(
    iso_code: str,
    node_id: str,
    node_type: str,
    start_time: datetime,
    end_time: datetime,
    price: float,
    product: str,  # "MONTHLY", "SEASONAL", "ANNUAL"
    zone: str = None,
    auction_id: str = None,
    source_url: str = None,
) -> MarketPriceFact:
    """
    Normalize capacity price data to canonical schema.
    
    Args:
        iso_code: ISO identifier
        node_id: Node identifier
        node_type: Type of node
        start_time: Period start
        end_time: Period end
        price: Price value
        product: "MONTHLY", "SEASONAL", or "ANNUAL"
        zone: Zone name (optional)
        auction_id: Auction identifier (optional)
        source_url: Source URL (optional)
    
    Returns:
        Normalized MarketPriceFact
    """
    product_map = {
        "MONTHLY": Product.CAPACITY_MONTHLY,
        "SEASONAL": Product.CAPACITY_SEASONAL,
        "ANNUAL": Product.CAPACITY_ANNUAL,
    }
    product_enum = product_map.get(product.upper(), Product.CAPACITY_MONTHLY)
    
    node_type_enum = NodeType(node_type.upper()) if isinstance(node_type, str) else node_type
    
    return MarketPriceFact(
        iso_code=iso_code.upper(),
        market_type=MarketType.CAPACITY,
        product=product_enum,
        node_id=str(node_id),
        node_type=node_type_enum,
        zone=zone,
        start_time=start_time,
        end_time=end_time,
        price=float(price),
        unit="$/kW-month",
        auction_id=auction_id,
        source_url=source_url,
    )

