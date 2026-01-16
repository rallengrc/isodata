"""
Tests for NYISO energy adapter.
"""

import unittest
from datetime import datetime, timedelta
import pytz

from adapters.nyiso_energy import NYISOEnergyAdapter
from canonical.schemas import MarketPriceFact


class TestEnergyAdapter(unittest.TestCase):
    """Test energy adapter functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.adapter = NYISOEnergyAdapter()
    
    def test_fetch_energy_prices(self):
        """Test fetching energy prices."""
        # Use a recent date range
        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=7)
        
        facts = self.adapter.fetch_energy_prices(
            start_date=start_date,
            end_date=end_date,
            nodes=None,
            product="DA",
        )
        
        # Should fetch some data (if available)
        if len(facts) > 0:
            fact = facts[0]
            self.assertIsInstance(fact, MarketPriceFact)
            self.assertEqual(fact.iso_code, "NYISO")
            self.assertEqual(fact.market_type, "ENERGY")
            self.assertIsNotNone(fact.price)
            self.assertIsNotNone(fact.auction_month)
            self.assertIsNotNone(fact.delivery_month)
    
    def test_fetch_nodes(self):
        """Test fetching available nodes."""
        nodes = self.adapter.fetch_nodes()
        self.assertGreater(len(nodes), 0)
        
        # Check node structure
        node = nodes[0]
        self.assertIn('node_id', node)
        self.assertIn('node_type', node)
        self.assertIn('zone', node)


if __name__ == '__main__':
    unittest.main()
