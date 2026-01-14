"""
Zone name normalization for consistent data across ISOs.
Handles variations like "N.Y.C." vs "NYC", "Long Island" vs "LI", etc.
"""

from typing import Dict, Optional
import re

# Zone name mapping: raw_name -> normalized_name
ZONE_NORMALIZATION_MAP = {
    # NYISO zones
    "N.Y.C.": "NYC",
    "NYC": "NYC",
    "New York City": "NYC",
    "LONGIL": "LI",
    "LI": "LI",
    "Long Island": "LI",
    "CAPITL": "CAPITL",
    "Capital": "CAPITL",
    "CENTRL": "CENTRL",
    "Central": "CENTRL",
    "WEST": "WEST",
    "West": "WEST",
    "NORTH": "NORTH",
    "North": "NORTH",
    "GENESE": "GENESE",
    "G-J": "G-J",
    "Genesee-Jamestown": "G-J",
    "MILLWD": "MILLWD",
    "Millwood": "MILLWD",
    "DUNWOD": "DUNWOD",
    "Dunwoodie": "DUNWOD",
    "H Q": "HQ",
    "HUD VL": "HUDVL",
    "Hudson Valley": "HUDVL",
    "MHK VL": "MHKVL",
    "Mohawk Valley": "MHKVL",
    "NPX": "NPX",
    "O H": "OH",
    "PJM": "PJM",
    "NYCA": "NYCA",
    "New York Control Area": "NYCA",
}


def normalize_zone_name(zone_name: str, iso_code: str = "NYISO") -> str:
    """
    Normalize zone name to standard form.
    
    Args:
        zone_name: Raw zone name from data source
        iso_code: ISO identifier for ISO-specific mappings
    
    Returns:
        Normalized zone name
    """
    if not zone_name:
        return zone_name
    
    # Clean whitespace and convert to string
    zone_name = str(zone_name).strip()
    
    # Check direct mapping first
    if zone_name in ZONE_NORMALIZATION_MAP:
        return ZONE_NORMALIZATION_MAP[zone_name]
    
    # Try case-insensitive match
    zone_upper = zone_name.upper()
    for raw, normalized in ZONE_NORMALIZATION_MAP.items():
        if raw.upper() == zone_upper:
            return normalized
    
    # If no mapping found, return cleaned version
    # Remove periods, normalize spaces
    cleaned = re.sub(r'\.', '', zone_name)  # Remove periods
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()  # Normalize spaces
    return cleaned.upper() if cleaned else zone_name


def get_zone_aliases(normalized_zone: str) -> list:
    """
    Get all known aliases for a normalized zone name.
    
    Args:
        normalized_zone: Normalized zone name
    
    Returns:
        List of all aliases (including normalized name)
    """
    aliases = [normalized_zone]
    for raw, normalized in ZONE_NORMALIZATION_MAP.items():
        if normalized == normalized_zone and raw != normalized_zone:
            aliases.append(raw)
    return aliases

