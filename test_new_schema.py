"""
Test script to verify new schema with YYYYMM and zone normalization.
"""

from datetime import datetime
import pytz
from canonical.schemas import MarketPriceFact, MarketType, Product, NodeType
from canonical.normalize import normalize_energy_price
from canonical.validation import DataValidator
from canonical.zone_normalization import normalize_zone_name
from canonical.temporal_utils import datetime_to_yyyymm, validate_yyyymm, get_capability_period

def test_zone_normalization():
    """Test zone name normalization."""
    print("Testing zone normalization...")
    
    test_cases = [
        ("N.Y.C.", "NYC"),
        ("NYC", "NYC"),
        ("LI", "LI"),
        ("Long Island", "LI"),
        ("CAPITL", "CAPITL"),
    ]
    
    for raw, expected in test_cases:
        result = normalize_zone_name(raw)
        assert result == expected, f"Expected {expected}, got {result}"
        print(f"  ✓ '{raw}' -> '{result}'")
    
    print("Zone normalization tests passed!\n")

def test_temporal_utils():
    """Test temporal utility functions."""
    print("Testing temporal utilities...")
    
    # Test datetime_to_yyyymm
    dt = datetime(2024, 1, 15, 10, 30, tzinfo=pytz.UTC)
    yyyymm = datetime_to_yyyymm(dt)
    assert yyyymm == "202401", f"Expected '202401', got {yyyymm}"
    print(f"  ✓ datetime_to_yyyymm: {dt} -> {yyyymm}")
    
    # Test validate_yyyymm
    assert validate_yyyymm("202401") == True
    assert validate_yyyymm("202412") == True
    assert validate_yyyymm("202413") == False  # Invalid month
    assert validate_yyyymm("2024") == False  # Too short
    print("  ✓ validate_yyyymm tests passed")
    
    # Test get_capability_period
    assert get_capability_period("202405") == "SUMMER"  # May
    assert get_capability_period("202410") == "SUMMER"  # October
    assert get_capability_period("202411") == "WINTER"  # November
    assert get_capability_period("202404") == "WINTER"  # April
    print("  ✓ get_capability_period tests passed")
    
    print("Temporal utilities tests passed!\n")

def test_energy_normalization():
    """Test energy price normalization."""
    print("Testing energy price normalization...")
    
    start_time = datetime(2024, 1, 2, 0, 0, tzinfo=pytz.UTC)
    end_time = datetime(2024, 1, 2, 1, 0, tzinfo=pytz.UTC)
    
    fact = normalize_energy_price(
        iso_code="NYISO",
        node_id="NYC",
        node_type="ZONE",
        start_time=start_time,
        end_time=end_time,
        price=50.25,
        product="DA",
        zone="N.Y.C.",  # Test zone normalization
        source_url="https://test.com",
    )
    
    # Verify required fields
    assert fact.auction_month == "202401" or fact.auction_month == "202312", \
        f"Expected auction_month to be 202401 or 202312, got {fact.auction_month}"
    assert fact.delivery_month == "202401", f"Expected '202401', got {fact.delivery_month}"
    assert fact.zone == "NYC", f"Expected normalized zone 'NYC', got {fact.zone}"
    assert fact.zone_normalized == "NYC", f"Expected 'NYC', got {fact.zone_normalized}"
    assert fact.zone_original == "N.Y.C.", f"Expected 'N.Y.C.', got {fact.zone_original}"
    
    print(f"  ✓ Energy fact created:")
    print(f"    - auction_month: {fact.auction_month}")
    print(f"    - delivery_month: {fact.delivery_month}")
    print(f"    - zone: {fact.zone} (normalized from {fact.zone_original})")
    
    print("Energy normalization tests passed!\n")
    return fact

def test_validation():
    """Test data validation."""
    print("Testing data validation...")
    
    validator = DataValidator()
    
    # Create a valid fact
    start_time = datetime(2024, 1, 2, 0, 0, tzinfo=pytz.UTC)
    end_time = datetime(2024, 1, 2, 1, 0, tzinfo=pytz.UTC)
    
    fact = normalize_energy_price(
        iso_code="NYISO",
        node_id="NYC",
        node_type="ZONE",
        start_time=start_time,
        end_time=end_time,
        price=50.25,
        product="DA",
        zone="N.Y.C.",
    )
    
    cleaned_fact, errors = validator.validate_fact(fact)
    
    assert len(errors) == 0, f"Expected no errors, got: {errors}"
    assert cleaned_fact.data_quality_score is not None
    assert cleaned_fact.data_quality_score > 0.9, \
        f"Expected high quality score, got {cleaned_fact.data_quality_score}"
    
    print(f"  ✓ Validation passed (quality score: {cleaned_fact.data_quality_score:.2f})")
    
    # Test invalid fact (negative price)
    invalid_fact = normalize_energy_price(
        iso_code="NYISO",
        node_id="NYC",
        node_type="ZONE",
        start_time=start_time,
        end_time=end_time,
        price=-10.0,  # Invalid
        product="DA",
        zone="NYC",
    )
    
    cleaned_invalid, errors = validator.validate_fact(invalid_fact)
    assert len(errors) > 0, "Expected validation errors for negative price"
    print(f"  ✓ Validation correctly caught errors: {errors}")
    
    print("Validation tests passed!\n")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing New Schema Implementation")
    print("=" * 60)
    print()
    
    try:
        test_zone_normalization()
        test_temporal_utils()
        test_energy_normalization()
        test_validation()
        
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

