"""Tests for trend analysis."""
import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.trend_analyzer import TrendAnalyzer
import numpy as np


class TestTrendAnalyzer(unittest.TestCase):
    """Test trend analyzer."""
    
    def setUp(self):
        """Set up test data."""
        self.analyzer = TrendAnalyzer()
        
        # Generate test data
        self.uptrend_prices = self._generate_trend(100, 200, 0.5)
        self.downtrend_prices = self._generate_trend(200, 100, -0.5)
        self.sideways_prices = self._generate_trend(150, 150, 0.05)
        
        # Add some noise
        self.uptrend_prices = self._add_noise(self.uptrend_prices, 5)
        self.downtrend_prices = self._add_noise(self.downtrend_prices, 5)
        self.sideways_prices = self._add_noise(self.sideways_prices, 3)
    
    def _generate_trend(self, start: float, end: float, slope: float, 
                        length: int = 100) -> list:
        """Generate a trend line."""
        return [start + i * slope for i in range(length)]
    
    def _add_noise(self, data: list, noise_std: float) -> list:
        """Add random noise to data."""
        noise = np.random.normal(0, noise_std, len(data))
        return [d + n for d, n in zip(data, noise)]
    
    def test_uptrend_detection(self):
        """Test uptrend detection."""
        result = self.analyzer.analyze(self.uptrend_prices)
        
        self.assertEqual(result['direction'], 'UPTREND')
        self.assertIn('UPTREND', result['label'])
        self.assertGreater(result['score'], 50)
        self.assertGreater(result['slope_pct'], 0)
    
    def test_downtrend_detection(self):
        """Test downtrend detection."""
        result = self.analyzer.analyze(self.downtrend_prices)
        
        self.assertEqual(result['direction'], 'DOWNTREND')
        self.assertIn('DOWNTREND', result['label'])
        self.assertLess(result['score'], 50)
        self.assertLess(result['slope_pct'], 0)
    
    def test_sideways_detection(self):
        """Test sideways/neutral detection."""
        result = self.analyzer.analyze(self.sideways_prices)
        
        # Should be NEUTRAL or weakly trending
        self.assertIn(result['direction'], ['NEUTRAL', 'UPTREND', 'DOWNTREND'])
        if result['direction'] != 'NEUTRAL':
            self.assertLess(abs(result['slope_pct']), 1.0)
    
    def test_ema_calculation(self):
        """Test EMA calculation."""
        prices = list(range(1, 101))
        result = self.analyzer.analyze(prices)
        
        self.assertGreater(result['ema_fast'], 0)
        self.assertGreater(result['ema_slow'], 0)
        self.assertLess(result['ema_fast'], max(prices))
        self.assertLess(result['ema_slow'], max(prices))
    
    def test_rsi_bounds(self):
        """Test RSI is within bounds."""
        prices = self.uptrend_prices
        result = self.analyzer.analyze(prices)
        
        self.assertGreaterEqual(result['rsi'], 0)
        self.assertLessEqual(result['rsi'], 100)
    
    def test_confidence_range(self):
        """Test confidence is within bounds."""
        result = self.analyzer.analyze(self.uptrend_prices)
        
        self.assertGreaterEqual(result['confidence'], 0)
        self.assertLessEqual(result['confidence'], 100)


if __name__ == '__main__':
    unittest.main()