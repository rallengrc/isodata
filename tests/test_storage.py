"""
Tests for storage components (ParquetWriter, DuckDB views, purge utility).
"""

import unittest
from pathlib import Path
from datetime import datetime
import pytz
import tempfile
import shutil

from storage.parquet_writer import ParquetWriter
from storage.duckdb_views import DuckDBViews
from storage.purge_data import DataPurge
from canonical.schemas import MarketPriceFact, MarketType, Product, NodeType
from canonical.normalize import normalize_energy_price


class TestStorage(unittest.TestCase):
    """Test storage components."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.parquet_dir = self.temp_dir / "parquet"
        self.duckdb_path = self.temp_dir / "analytics.duckdb"
        
        self.parquet_dir.mkdir(parents=True)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_parquet_writer(self):
        """Test ParquetWriter."""
        writer = ParquetWriter(self.parquet_dir, validate=True)
        
        # Create test facts
        facts = []
        for i in range(5):
            start_time = datetime(2024, 1, 1, i, 0, tzinfo=pytz.UTC)
            end_time = datetime(2024, 1, 1, i + 1, 0, tzinfo=pytz.UTC)
            fact = normalize_energy_price(
                iso_code="NYISO",
                node_id="NYC",
                node_type="ZONE",
                start_time=start_time,
                end_time=end_time,
                price=50.0 + i,
                product="DA",
                zone="NYC",
            )
            facts.append(fact)
        
        # Write facts
        result = writer.write_facts(
            facts=facts,
            iso_code="NYISO",
            market_type="ENERGY",
        )
        
        self.assertEqual(result['rows_written'], 5)
        self.assertGreater(len(result['files']), 0)
        
        # Verify file exists
        parquet_file = result['files'][0]
        self.assertTrue(Path(parquet_file).exists())
    
    def test_duckdb_views(self):
        """Test DuckDB views creation."""
        # First write some data
        writer = ParquetWriter(self.parquet_dir, validate=True)
        facts = []
        start_time = datetime(2024, 1, 1, 0, 0, tzinfo=pytz.UTC)
        end_time = datetime(2024, 1, 1, 1, 0, tzinfo=pytz.UTC)
        fact = normalize_energy_price(
            iso_code="NYISO",
            node_id="NYC",
            node_type="ZONE",
            start_time=start_time,
            end_time=end_time,
            price=50.0,
            product="DA",
            zone="NYC",
        )
        facts.append(fact)
        writer.write_facts(facts=facts, iso_code="NYISO", market_type="ENERGY")
        
        # Create views
        views = DuckDBViews(self.duckdb_path, self.parquet_dir)
        views.create_energy_views()
        views.create_unified_view()
        
        # Query views
        import duckdb
        con = duckdb.connect(str(self.duckdb_path))
        result = con.execute("SELECT COUNT(*) as cnt FROM energy_prices").fetchone()
        self.assertGreater(result[0], 0)
        con.close()
        views.close()
    
    def test_purge_utility(self):
        """Test data purge utility."""
        # Write some data first
        writer = ParquetWriter(self.parquet_dir, validate=True)
        facts = []
        start_time = datetime(2024, 1, 1, 0, 0, tzinfo=pytz.UTC)
        end_time = datetime(2024, 1, 1, 1, 0, tzinfo=pytz.UTC)
        fact = normalize_energy_price(
            iso_code="NYISO",
            node_id="NYC",
            node_type="ZONE",
            start_time=start_time,
            end_time=end_time,
            price=50.0,
            product="DA",
            zone="NYC",
        )
        facts.append(fact)
        writer.write_facts(facts=facts, iso_code="NYISO", market_type="ENERGY")
        
        # Verify data exists
        parquet_files = list(self.parquet_dir.rglob("*.parquet"))
        self.assertGreater(len(parquet_files), 0)
        
        # Purge by ISO
        purger = DataPurge(self.parquet_dir, self.duckdb_path)
        result = purger.purge_by_iso("NYISO", confirm=True)
        
        self.assertEqual(result['status'], 'success')
        self.assertGreater(result['files_deleted'], 0)
        
        # Verify files are gone
        parquet_files_after = list(self.parquet_dir.rglob("*.parquet"))
        self.assertEqual(len(parquet_files_after), 0)


if __name__ == '__main__':
    unittest.main()
