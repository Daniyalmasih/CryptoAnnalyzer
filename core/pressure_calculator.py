"""Calculate buying vs selling pressure from order book and trade data."""
from typing import Dict, List, Optional, Any, Tuple
import math
import numpy as np

# Fix imports - absolute imports
from utils.helpers import safe_float, clamp, bar_string
from utils.logger import get_logger


class PressureCalculator:
    """Calculates buying/selling pressure from order book and tape data."""
    
    def __init__(self, config_path = None):
        """Initialize pressure calculator."""
        self.logger = get_logger("pressure_calculator")
        self.config_path = config_path
    
    def calculate_pressure(self, order_book: Dict[str, Any], 
                          trades: Optional[List[Dict]] = None,
                          price: float = 0.0) -> Dict[str, Any]:
        """
        Calculate buying/selling pressure and price prediction.
        
        Args:
            order_book: Order book data with 'bids' and 'asks'
            trades: Optional list of recent trades
            price: Current price (if known, otherwise uses mid price)
        
        Returns:
            Pressure analysis with predictions
        """
        try:
            bids = order_book.get('bids', [])
            asks = order_book.get('asks', [])
            
            if not bids or not asks:
                return self._empty_result()
            
            # Calculate mid price
            best_bid = safe_float(bids[0][0]) if bids else 0
            best_ask = safe_float(asks[0][0]) if asks else 0
            mid_price = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0
            
            if price <= 0:
                price = mid_price
            
            if price <= 0:
                return self._empty_result()
            
            # Calculate weighted pressure across multiple ranges
            pressure_ranges = self._calculate_weighted_pressure(bids, asks, price)
            
            # Calculate overall pressure
            overall_pressure = self._calculate_overall_pressure(pressure_ranges)
            
            # Calculate confidence
            confidence = self._calculate_confidence(pressure_ranges, order_book)
            
            # Determine predicted direction
            direction, predicted_price, reason = self._predict_direction(
                pressure_ranges, overall_pressure, order_book, price
            )
            
            return {
                'buying_pressure': overall_pressure['buy'],
                'selling_pressure': overall_pressure['sell'],
                'pressure_ratio': overall_pressure['ratio'],
                'pressure_ranges': pressure_ranges,
                'direction': direction,
                'predicted_price': predicted_price,
                'confidence': confidence,
                'reason': reason,
                'imbalance': overall_pressure['imbalance'],
                'weighted_mid': overall_pressure['weighted_mid']
            }
            
        except Exception as e:
            self.logger.error(f"Pressure calculation failed: {e}")
            return self._empty_result()
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty pressure result."""
        return {
            'buying_pressure': 50.0,
            'selling_pressure': 50.0,
            'pressure_ratio': 1.0,
            'pressure_ranges': {},
            'direction': 'NEUTRAL',
            'predicted_price': 0.0,
            'confidence': 0,
            'reason': 'Insufficient data',
            'imbalance': 0.0,
            'weighted_mid': 0.0
        }
    
    def _calculate_weighted_pressure(self, bids: List[List[float]], 
                                    asks: List[List[float]], 
                                    price: float) -> Dict[str, Dict]:
        """
        Calculate pressure at different price ranges with weighting.
        
        Returns pressure at 0.1%, 0.25%, 0.5%, 1%, 2% ranges.
        """
        ranges = [0.001, 0.0025, 0.005, 0.01, 0.02]
        result = {}
        
        for r in ranges:
            # Calculate depth within range
            bid_depth = 0
            for bid_price, qty in bids:
                if bid_price >= price * (1 - r):
                    bid_depth += qty
                else:
                    break
            
            ask_depth = 0
            for ask_price, qty in asks:
                if ask_price <= price * (1 + r):
                    ask_depth += qty
                else:
                    break
            
            # Calculate pressure (higher weight for closer levels)
            total_depth = bid_depth + ask_depth
            if total_depth > 0:
                buy_pct = (bid_depth / total_depth) * 100
                sell_pct = (ask_depth / total_depth) * 100
                ratio = bid_depth / ask_depth if ask_depth > 0 else float('inf')
                imbalance = (bid_depth - ask_depth) / total_depth * 100
            else:
                buy_pct = 50.0
                sell_pct = 50.0
                ratio = 1.0
                imbalance = 0.0
            
            result[f"{r*100:.1f}%"] = {
                'bid_depth': bid_depth,
                'ask_depth': ask_depth,
                'buy_pct': buy_pct,
                'sell_pct': sell_pct,
                'ratio': ratio,
                'imbalance': imbalance,
                'weight': 1.0 / (r * 100)  # Higher weight for smaller ranges
            }
        
        return result
    
    def _calculate_overall_pressure(self, pressure_ranges: Dict[str, Dict]) -> Dict:
        """
        Calculate overall pressure by weighting different ranges.
        
        Returns:
            Overall pressure metrics
        """
        if not pressure_ranges:
            return {'buy': 50.0, 'sell': 50.0, 'ratio': 1.0, 
                   'imbalance': 0.0, 'weighted_mid': 0.0}
        
        total_weight = 0
        weighted_buy = 0
        weighted_sell = 0
        weighted_imbalance = 0
        weighted_mid = 0
        
        for range_name, data in pressure_ranges.items():
            weight = data.get('weight', 1.0)
            total_weight += weight
            weighted_buy += data['buy_pct'] * weight
            weighted_sell += data['sell_pct'] * weight
            weighted_imbalance += data['imbalance'] * weight
            
            # Weighted mid price (weighted by total depth)
            depth_weight = (data['bid_depth'] + data['ask_depth']) / 1000  # Normalize
            weighted_mid += data['bid_depth'] * weight
        
        if total_weight > 0:
            buy = weighted_buy / total_weight
            sell = weighted_sell / total_weight
            imbalance = weighted_imbalance / total_weight
            weighted_mid = weighted_mid / total_weight if total_weight > 0 else 0
        else:
            buy = 50.0
            sell = 50.0
            imbalance = 0.0
            weighted_mid = 0.0
        
        # Clamp to valid ranges
        buy = clamp(buy, 0, 100)
        sell = clamp(sell, 0, 100)
        ratio = buy / sell if sell > 0 else 100.0
        
        return {
            'buy': buy,
            'sell': sell,
            'ratio': ratio,
            'imbalance': imbalance,
            'weighted_mid': weighted_mid
        }
    
    def _calculate_confidence(self, pressure_ranges: Dict[str, Dict],
                             order_book: Dict[str, Any]) -> int:
        """
        Calculate confidence score for the pressure analysis.
        
        Returns:
            Confidence percentage (0-100)
        """
        if not pressure_ranges:
            return 0
        
        # Factors affecting confidence:
        # 1. Consistency across ranges
        # 2. Total depth
        # 3. Spread tightness
        
        # Consistency across ranges
        buy_pcts = [data['buy_pct'] for data in pressure_ranges.values()]
        if len(buy_pcts) > 1:
            std_dev = np.std(buy_pcts)
            consistency_score = max(0, 100 - std_dev * 2)  # Higher std = lower confidence
        else:
            consistency_score = 50
        
        # Total depth
        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        total_depth = sum(qty for _, qty in bids) + sum(qty for _, qty in asks)
        depth_score = min(100, total_depth / 100)  # 100 depth = 100% confidence
        
        # Spread tightness
        best_bid = safe_float(bids[0][0]) if bids else 0
        best_ask = safe_float(asks[0][0]) if asks else 0
        if best_bid > 0 and best_ask > 0:
            spread_pct = (best_ask - best_bid) / best_bid * 100
            spread_score = max(0, 100 - spread_pct * 10)  # 0.1% spread = 99% confidence
        else:
            spread_score = 50
        
        # Weighted average
        confidence = (consistency_score * 0.4 + depth_score * 0.3 + spread_score * 0.3)
        return int(clamp(confidence, 0, 100))
    
    def _predict_direction(self, pressure_ranges: Dict[str, Dict],
                          overall_pressure: Dict,
                          order_book: Dict[str, Any],
                          current_price: float) -> Tuple[str, float, str]:
        """
        Predict price direction and target.
        
        Returns:
            Tuple of (direction, predicted_price, reason)
        """
        if not pressure_ranges or current_price <= 0:
            return 'NEUTRAL', current_price, 'Insufficient data'
        
        # Get pressure at different ranges
        near_pressure = pressure_ranges.get('0.1%', {})
        mid_pressure = pressure_ranges.get('0.5%', {})
        far_pressure = pressure_ranges.get('2.0%', {})
        
        near_buy = near_pressure.get('buy_pct', 50.0)
        mid_buy = mid_pressure.get('buy_pct', 50.0)
        far_buy = far_pressure.get('buy_pct', 50.0)
        
        # Determine direction based on pressure
        buy_pressure = overall_pressure['buy']
        
        if buy_pressure > 60:
            direction = 'UP'
        elif buy_pressure < 40:
            direction = 'DOWN'
        else:
            direction = 'NEUTRAL'
        
        # Calculate predicted price
        if direction == 'UP':
            # Target based on resistance levels
            resistance = self._find_resistance_level(order_book, current_price)
            if resistance > current_price:
                predicted_price = resistance
            else:
                # Estimate based on pressure
                spread_pct = 0.01 * (buy_pressure / 50)  # 1% base movement
                predicted_price = current_price * (1 + spread_pct)
        elif direction == 'DOWN':
            # Target based on support levels
            support = self._find_support_level(order_book, current_price)
            if support < current_price and support > 0:
                predicted_price = support
            else:
                spread_pct = 0.01 * ((100 - buy_pressure) / 50)
                predicted_price = current_price * (1 - spread_pct)
        else:
            predicted_price = current_price
        
        # Generate reason
        reason = self._generate_reason(direction, buy_pressure, pressure_ranges)
        
        return direction, predicted_price, reason
    
    def _find_resistance_level(self, order_book: Dict, current_price: float) -> float:
        """Find the nearest significant resistance level."""
        asks = order_book.get('asks', [])
        
        if not asks:
            return current_price * 1.01
        
        # Look for a large cluster of ask liquidity
        for ask_price, qty in asks:
            if ask_price > current_price:
                # Check if this is a significant level
                if qty > 10:  # Arbitrary threshold
                    return ask_price
        
        # Fallback: return next price level
        return asks[0][0] if asks else current_price * 1.01
    
    def _find_support_level(self, order_book: Dict, current_price: float) -> float:
        """Find the nearest significant support level."""
        bids = order_book.get('bids', [])
        
        if not bids:
            return current_price * 0.99
        
        # Look for a large cluster of bid liquidity
        for bid_price, qty in bids:
            if bid_price < current_price:
                if qty > 10:  # Arbitrary threshold
                    return bid_price
        
        # Fallback: return previous price level
        return bids[0][0] if bids else current_price * 0.99
    
    def _generate_reason(self, direction: str, buy_pressure: float,
                        pressure_ranges: Dict[str, Dict]) -> str:
        """Generate a human-readable reason for the prediction."""
        if direction == 'NEUTRAL':
            return 'Buying and selling pressure are balanced; price likely to range.'
        
        near_pressure = pressure_ranges.get('0.1%', {})
        far_pressure = pressure_ranges.get('2.0%', {})
        
        near_buy = near_pressure.get('buy_pct', 50.0)
        far_buy = far_pressure.get('buy_pct', 50.0)
        
        if direction == 'UP':
            reason = f"Buying pressure {buy_pressure:.1f}% "
            if near_buy > far_buy:
                reason += "with strong support near the current price. "
            else:
                reason += "across multiple price levels. "
            
            # Check for resistance
            reason += "Bid volume dominates the order book."
        else:
            reason = f"Selling pressure {(100 - buy_pressure):.1f}% "
            if near_buy < far_buy:
                reason += "with strong resistance near the current price. "
            else:
                reason += "across multiple price levels. "
            
            reason += "Ask volume dominates the order book."
        
        return reason