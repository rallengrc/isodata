"""
Data validation and cleaning utilities.
"""

from typing import List, Tuple
from canonical.schemas import MarketPriceFact
from canonical.zone_normalization import normalize_zone_name
from canonical.temporal_utils import validate_yyyymm, get_capability_period


class DataValidator:
    """Validates and cleans MarketPriceFact objects."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_fact(self, fact: MarketPriceFact) -> Tuple[MarketPriceFact, List[str], List[str]]:
        """
        Validate and clean a MarketPriceFact.
        
        Returns:
            (cleaned_fact, list_of_errors, list_of_warnings)
        """
        errors = []
        warnings = []
        fact_dict = fact.dict()
        
        # Normalize zone name
        if fact.zone:
            original_zone = fact.zone
            normalized_zone = normalize_zone_name(fact.zone, fact.iso_code)
            
            # Update fact with normalized zone
            fact_dict['zone_normalized'] = normalized_zone
            fact_dict['zone_original'] = original_zone
            fact_dict['zone'] = normalized_zone  # Use normalized for zone field
            
            if original_zone != normalized_zone:
                warnings.append(f"Zone name normalized: '{original_zone}' -> '{normalized_zone}'")
        
        # Validate YYYYMM format
        if not validate_yyyymm(fact.auction_month):
            errors.append(f"Invalid auction_month format: {fact.auction_month} (must be YYYYMM)")
        
        if not validate_yyyymm(fact.delivery_month):
            errors.append(f"Invalid delivery_month format: {fact.delivery_month} (must be YYYYMM)")
        
        # Validate price fields match market_type
        if fact.market_type == "ENERGY":
            if fact.price_energy is None:
                errors.append("ENERGY market_type requires price_energy field")
            if fact.price_capacity is not None:
                errors.append("ENERGY market_type cannot have price_capacity field")
            # Validate price value
            if fact.price_energy is not None:
                if fact.price_energy < 0:
                    warnings.append(f"Negative energy price: {fact.price_energy} $/MWh (valid but unusual)")
                if fact.price_energy > 10000:
                    warnings.append(f"Unusually high energy price: {fact.price_energy} $/MWh")
        elif fact.market_type == "CAPACITY":
            if fact.price_capacity is None:
                errors.append("CAPACITY market_type requires price_capacity field")
            if fact.price_energy is not None:
                errors.append("CAPACITY market_type cannot have price_energy field")
            # Validate price value
            if fact.price_capacity is not None:
                if fact.price_capacity < 0:
                    warnings.append(f"Negative capacity price: {fact.price_capacity} $/kW-month (valid but unusual)")
                if fact.price_capacity > 100:
                    warnings.append(f"Unusually high capacity price: {fact.price_capacity} $/kW-month")
        else:
            errors.append(f"Unknown market_type: {fact.market_type}")
        
        # Validate timestamps
        if fact.end_time <= fact.start_time:
            errors.append(f"end_time must be after start_time: {fact.start_time} -> {fact.end_time}")
        
        # Validate units match price field type
        if fact.market_type == "ENERGY":
            if fact.price_energy is not None and "$/MWh" not in fact.unit:
                warnings.append(f"Energy market but unit is {fact.unit}, expected $/MWh")
        elif fact.market_type == "CAPACITY":
            if fact.price_capacity is not None and "$/kW-month" not in fact.unit:
                warnings.append(f"Capacity market but unit is {fact.unit}, expected $/kW-month")
        
        # Validate capability period matches delivery month (if provided)
        if fact.capability_period:
            expected_period = get_capability_period(fact.delivery_month)
            if expected_period and expected_period != fact.capability_period:
                warnings.append(
                    f"Capability period mismatch: delivery_month {fact.delivery_month} suggests "
                    f"{expected_period}, but got {fact.capability_period}"
                )
        
        # Validate auction_month vs delivery_month relationship
        # For energy markets, auction_month should be <= delivery_month (same or previous month)
        # For capacity markets, auction_month can be before delivery_month (forward capacity)
        if fact.market_type == "ENERGY":
            if fact.auction_month > fact.delivery_month:
                # Allow if within same year and close months (e.g., Dec auction for Jan delivery)
                auction_year = int(fact.auction_month[:4])
                delivery_year = int(fact.delivery_month[:4])
                auction_month_num = int(fact.auction_month[4:6])
                delivery_month_num = int(fact.delivery_month[4:6])
                
                if delivery_year > auction_year + 1:
                    errors.append(
                        f"Energy auction_month {fact.auction_month} is too far before "
                        f"delivery_month {fact.delivery_month}"
                    )
                elif delivery_year == auction_year + 1 and delivery_month_num > 1:
                    errors.append(
                        f"Energy auction_month {fact.auction_month} is too far before "
                        f"delivery_month {fact.delivery_month}"
                    )
                elif delivery_year == auction_year and delivery_month_num - auction_month_num > 1:
                    warnings.append(
                        f"Energy auction_month {fact.auction_month} is more than 1 month "
                        f"before delivery_month {fact.delivery_month}"
                    )
        
        # Calculate data quality score
        quality_score = 1.0
        if errors:
            quality_score -= len(errors) * 0.2
        if warnings:
            quality_score -= len(warnings) * 0.05
        quality_score = max(0.0, quality_score)
        
        fact_dict['data_quality_score'] = quality_score
        fact_dict['validation_errors'] = errors if errors else None
        
        # Recreate fact with updates
        cleaned_fact = MarketPriceFact(**fact_dict)
        
        return cleaned_fact, errors, warnings

