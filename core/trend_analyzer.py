"""Trend analysis with direction and strength detection."""
from typing import Dict, List, Optional, Any, Tuple
import math
import numpy as np
from collections import deque

# Fix imports - absolute imports
from utils.helpers import (
    calculate_ema, calculate_sma, calculate_rsi, calculate_adx,
    calculate_atr, safe_float, clamp
)
from utils.logger import get_logger


class TrendAnalyzer:
    """Analyzes trend direction and strength using multiple indicators."""
    
    def __init__(self, config_path = None):
        """Initialize trend analyzer."""
        self.logger = get_logger("trend_analyzer")
        self.config_path = config_path
        
        # Default parameters
        self.ema_fast = 12
        self.ema_slow = 26
        self.rsi_period = 14
        self.adx_period = 14
        self.strong_threshold = 70
        self.medium_threshold = 40
        self.weak_threshold = 20
    
    def analyze(self, price_data: List[float], 
                high_data: Optional[List[float]] = None,
                low_data: Optional[List[float]] = None,
                close_data: Optional[List[float]] = None) -> Dict[str, Any]:
        """
        Analyze trend direction and strength.
        
        Args:
            price_data: List of prices (typically closing prices)
            high_data: Optional list of high prices
            low_data: Optional list of low prices
            close_data: Optional list of close prices (uses price_data if not provided)
        
        Returns:
            Trend analysis results
        """
        try:
            if not price_data or len(price_data) < self.ema_slow + 1:
                return self._empty_result()
            
            # Use price_data as closes if close_data not provided
            if close_data is None:
                close_data = price_data
            
            # Calculate indicators
            ema_fast_values = calculate_ema(price_data, self.ema_fast)
            ema_slow_values = calculate_ema(price_data, self.ema_slow)
            rsi_values = calculate_rsi(close_data, self.rsi_period)
            
            # Calculate ADX if high/low data available
            adx_values = []
            if high_data and low_data and close_data:
                adx_values = calculate_adx(high_data, low_data, close_data, self.adx_period)
            
            # Get latest values
            current_ema_fast = ema_fast_values[-1] if ema_fast_values else 0
            current_ema_slow = ema_slow_values[-1] if ema_slow_values else 0
            current_rsi = rsi_values[-1] if rsi_values else 50
            current_adx = adx_values[-1] if adx_values else 0
            
            # Calculate slope
            slope = self._calculate_slope(price_data)
            
            # Detect structure (higher highs/lower lows)
            structure = self._detect_structure(price_data)
            
            # Determine trend direction
            direction = self._determine_direction(
                current_ema_fast, current_ema_slow,
                current_rsi, slope, structure
            )
            
            # Determine strength
            strength, strength_label = self._determine_strength(
                current_adx, slope, current_rsi, direction
            )
            
            # Calculate trend score (0-100)
            score = self._calculate_trend_score(
                direction, current_ema_fast, current_ema_slow,
                current_rsi, current_adx, slope
            )
            
            # Calculate confidence
            confidence = self._calculate_confidence(
                direction, strength, current_adx, slope, len(price_data)
            )
            
            # Generate label
            label = self._generate_label(direction, strength_label)
            
            return {
                'direction': direction,
                'strength': strength_label,
                'label': label,
                'score': score,
                'confidence': confidence,
                'ema_fast': current_ema_fast,
                'ema_slow': current_ema_slow,
                'rsi': current_rsi,
                'adx': current_adx,
                'slope_pct': slope,
                'structure': structure,
                'trend_line': self._calculate_trend_line(price_data)
            }
            
        except Exception as e:
            self.logger.error(f"Trend analysis failed: {e}")
            return self._empty_result()
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty trend result."""
        return {
            'direction': 'NEUTRAL',
            'strength': 'NONE',
            'label': 'NEUTRAL',
            'score': 50.0,
            'confidence': 0,
            'ema_fast': 0.0,
            'ema_slow': 0.0,
            'rsi': 50.0,
            'adx': 0.0,
            'slope_pct': 0.0,
            'structure': 'NEUTRAL',
            'trend_line': []
        }
    
    def _calculate_slope(self, prices: List[float], window: int = 20) -> float:
        """Calculate percentage slope using linear regression."""
        if len(prices) < window:
            return 0.0
        
        recent = prices[-window:]
        x = np.arange(window)
        y = np.array(recent)
        
        # Linear regression
        coeffs = np.polyfit(x, y, 1)
        slope = coeffs[0]
        
        # Convert to percentage
        avg_price = np.mean(y)
        if avg_price > 0:
            slope_pct = (slope / avg_price) * 100
            return clamp(slope_pct, -100, 100)
        
        return 0.0
    
    def _detect_structure(self, prices: List[float], window: int = 20) -> str:
        """Detect price structure (higher highs, lower lows, etc.)."""
        if len(prices) < window:
            return 'NEUTRAL'
        
        recent = prices[-window:]
        
        # Find peaks and troughs
        peaks = []
        troughs = []
        
        for i in range(2, len(recent) - 2):
            if recent[i] > recent[i-1] and recent[i] > recent[i-2] and \
               recent[i] > recent[i+1] and recent[i] > recent[i+2]:
                peaks.append(i)
            elif recent[i] < recent[i-1] and recent[i] < recent[i-2] and \
                 recent[i] < recent[i+1] and recent[i] < recent[i+2]:
                troughs.append(i)
        
        if len(peaks) < 2 or len(troughs) < 2:
            return 'NEUTRAL'
        
        # Check for higher highs / higher lows (uptrend)
        higher_highs = all(peaks[i] < peaks[i+1] for i in range(len(peaks)-1))
        higher_lows = all(troughs[i] < troughs[i+1] for i in range(len(troughs)-1))
        
        if higher_highs and higher_lows:
            return 'HIGHER_HIGHS'
        
        # Check for lower highs / lower lows (downtrend)
        lower_highs = all(peaks[i] > peaks[i+1] for i in range(len(peaks)-1))
        lower_lows = all(troughs[i] > troughs[i+1] for i in range(len(troughs)-1))
        
        if lower_highs and lower_lows:
            return 'LOWER_LOWS'
        
        return 'NEUTRAL'
    
    def _determine_direction(self, ema_fast: float, ema_slow: float,
                            rsi: float, slope: float, structure: str) -> str:
        """Determine trend direction."""
        # EMA crossover
        ema_direction = 0
        if ema_fast > ema_slow:
            ema_direction = 1
        elif ema_fast < ema_slow:
            ema_direction = -1
        
        # RSI
        rsi_direction = 0
        if rsi > 55:
            rsi_direction = 1
        elif rsi < 45:
            rsi_direction = -1
        
        # Slope
        slope_direction = 0
        if slope > 0.1:
            slope_direction = 1
        elif slope < -0.1:
            slope_direction = -1
        
        # Structure
        structure_direction = 0
        if 'HIGHER' in structure:
            structure_direction = 1
        elif 'LOWER' in structure:
            structure_direction = -1
        
        # Weighted vote
        score = (ema_direction * 2 + rsi_direction + slope_direction * 1.5 + 
                structure_direction * 1.5)
        
        if score > 0.5:
            return 'UPTREND'
        elif score < -0.5:
            return 'DOWNTREND'
        else:
            return 'NEUTRAL'
    
    def _determine_strength(self, adx: float, slope: float, 
                           rsi: float, direction: str) -> Tuple[str, str]:
        """
        Determine trend strength.
        
        Returns:
            Tuple of (strength_value, strength_label)
        """
        if direction == 'NEUTRAL':
            return 'NONE', 'NONE'
        
        # ADX strength
        if adx >= 70:
            adx_strength = 'STRONG'
            adx_score = 3
        elif adx >= 40:
            adx_strength = 'MEDIUM'
            adx_score = 2
        elif adx >= 20:
            adx_strength = 'WEAK'
            adx_score = 1
        else:
            adx_strength = 'NONE'
            adx_score = 0
        
        # Slope strength (absolute value)
        slope_abs = abs(slope)
        if slope_abs > 2.0:
            slope_strength = 'STRONG'
            slope_score = 3
        elif slope_abs > 1.0:
            slope_strength = 'MEDIUM'
            slope_score = 2
        elif slope_abs > 0.5:
            slope_strength = 'WEAK'
            slope_score = 1
        else:
            slope_strength = 'NONE'
            slope_score = 0
        
        # RSI extremity (overbought/oversold)
        rsi_score = 0
        if direction == 'UPTREND' and rsi > 70:
            rsi_score = 1  # Strong uptrend
        elif direction == 'DOWNTREND' and rsi < 30:
            rsi_score = 1  # Strong downtrend
        
        # Overall score
        total_score = adx_score + slope_score + rsi_score
        
        if total_score >= 6:
            return 'STRONG', 'STRONG'
        elif total_score >= 4:
            return 'MEDIUM', 'MEDIUM'
        elif total_score >= 2:
            return 'WEAK', 'WEAK'
        else:
            return 'NONE', 'NONE'
    
    def _calculate_trend_score(self, direction: str, ema_fast: float,
                              ema_slow: float, rsi: float, adx: float,
                              slope: float) -> float:
        """Calculate overall trend score (0-100)."""
        if direction == 'NEUTRAL':
            return 50.0
        
        # Direction factor
        direction_factor = 1 if direction == 'UPTREND' else -1
        
        # EMA momentum
        ema_momentum = (ema_fast - ema_slow) / ema_slow * 100 if ema_slow > 0 else 0
        ema_score = clamp(ema_momentum * 10, -30, 30)
        
        # RSI score
        rsi_score = (rsi - 50) * 0.5
        
        # ADX contribution
        adx_score = adx * 0.3
        
        # Slope contribution
        slope_score = slope * 5
        
        # Combine
        raw_score = (ema_score + rsi_score + adx_score + slope_score) * 0.5
        
        # Scale to 0-100
        score = 50 + clamp(raw_score, -50, 50)
        
        # Ensure direction matches
        if direction == 'UPTREND' and score < 50:
            score = 50 + (50 - score) / 2
        elif direction == 'DOWNTREND' and score > 50:
            score = 50 - (score - 50) / 2
        
        return clamp(score, 0, 100)
    
    def _calculate_confidence(self, direction: str, strength: str,
                             adx: float, slope: float, data_points: int) -> int:
        """Calculate confidence in trend analysis."""
        if direction == 'NEUTRAL':
            return 50
        
        # ADX confidence
        adx_confidence = min(100, adx * 2)
        
        # Slope confidence
        slope_abs = abs(slope)
        slope_confidence = min(100, slope_abs * 20)
        
        # Data sufficiency
        data_confidence = min(100, data_points / 2)
        
        # Strength adjustment
        strength_multiplier = {
            'STRONG': 1.0,
            'MEDIUM': 0.8,
            'WEAK': 0.6,
            'NONE': 0.3
        }.get(strength, 0.5)
        
        # Weighted average
        confidence = (adx_confidence * 0.4 + slope_confidence * 0.3 + 
                     data_confidence * 0.3) * strength_multiplier
        
        return int(clamp(confidence, 0, 100))
    
    def _generate_label(self, direction: str, strength: str) -> str:
        """Generate a human-readable trend label."""
        if direction == 'NEUTRAL':
            return 'NEUTRAL (sideways)'
        
        if direction == 'UPTREND':
            return f"{strength} UPTREND"
        else:
            return f"{strength} DOWNTREND"
    
    def _calculate_trend_line(self, prices: List[float]) -> List[float]:
        """Calculate a trend line using linear regression."""
        if len(prices) < 20:
            return prices
        
        x = np.arange(len(prices))
        y = np.array(prices)
        
        coeffs = np.polyfit(x, y, 1)
        trend_line = np.polyval(coeffs, x)
        
        return trend_line.tolist()