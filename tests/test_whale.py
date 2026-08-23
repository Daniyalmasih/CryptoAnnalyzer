"""Tests for whale detection."""
import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.whale_detector import WhaleDetector


class TestWhaleDetector(unittest.TestCase):
    """Test whale detector."""
    
    def setUp(self):
        """Set up test data."""
        self.detector = WhaleDetector()
        
        # Sample order book with walls
        self.bids = [
            [100.0, 10.0],
            [99.5, 15.0],
            [99.0, 20.0],
            [98.5, 25.0],
            [98.0, 30.0],
            [97.5, 100.0],  # Bid wall
            [97.0, 5.0],
            [96.5, 8.0],
            [96.0, 200.0],  # Big bid wall
            [95.5, 12.0]
        ]
        
        self.asks = [
            [100.5, 12.0],
            [101.0, 18.0],
            [101.5, 22.0],
            [102.0, 150.0],  # Ask wall
            [102.5, 35.0],
            [103.0, 8.0],
            [103.5, 10.0],
            [104.0, 15.0],
            [104.5, 250.0],  # Big ask wall
            [105.0, 20.0]
        ]
        
        self.order_book = {
            'bids': self.bids,
            'asks': self.asks
        }
        
        # Sample trades with whale trades
        self.trades = [
            {'qty': 1.5, 'price': 100, 'is_buyer_maker': False},
            {'qty': 2.0, 'price': 101, 'is_buyer_maker': True},
            {'qty': 1.2, 'price': 99.5, 'is_buyer_maker': False},
            {'qty': 50.0, 'price': 102, 'is_buyer_maker': False},  # Whale buy
            {'qty': 2.5, 'price': 100.5, 'is_buyer_maker': False},
            {'qty': 60.0, 'price': 99.0, 'is_buyer_maker': True},   # Whale sell
            {'qty': 3.0, 'price': 101.5, 'is_buyer_maker': True}
        ]
    
    def test_basic_detection(self):
        """Test basic whale detection."""
        result = self.detector.detect(self.order_book, self.trades, 100.0)
        
        self.assertTrue(result['detected'])
        self.assertGreater(result['count'], 0)
    
    def test_wall_detection(self):
        """Test wall detection."""
        result = self.detector.detect(self.order_book, None, 100.0)
        
        # Should detect bid walls
        self.assertGreater(len(result['bid_walls']), 0)
        self.assertGreater(len(result['ask_walls']), 0)
        
        # Check wall properties
        if result['bid_walls']:
            wall = result['bid_walls'][0]
            self.assertIn('price', wall)
            self.assertIn('qty', wall)
            self.assertIn('notional', wall)
            self.assertEqual(wall['side'], 'BID')
    
    def test_whale_trade_detection(self):
        """Test whale trade detection."""
        result = self.detector.detect(self.order_book, self.trades, 100.0)
        
        self.assertGreater(len(result['whale_trades']), 0)
        
        # Check trade properties
        trade = result['whale_trades'][0]
        self.assertIn('price', trade)
        self.assertIn('qty', trade)
        self.assertIn('side', trade)
        self.assertIn('notional', trade)
    
    def test_bias_detection(self):
        """Test bias detection."""
        result = self.detector.detect(self.order_book, self.trades, 100.0)
        
        self.assertIn(result['bias'], ['BUY', 'SELL', 'NEUTRAL'])
        self.assertIn(result['strength'], ['WEAK', 'MEDIUM', 'STRONG', 'EXTREME', 'NONE'])
    
    def test_wall_filtering(self):
        """Test wall filtering by notional."""
        # Reduce min_notional to detect more walls
        self.detector.min_notional = 100.0
        
        result = self.detector.detect(self.order_book, None, 100.0)
        
        # Should detect more walls
        self.assertGreater(len(result['bid_walls']) + len(result['ask_walls']), 2)
    
    def test_empty_data(self):
        """Test handling of empty data."""
        result = self.detector.detect({'bids': [], 'asks': []}, [], 0)
        
        self.assertFalse(result['detected'])
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['bias'], 'NEUTRAL')
    
    def test_wall_clustering(self):
        """Test wall clustering."""
        # Create clustered walls
        clustered_bids = [
            [100.0, 10.0],
            [99.9, 15.0],  # Very close to 100.0
            [99.8, 20.0],  # Very close to 100.0
            [98.0, 100.0]  # Wall
        ]
        
        order_book = {
            'bids': clustered_bids,
            'asks': [[101.0, 10.0], [102.0, 20.0]]
        }
        
        result = self.detector.detect(order_book, None, 100.0)
        
        # Should cluster nearby levels
        if result['bid_walls']:
            # The wall at 98.0 should be detected
            wall_prices = [w['price'] for w in result['bid_walls']]
            self.assertTrue(any(price < 98.5 for price in wall_prices))


if __name__ == '__main__':
    unittest.main()