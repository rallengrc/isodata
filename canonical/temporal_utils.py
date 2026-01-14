"""
Temporal utilities for YYYYMM month format and capability periods.
"""

from datetime import datetime
from typing import List, Optional
import pytz


def datetime_to_yyyymm(dt: datetime) -> str:
    """
    Convert datetime to YYYYMM string format.
    
    Args:
        dt: Datetime object (timezone-aware or naive)
    
    Returns:
        YYYYMM string (e.g., "202401" for January 2024)
    """
    if dt is None:
        raise ValueError("datetime cannot be None")
    
    return dt.strftime("%Y%m")


def yyyymm_to_datetime(yyyymm: str, day: int = 1, hour: int = 0, minute: int = 0, tz=pytz.UTC) -> datetime:
    """
    Convert YYYYMM string to datetime.
    
    Args:
        yyyymm: YYYYMM string (e.g., "202401")
        day: Day of month (default: 1)
        hour: Hour (default: 0)
        minute: Minute (default: 0)
        tz: Timezone (default: UTC)
    
    Returns:
        Datetime object
    """
    if len(yyyymm) != 6:
        raise ValueError(f"YYYYMM must be 6 digits, got: {yyyymm}")
    
    year = int(yyyymm[:4])
    month = int(yyyymm[4:6])
    
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month in YYYYMM: {yyyymm}")
    
    dt = datetime(year, month, day, hour, minute)
    if tz:
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        else:
            dt = dt.astimezone(tz)
    
    return dt


def get_capability_period(delivery_month: str) -> Optional[str]:
    """
    Determine capability period (SUMMER or WINTER) from delivery month.
    
    Summer: May (05) through October (10)
    Winter: November (11) through April (04)
    
    Args:
        delivery_month: YYYYMM string
    
    Returns:
        "SUMMER", "WINTER", or None if not applicable
    """
    if len(delivery_month) != 6:
        return None
    
    month = int(delivery_month[4:6])
    
    if month >= 5 and month <= 10:
        return "SUMMER"
    elif month == 11 or month == 12 or month <= 4:
        return "WINTER"
    
    return None


def get_delivery_months_for_strip(auction_month: str, capability_period: str) -> List[str]:
    """
    Get all delivery months covered by a strip auction.
    
    Args:
        auction_month: YYYYMM when auction ran
        capability_period: "SUMMER" or "WINTER"
    
    Returns:
        List of YYYYMM strings for all months in the capability period
    """
    if len(auction_month) != 6:
        raise ValueError(f"Invalid auction_month format: {auction_month}")
    
    year = int(auction_month[:4])
    months = []
    
    if capability_period == "SUMMER":
        # May (05) through October (10)
        for month in range(5, 11):
            months.append(f"{year}{month:02d}")
    elif capability_period == "WINTER":
        # November (11) through April (04) - crosses year boundary
        # November and December of auction year
        for month in range(11, 13):
            months.append(f"{year}{month:02d}")
        # January through April of following year
        for month in range(1, 5):
            months.append(f"{year + 1}{month:02d}")
    else:
        raise ValueError(f"Invalid capability_period: {capability_period}")
    
    return months


def validate_yyyymm(yyyymm: str) -> bool:
    """
    Validate YYYYMM format.
    
    Args:
        yyyymm: String to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(yyyymm, str) or len(yyyymm) != 6:
        return False
    
    try:
        year = int(yyyymm[:4])
        month = int(yyyymm[4:6])
        if month < 1 or month > 12:
            return False
        if year < 2000 or year > 2100:  # Reasonable bounds
            return False
        return True
    except (ValueError, IndexError):
        return False

