"""
Normalization utilities for converting ISO-specific data to canonical schema.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from canonical.schemas import MarketPriceFact, MarketType, Product, NodeType
from canonical.zone_normalization import normalize_zone_name
from canonical.temporal_utils import datetime_to_yyyymm


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
    auction_time: Optional[datetime] = None,
) -> MarketPriceFact:
    """
    Normalize energy price data to canonical schema.
    
    Args:
        iso_code: ISO identifier
        node_id: Node identifier
        node_type: Type of node (NODE, ZONE, HUB)
        start_time: Period start (delivery period)
        end_time: Period end (delivery period)
        price: Price value
        product: "DA" or "RT"
        zone: Zone name (optional, will be normalized)
        source_url: Source URL (optional)
        auction_time: Optional auction/market clearing time (if None, uses start_time)
    
    Returns:
        Normalized MarketPriceFact
    """
    product_enum = Product.ENERGY_DA if product.upper() in ("DA", "DAY_AHEAD", "DAM") else Product.ENERGY_RT
    
    node_type_enum = NodeType(node_type.upper()) if isinstance(node_type, str) else node_type
    
    # Extract YYYYMM months
    # For energy markets, delivery_month is from start_time
    delivery_month = datetime_to_yyyymm(start_time)
    
    # For day-ahead markets, auction typically runs day before delivery
    # For real-time markets, auction and delivery are same hour
    if auction_time:
        auction_month = datetime_to_yyyymm(auction_time)
    elif product_enum == Product.ENERGY_DA:
        # Day-ahead: auction typically runs day before (or same day for same-day clearing)
        # Use start_time - 1 day, but if that's previous month, use start_time month
        auction_dt = start_time - timedelta(days=1)
        auction_month = datetime_to_yyyymm(auction_dt)
        # If auction month is more than 1 month before delivery, use delivery month
        if auction_month < delivery_month:
            # Check if it's just previous month (normal case)
            auction_year = int(auction_month[:4])
            auction_month_num = int(auction_month[4:6])
            delivery_year = int(delivery_month[:4])
            delivery_month_num = int(delivery_month[4:6])
            
            if (delivery_year == auction_year and delivery_month_num - auction_month_num == 1) or \
               (delivery_year == auction_year + 1 and delivery_month_num == 1 and auction_month_num == 12):
                # Normal case: auction previous month
                pass
            else:
                # Use delivery month (same-day clearing)
                auction_month = delivery_month
    else:
        # Real-time: auction and delivery are same
        auction_month = delivery_month
    
    # Normalize zone name
    zone_normalized = None
    zone_original = zone
    if zone:
        zone_normalized = normalize_zone_name(zone, iso_code)
    
    return MarketPriceFact(
        iso_code=iso_code.upper(),
        market_type=MarketType.ENERGY,
        product=product_enum,
        node_id=str(node_id),
        node_type=node_type_enum,
        zone=zone_normalized,  # Use normalized
        start_time=start_time,
        end_time=end_time,
        auction_month=auction_month,
        delivery_month=delivery_month,
        price=float(price),
        unit="$/MWh",
        zone_normalized=zone_normalized,
        zone_original=zone_original,
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
    auction_time: Optional[datetime] = None,
    capability_period: Optional[str] = None,
    auction_type: Optional[str] = None,
    awarded_mw: Optional[float] = None,
    posted_at: Optional[datetime] = None,
    season_id: Optional[str] = None,
) -> MarketPriceFact:
    """
    Normalize capacity price data to canonical schema.
    
    Args:
        iso_code: ISO identifier
        node_id: Node identifier
        node_type: Type of node
        start_time: Period start (delivery period)
        end_time: Period end (delivery period)
        price: Price value
        product: "MONTHLY", "SEASONAL", or "ANNUAL"
        zone: Zone name (optional, will be normalized)
        auction_id: Auction identifier (optional)
        source_url: Source URL (optional)
        auction_time: Auction/market clearing time (if None, uses start_time)
        capability_period: "SUMMER" or "WINTER" (optional, will be inferred if not provided)
        auction_type: "MONTHLY", "STRIP", or "SPOT" (optional)
        awarded_mw: Awarded/cleared quantity in MW (optional)
        posted_at: When auction results were posted (optional)
        season_id: NYISO season/capability period ID (optional)
    
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
    
    # Extract YYYYMM months
    delivery_month = datetime_to_yyyymm(start_time)
    
    if auction_time:
        auction_month = datetime_to_yyyymm(auction_time)
    else:
        # Default to delivery month if not provided
        auction_month = delivery_month
    
    # Infer capability period if not provided
    if not capability_period:
        from canonical.temporal_utils import get_capability_period
        capability_period = get_capability_period(delivery_month)
    
    # Normalize zone name
    zone_normalized = None
    zone_original = zone
    if zone:
        zone_normalized = normalize_zone_name(zone, iso_code)
    
    return MarketPriceFact(
        iso_code=iso_code.upper(),
        market_type=MarketType.CAPACITY,
        product=product_enum,
        node_id=str(node_id),
        node_type=node_type_enum,
        zone=zone_normalized,  # Use normalized
        start_time=start_time,
        end_time=end_time,
        auction_month=auction_month,
        delivery_month=delivery_month,
        price=float(price),
        unit="$/kW-month",
        capability_period=capability_period,
        auction_type=auction_type,
        auction_id=auction_id,
        awarded_mw=awarded_mw,
        posted_at=posted_at,
        season_id=season_id,
        zone_normalized=zone_normalized,
        zone_original=zone_original,
        source_url=source_url,
    )

