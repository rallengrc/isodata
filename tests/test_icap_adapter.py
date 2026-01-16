"""
Tests for NYISO ICAP adapter and HTML parsing.
"""

import unittest
from pathlib import Path
from datetime import datetime
import pytz

from adapters.nyiso_capacity import NYISOCapacityAdapter
from canonical.schemas import MarketPriceFact


class TestICAPAdapter(unittest.TestCase):
    """Test ICAP adapter functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.adapter = NYISOCapacityAdapter()
        self.test_html_file = Path(r"C:\Users\rallen\Documents\winter2324.html")
    
    def test_parse_saved_html(self):
        """Test parsing the saved HTML file."""
        if not self.test_html_file.exists():
            self.skipTest(f"Test HTML file not found: {self.test_html_file}")
        
        html_content = self.test_html_file.read_text(encoding='utf-8')
        parsed_data = self.adapter._parse_monthly_auction_html(html_content, "202311")
        
        self.assertIsNotNone(parsed_data, "Should parse HTML successfully")
        self.assertEqual(parsed_data['auction_month'], "202311")
        self.assertEqual(parsed_data['capability_period'], "WINTER")
        self.assertIsNotNone(parsed_data['season_id'])
        self.assertIsNotNone(parsed_data['posted_at'])
        self.assertGreater(len(parsed_data['zones']), 0, "Should find zones")
        
        # Verify NYC zone data
        self.assertIn('NYC', parsed_data['zones'])
        nyc_data = parsed_data['zones']['NYC']
        self.assertIn('202311', nyc_data)
        self.assertAlmostEqual(nyc_data['202311']['price'], 13.04, places=2)
        self.assertAlmostEqual(nyc_data['202311']['awarded_mw'], 656.9, places=1)
    
    def test_fetch_monthly_auction_live(self):
        """Test fetching monthly auction from live NYISO portal."""
        # This test requires network access
        facts = self.adapter._fetch_monthly_auction(
            auction_month="202311",
            season_id=None,
            nodes=None,
        )
        
        self.assertGreater(len(facts), 0, "Should fetch at least some records")
        
        # Verify first fact structure
        fact = facts[0]
        self.assertIsInstance(fact, MarketPriceFact)
        self.assertEqual(fact.iso_code, "NYISO")
        self.assertEqual(fact.market_type, "CAPACITY")
        self.assertEqual(fact.auction_month, "202311")
        self.assertIn(fact.delivery_month, ["202311", "202312", "202401", "202402", "202403", "202404"])
        self.assertEqual(fact.capability_period, "WINTER")
        self.assertIsNotNone(fact.price)
        self.assertIsNotNone(fact.awarded_mw)
        self.assertIsNotNone(fact.posted_at)
        self.assertIsNotNone(fact.season_id)
    
    def test_fetch_capacity_prices(self):
        """Test the main fetch_capacity_prices method."""
        start_date = datetime(2023, 11, 1, tzinfo=pytz.UTC)
        end_date = datetime(2024, 4, 30, tzinfo=pytz.UTC)
        
        facts = self.adapter.fetch_capacity_prices(
            start_date=start_date,
            end_date=end_date,
            nodes=None,
            auction_type="MONTHLY",
        )
        
        self.assertGreater(len(facts), 0, "Should fetch records")
        
        # Verify all facts have correct structure
        for fact in facts:
            self.assertIsInstance(fact, MarketPriceFact)
            self.assertEqual(fact.iso_code, "NYISO")
            self.assertEqual(fact.market_type, "CAPACITY")


if __name__ == '__main__':
    unittest.main()
