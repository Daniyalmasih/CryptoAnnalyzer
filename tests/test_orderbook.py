"""Tests for order book analysis."""
import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.orderbook_analyzer import OrderBookAnalyzer


class TestOrderBookAnalyzer(unittest.TestCase):
    """Test order book analyzer."""
    
    def setUp(self):
        """Set up test data."""
        self.analyzer = OrderBookAnalyzer()
        
        # Sample order book data
        self.bids = [
            [100.0, 10.0],
            [99.5, 15.0],
            [99.0, 20.0],
            [98.5, 25.0],
            [98.0, 30.0]
        ]
        self.asks = [
            [100.5, 12.0],
            [101.0, 18.0],
            [101.5, 22.0],
            [102.0, 28.0],
            [102.5, 35.0]
        ]
        self.order_book = {
            'bids': self.bids,
            'asks': self.asks
        }
    
    def test_analyze_basic(self):
        """Test basic analysis."""
        result = self.analyzer.analyze(self.order_book)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['best_bid'], 100.0)
        self.assertEqual(result['best_ask'], 100.5)
        self.assertEqual(result['spread'], 0.5)
        self.assertEqual(result['bid_levels'], 5)
        self.assertEqual(result['ask_levels'], 5)
    
    def test_imbalance_calculation(self):
        """Test imbalance calculation."""
        result = self.analyzer.analyze(self.order_book)
        
        total_bid = sum(qty for _, qty in self.bids)
        total_ask = sum(qty for _, qty in self.asks)
        
        # Bid depth should be higher
        self.assertGreater(result['total_bid_qty'], result['total_ask_qty'])
        self.assertGreater(result['imbalance'], 0)
    
    def test_support_resistance(self):
        """Test support/resistance detection."""
        result = self.analyzer.analyze(self.order_book)
        
        self.assertIsInstance(result['support'], list)
        self.assertIsInstance(result['resistance'], list)
        
        # Should find some levels
        if result['support']:
            self.assertTrue(all(s < result['best_bid'] for s in result['support']))
        
        if result['resistance']:
            self.assertTrue(all(r > result['best_ask'] for r in result['resistance']))
    
    def test_empty_data(self):
        """Test handling of empty data."""
        result = self.analyzer.analyze({'bids': [], 'asks': []})
        
        self.assertEqual(result['best_bid'], 0)
        self.assertEqual(result['best_ask'], 0)
        self.assertEqual(result['spread'], 0)
        self.assertEqual(result['total_bid_qty'], 0)
        self.assertEqual(result['total_ask_qty'], 0)
    
    def test_depth_ranges(self):
        """Test depth range calculation."""
        result = self.analyzer.analyze(self.order_book)
        
        self.assertIn('0.1%', result['depth_ranges'])
        self.assertIn('1.0%', result['depth_ranges'])
        
        # Depth should increase with range
        range_01 = result['depth_ranges']['0.1%']
        range_10 = result['depth_ranges']['1.0%']
        
        self.assertGreaterEqual(range_10['total'], range_01['total'])


if __name__ == '__main__':
    unittest.main()