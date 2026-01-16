"""
Tests for canonical schemas and validation.
"""

import unittest
from datetime import datetime
import pytz

from canonical.schemas import MarketPriceFact, MarketType, Product, NodeType
from canonical.normalize import normalize_energy_price, normalize_capacity_price
from canonical.temporal_utils import datetime_to_yyyymm, get_capability_period
from canonical.zone_normalization import normalize_zone_name


class TestSchemas(unittest.TestCase):
    """Test schema validation and normalization."""
    
    def test_energy_price_normalization(self):
        """Test energy price normalization."""
        start_time = datetime(2024, 1, 1, 0, 0, tzinfo=pytz.UTC)
        end_time = datetime(2024, 1, 1, 1, 0, tzinfo=pytz.UTC)
        
        fact = normalize_energy_price(
            iso_code="NYISO",
            node_id="NYC",
            node_type="ZONE",
            start_time=start_time,
            end_time=end_time,
            price=50.25,
            product="DA",
            zone="NYC",
        )
        
        self.assertEqual(fact.iso_code, "NYISO")
        self.assertEqual(fact.market_type, MarketType.ENERGY)
        self.assertEqual(fact.product, Product.ENERGY_DA)
        self.assertEqual(fact.auction_month, "202312")  # Day-ahead: previous month
        self.assertEqual(fact.delivery_month, "202401")
        self.assertEqual(fact.price, 50.25)
        self.assertEqual(fact.unit, "$/MWh")
    
    def test_capacity_price_normalization(self):
        """Test capacity price normalization with new fields."""
        start_time = datetime(2024, 1, 1, 0, 0, tzinfo=pytz.UTC)
        end_time = datetime(2024, 1, 31, 23, 59, tzinfo=pytz.UTC)
        
        fact = normalize_capacity_price(
            iso_code="NYISO",
            node_id="NYC",
            node_type="ZONE",
            start_time=start_time,
            end_time=end_time,
            price=13.04,
            product="MONTHLY",
            zone="NYC",
            auction_time=datetime(2023, 11, 1, tzinfo=pytz.UTC),
            capability_period="WINTER",
            auction_type="MONTHLY",
            awarded_mw=656.9,
            posted_at=datetime(2023, 10, 13, 10, 0, tzinfo=pytz.UTC),
            season_id="702409",
        )
        
        self.assertEqual(fact.iso_code, "NYISO")
        self.assertEqual(fact.market_type, MarketType.CAPACITY)
        self.assertEqual(fact.product, Product.CAPACITY_MONTHLY)
        self.assertEqual(fact.auction_month, "202311")
        self.assertEqual(fact.delivery_month, "202401")
        self.assertEqual(fact.capability_period, "WINTER")
        self.assertEqual(fact.auction_type, "MONTHLY")
        self.assertEqual(fact.price, 13.04)
        self.assertEqual(fact.unit, "$/kW-month")
        self.assertEqual(fact.awarded_mw, 656.9)
        self.assertIsNotNone(fact.posted_at)
        self.assertEqual(fact.season_id, "702409")
    
    def test_zone_normalization(self):
        """Test zone name normalization."""
        self.assertEqual(normalize_zone_name("N.Y.C.", "NYISO"), "NYC")
        self.assertEqual(normalize_zone_name("NYC", "NYISO"), "NYC")
        self.assertEqual(normalize_zone_name("LONGIL", "NYISO"), "LI")
        self.assertEqual(normalize_zone_name("G-J", "NYISO"), "G-J")
    
    def test_temporal_utils(self):
        """Test temporal utility functions."""
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=pytz.UTC)
        self.assertEqual(datetime_to_yyyymm(dt), "202401")
        
        self.assertEqual(get_capability_period("202401"), "WINTER")
        self.assertEqual(get_capability_period("202405"), "SUMMER")
        self.assertEqual(get_capability_period("202411"), "WINTER")


if __name__ == '__main__':
    unittest.main()
