"""Tests for volume analysis."""
import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.volume_analyzer import VolumeAnalyzer


class TestVolumeAnalyzer(unittest.TestCase):
    """Test volume analyzer."""
    
    def setUp(self):
        """Set up test data."""
        self.analyzer = VolumeAnalyzer()
        
        # Sample volume data
        self.volumes = [100, 120, 110, 130, 115, 125, 140, 135, 120, 150]
        
        # Sample trades
        self.trades = [
            {'qty': 1.5, 'price': 100, 'is_buyer_maker': False},
            {'qty': 2.0, 'price': 101, 'is_buyer_maker': True},
            {'qty': 1.2, 'price': 99.5, 'is_buyer_maker': False},
            {'qty': 3.0, 'price': 102, 'is_buyer_maker': True},
            {'qty': 2.5, 'price': 100.5, 'is_buyer_maker': False}
        ]
    
    def test_basic_analysis(self):
        """Test basic volume analysis."""
        result = self.analyzer.analyze(self.volumes)
        
        self.assertEqual(result['current'], 150)
        self.assertGreater(result['average'], 0)
        self.assertGreater(result['ratio'], 1.0)
    
    def test_volume_status(self):
        """Test volume status labels."""
        # Very high volume
        high_volumes = [100, 100, 100, 100, 300]
        result = self.analyzer.analyze(high_volumes)
        self.assertEqual(result['status'], 'VERY_HIGH')
        
        # Low volume
        low_volumes = [100, 100, 100, 100, 30]
        result = self.analyzer.analyze(low_volumes)
        self.assertEqual(result['status'], 'LOW')
    
    def test_buy_sell_split(self):
        """Test buy/sell volume split."""
        result = self.analyzer.analyze(self.volumes, trades=self.trades)
        
        self.assertGreater(result['buy_volume'], 0)
        self.assertGreater(result['sell_volume'], 0)
        self.assertEqual(result['buy_pct'] + result['sell_pct'], 100)
    
    def test_direction_detection(self):
        """Test volume direction detection."""
        # Buy dominant
        buy_trades = [
            {'qty': 10.0, 'price': 100, 'is_buyer_maker': False},
            {'qty': 8.0, 'price': 101, 'is_buyer_maker': False},
            {'qty': 2.0, 'price': 99.5, 'is_buyer_maker': True}
        ]
        result = self.analyzer.analyze(self.volumes, trades=buy_trades)
        self.assertEqual(result['direction'], 'BUY_DOMINANT')
        
        # Sell dominant
        sell_trades = [
            {'qty': 2.0, 'price': 100, 'is_buyer_maker': False},
            {'qty': 8.0, 'price': 101, 'is_buyer_maker': True},
            {'qty': 10.0, 'price': 99.5, 'is_buyer_maker': True}
        ]
        result = self.analyzer.analyze(self.volumes, trades=sell_trades)
        self.assertEqual(result['direction'], 'SELL_DOMINANT')
    
    def test_spike_detection(self):
        """Test volume spike detection."""
        # No spike
        normal_volumes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
        result = self.analyzer.analyze(normal_volumes)
        self.assertFalse(result['spike'])
        
        # Spike
        spike_volumes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 500]
        result = self.analyzer.analyze(spike_volumes)
        self.assertTrue(result['spike'])
    
    def test_cvd_update(self):
        """Test CVD (Cumulative Volume Delta) update."""
        result = self.analyzer.analyze(self.volumes, trades=self.trades)
        
        # CVD should be tracked
        self.assertIsNotNone(result['cvd'])
    
    def test_tape_analysis(self):
        """Test tape reading analysis."""
        result = self.analyzer.analyze(self.volumes, trades=self.trades)
        
        tape = result.get('tape', {})
        self.assertIn('buy_pct', tape)
        self.assertIn('sell_pct', tape)
        self.assertIn('trades', tape)
        self.assertEqual(tape['trades'], len(self.trades))


if __name__ == '__main__':
    unittest.main()