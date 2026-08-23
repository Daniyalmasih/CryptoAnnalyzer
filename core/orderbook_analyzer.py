"""Order book depth analysis for support/resistance and liquidity."""
from typing import Dict, List, Tuple, Optional, Any
import math
import numpy as np
from collections import defaultdict

# Fix imports - absolute imports
from utils.helpers import safe_float, clamp
from utils.logger import get_logger


class OrderBookAnalyzer:
    """Analyzes order book depth for liquidity clusters and support/resistance."""
    
    def __init__(self, config_path = None):
        """Initialize order book analyzer."""
        self.logger = get_logger("orderbook_analyzer")
        self.config_path = config_path
    
    def analyze(self, order_book: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze order book depth.
        
        Args:
            order_book: Order book data with 'bids' and 'asks'
        
        Returns:
            Analysis results including support/resistance levels, clusters, etc.
        """
        try:
            bids = order_book.get('bids', [])
            asks = order_book.get('asks', [])
            
            if not bids or not asks:
                return self._empty_result()
            
            # Extract prices and quantities
            bid_prices = [safe_float(b[0]) for b in bids]
            bid_qties = [safe_float(b[1]) for b in bids]
            ask_prices = [safe_float(a[0]) for a in asks]
            ask_qties = [safe_float(a[1]) for a in asks]
            
            # Best bid/ask
            best_bid = bid_prices[0] if bid_prices else 0
            best_ask = ask_prices[0] if ask_prices else 0
            
            # Spread
            spread = best_ask - best_bid if best_bid > 0 and best_ask > 0 else 0
            spread_pct = (spread / best_bid * 100) if best_bid > 0 else 0
            
            # Cumulative depth
            cum_bid_qty = sum(bid_qties)
            cum_ask_qty = sum(ask_qties)
            
            # Depth at different price ranges
            depth_ranges = self._calculate_depth_ranges(bids, asks, best_bid, best_ask)
            
            # Liquidity clusters (support/resistance)
            support, resistance = self._find_liquidity_clusters(bids, asks, best_bid, best_ask)
            
            # VWAP of the book
            vwap = self._calculate_vwap(bids, asks)
            
            # Book slope
            slope = self._calculate_book_slope(bids, asks)
            
            # Microprice
            microprice = self._calculate_microprice(bids, asks)
            
            return {
                'depth_analyzed': len(bids) + len(asks),
                'bid_levels': len(bids),
                'ask_levels': len(asks),
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread': spread,
                'spread_pct': spread_pct,
                'total_bid_qty': cum_bid_qty,
                'total_ask_qty': cum_ask_qty,
                'imbalance': self._calculate_imbalance(bids, asks),
                'depth_ranges': depth_ranges,
                'support': support,
                'resistance': resistance,
                'vwap': vwap,
                'slope': slope,
                'microprice': microprice,
                'clusters': self._get_clusters(bids, asks)
            }
            
        except Exception as e:
            self.logger.error(f"Order book analysis failed: {e}")
            return self._empty_result()
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty analysis result."""
        return {
            'depth_analyzed': 0,
            'bid_levels': 0,
            'ask_levels': 0,
            'best_bid': 0.0,
            'best_ask': 0.0,
            'spread': 0.0,
            'spread_pct': 0.0,
            'total_bid_qty': 0.0,
            'total_ask_qty': 0.0,
            'imbalance': 0.0,
            'depth_ranges': {},
            'support': [],
            'resistance': [],
            'vwap': 0.0,
            'slope': 0.0,
            'microprice': 0.0,
            'clusters': []
        }
    
    def _calculate_depth_ranges(self, bids: List[List[float]], 
                                asks: List[List[float]],
                                best_bid: float, 
                                best_ask: float) -> Dict[str, float]:
        """Calculate cumulative depth at different price ranges."""
        ranges = [0.001, 0.0025, 0.005, 0.01, 0.02]  # 0.1%, 0.25%, 0.5%, 1%, 2%
        result = {}
        
        if best_bid <= 0 or best_ask <= 0:
            return {f"{r*100}%": 0.0 for r in ranges}
        
        mid = (best_bid + best_ask) / 2
        
        for r in ranges:
            # Bid depth: within r% below mid
            bid_depth = 0
            for price, qty in bids:
                if price >= mid * (1 - r):
                    bid_depth += qty
                else:
                    break
            
            # Ask depth: within r% above mid
            ask_depth = 0
            for price, qty in asks:
                if price <= mid * (1 + r):
                    ask_depth += qty
                else:
                    break
            
            result[f"{r*100:.1f}%"] = {
                'bid_depth': bid_depth,
                'ask_depth': ask_depth,
                'total': bid_depth + ask_depth
            }
        
        return result
    
    def _find_liquidity_clusters(self, bids: List[List[float]], 
                                 asks: List[List[float]],
                                 best_bid: float, 
                                 best_ask: float) -> Tuple[List[float], List[float]]:
        """
        Find support (bid) and resistance (ask) levels.
        
        Returns:
            Tuple of (support_levels, resistance_levels)
        """
        support = []
        resistance = []
        
        if not bids or not asks or best_bid <= 0:
            return support, resistance
        
        mid = (best_bid + best_ask) / 2
        cluster_threshold = 0.02  # 2% price range for clustering
        
        # Find support levels (large bid clusters)
        bid_clusters = self._cluster_levels(bids, mid, 'bid', cluster_threshold)
        if bid_clusters:
            # Sort by quantity (descending) and take top 5
            bid_clusters.sort(key=lambda x: x['total_qty'], reverse=True)
            support = [c['price'] for c in bid_clusters[:5]]
        
        # Find resistance levels (large ask clusters)
        ask_clusters = self._cluster_levels(asks, mid, 'ask', cluster_threshold)
        if ask_clusters:
            # Sort by quantity (descending) and take top 5
            ask_clusters.sort(key=lambda x: x['total_qty'], reverse=True)
            resistance = [c['price'] for c in ask_clusters[:5]]
        
        return support, resistance
    
    def _cluster_levels(self, levels: List[List[float]], mid: float,
                        side: str, threshold: float) -> List[Dict]:
        """Cluster price levels that are close together."""
        if not levels:
            return []
        
        clusters = []
        sorted_levels = sorted(levels, key=lambda x: x[0])
        
        current_cluster = []
        current_price_sum = 0
        current_qty_sum = 0
        last_price = None
        
        for price, qty in sorted_levels:
            # Skip zero quantities
            if qty <= 0:
                continue
            
            if last_price is None:
                current_cluster.append((price, qty))
                current_price_sum += price
                current_qty_sum += qty
                last_price = price
            else:
                # Check if price is within threshold
                if abs(price - last_price) / mid < threshold:
                    current_cluster.append((price, qty))
                    current_price_sum += price
                    current_qty_sum += qty
                    last_price = price
                else:
                    # Finalize cluster
                    if current_cluster:
                        avg_price = current_price_sum / len(current_cluster)
                        clusters.append({
                            'price': avg_price,
                            'total_qty': current_qty_sum,
                            'count': len(current_cluster)
                        })
                    
                    # Start new cluster
                    current_cluster = [(price, qty)]
                    current_price_sum = price
                    current_qty_sum = qty
                    last_price = price
        
        # Finalize last cluster
        if current_cluster:
            avg_price = current_price_sum / len(current_cluster)
            clusters.append({
                'price': avg_price,
                'total_qty': current_qty_sum,
                'count': len(current_cluster)
            })
        
        return clusters
    
    def _calculate_vwap(self, bids: List[List[float]], asks: List[List[float]]) -> float:
        """Calculate Volume-Weighted Average Price of the order book."""
        total_qty = 0
        total_value = 0
        
        # Process bids
        for price, qty in bids:
            if qty > 0:
                total_qty += qty
                total_value += price * qty
        
        # Process asks
        for price, qty in asks:
            if qty > 0:
                total_qty += qty
                total_value += price * qty
        
        if total_qty > 0:
            return total_value / total_qty
        return 0.0
    
    def _calculate_book_slope(self, bids: List[List[float]], 
                              asks: List[List[float]]) -> float:
        """Calculate slope of the cumulative depth curve."""
        # For simplicity, use the 0.1% range
        if not bids or not asks:
            return 0.0
        
        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        
        if best_bid <= 0 or best_ask <= 0:
            return 0.0
        
        mid = (best_bid + best_ask) / 2
        range_pct = 0.001  # 0.1%
        
        # Get depth within range
        bid_depth = 0
        for price, qty in bids:
            if price >= mid * (1 - range_pct):
                bid_depth += qty
            else:
                break
        
        ask_depth = 0
        for price, qty in asks:
            if price <= mid * (1 + range_pct):
                ask_depth += qty
            else:
                break
        
        # Slope = (ask_depth - bid_depth) / (mid * range_pct * 2)
        price_range = mid * range_pct * 2
        if price_range > 0:
            slope = (ask_depth - bid_depth) / price_range
            return slope
        return 0.0
    
    def _calculate_microprice(self, bids: List[List[float]], 
                              asks: List[List[float]]) -> float:
        """
        Calculate microprice (weighted average of bid/ask using imbalance).
        """
        if not bids or not asks:
            return 0.0
        
        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        
        if best_bid <= 0 or best_ask <= 0:
            return 0.0
        
        # Get depth at best prices
        best_bid_qty = bids[0][1] if bids else 0
        best_ask_qty = asks[0][1] if asks else 0
        
        # Simple microprice
        total_qty = best_bid_qty + best_ask_qty
        if total_qty > 0:
            microprice = (best_bid * best_ask_qty + best_ask * best_bid_qty) / total_qty
            return microprice
        
        return (best_bid + best_ask) / 2
    
    def _calculate_imbalance(self, bids: List[List[float]], 
                             asks: List[List[float]]) -> float:
        """Calculate order book imbalance."""
        if not bids or not asks:
            return 0.0
        
        total_bid_qty = sum(qty for _, qty in bids)
        total_ask_qty = sum(qty for _, qty in asks)
        
        if total_bid_qty + total_ask_qty > 0:
            imbalance = (total_bid_qty - total_ask_qty) / (total_bid_qty + total_ask_qty)
            return imbalance * 100  # Percentage
        
        return 0.0
    
    def _get_clusters(self, bids: List[List[float]], 
                      asks: List[List[float]]) -> List[Dict]:
        """Get all liquidity clusters with details."""
        clusters = []
        
        # Combine bids and asks into a single view
        all_levels = []
        for price, qty in bids:
            if qty > 0:
                all_levels.append({'price': price, 'qty': qty, 'side': 'BID'})
        for price, qty in asks:
            if qty > 0:
                all_levels.append({'price': price, 'qty': qty, 'side': 'ASK'})
        
        # Sort by quantity (top 10)
        all_levels.sort(key=lambda x: x['qty'], reverse=True)
        
        for level in all_levels[:10]:
            clusters.append({
                'price': level['price'],
                'qty': level['qty'],
                'side': level['side']
            })
        
        return clusters