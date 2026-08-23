"""Whale detection from order book walls and large trades."""
from typing import Dict, List, Optional, Any, Tuple
import math
import numpy as np
from collections import defaultdict

# Fix imports - absolute imports
from utils.helpers import safe_float, format_notional, clamp
from utils.logger import get_logger


class WhaleDetector:
    """Detects whale activity from order book walls and large trades."""
    
    def __init__(self, config_path = None):
        """Initialize whale detector."""
        self.logger = get_logger("whale_detector")
        self.config_path = config_path
        
        # Default parameters
        self.wall_multiplier = 5.0
        self.min_notional = 500000.0
        self.min_ratio = 3.0
        self.cluster_radius_bps = 2
    
    def detect(self, order_book: Dict[str, Any], 
               trades: Optional[List[Dict]] = None,
               price: float = 0.0) -> Dict[str, Any]:
        """
        Detect whale walls and large trades.
        
        Args:
            order_book: Order book data with 'bids' and 'asks'
            trades: Optional list of recent trades
            price: Current price (if known)
        
        Returns:
            Whale detection results
        """
        try:
            bids = order_book.get('bids', [])
            asks = order_book.get('asks', [])
            
            if not bids or not asks:
                return self._empty_result()
            
            # Get mid price
            best_bid = safe_float(bids[0][0]) if bids else 0
            best_ask = safe_float(asks[0][0]) if asks else 0
            mid_price = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0
            
            if price <= 0:
                price = mid_price
            
            if price <= 0:
                return self._empty_result()
            
            # Detect bid walls
            bid_walls = self._detect_walls(bids, 'BID', price)
            
            # Detect ask walls
            ask_walls = self._detect_walls(asks, 'ASK', price)
            
            # Analyze walls
            walls_analysis = self._analyze_walls(bid_walls, ask_walls, price)
            
            # Detect whale trades
            whale_trades = self._detect_whale_trades(trades) if trades else []
            
            # Analyze trade bias
            trade_bias, trade_strength = self._analyze_trade_bias(whale_trades)
            
            # Overall bias
            overall_bias, overall_strength, score = self._determine_overall_bias(
                bid_walls, ask_walls, whale_trades, trade_bias
            )
            
            # Generate note
            note = self._generate_note(overall_bias, bid_walls, ask_walls, whale_trades)
            
            return {
                'detected': len(bid_walls) + len(ask_walls) + len(whale_trades) > 0,
                'count': len(bid_walls) + len(ask_walls) + len(whale_trades),
                'bias': overall_bias,
                'strength': overall_strength,
                'score': score,
                'bid_walls': bid_walls,
                'ask_walls': ask_walls,
                'whale_trades': whale_trades,
                'trade_bias': trade_bias,
                'note': note,
                'wall_ratio': walls_analysis['ratio'],
                'total_wall_notional': walls_analysis['total_notional']
            }
            
        except Exception as e:
            self.logger.error(f"Whale detection failed: {e}")
            return self._empty_result()
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty whale detection result."""
        return {
            'detected': False,
            'count': 0,
            'bias': 'NEUTRAL',
            'strength': 'NONE',
            'score': 0,
            'bid_walls': [],
            'ask_walls': [],
            'whale_trades': [],
            'trade_bias': 'NEUTRAL',
            'note': 'No whale activity detected',
            'wall_ratio': 1.0,
            'total_wall_notional': 0.0
        }
    
    def _detect_walls(self, levels: List[List[float]], side: str, 
                      price: float) -> List[Dict]:
        """
        Detect whale walls in order book levels.
        
        Args:
            levels: List of [price, qty] levels
            side: 'BID' or 'ASK'
            price: Current price
        
        Returns:
            List of wall dictionaries
        """
        walls = []
        
        if not levels or price <= 0:
            return walls
        
        # Calculate average quantity
        qties = [safe_float(qty) for _, qty in levels if qty > 0]
        if not qties:
            return walls
        
        avg_qty = np.mean(qties)
        std_qty = np.std(qties)
        
        # Threshold for wall detection
        threshold = max(avg_qty * self.wall_multiplier, 
                       avg_qty + std_qty * 2)
        
        # Find levels that exceed threshold
        for level_price, qty in levels:
            qty = safe_float(qty)
            if qty <= 0:
                continue
            
            if qty > threshold:
                notional = qty * level_price
                distance_pct = abs(level_price - price) / price * 100
                ratio = qty / avg_qty if avg_qty > 0 else 0
                
                if notional >= self.min_notional:
                    walls.append({
                        'price': level_price,
                        'qty': qty,
                        'notional': notional,
                        'distance_pct': distance_pct,
                        'ratio': ratio,
                        'side': side,
                        'is_bid_wall': side == 'BID'
                    })
        
        # Sort by notional (descending)
        walls.sort(key=lambda x: x['notional'], reverse=True)
        
        # Remove duplicates (cluster nearby levels)
        walls = self._cluster_walls(walls, price)
        
        return walls[:10]  # Return top 10 walls
    
    def _cluster_walls(self, walls: List[Dict], price: float) -> List[Dict]:
        """Cluster walls that are close together."""
        if not walls:
            return walls
        
        clustered = []
        radius = price * (self.cluster_radius_bps / 10000)  # Convert bps to price
        
        for wall in walls:
            found = False
            for cluster in clustered:
                if abs(wall['price'] - cluster['price']) <= radius:
                    # Merge into cluster
                    cluster['qty'] += wall['qty']
                    cluster['notional'] += wall['notional']
                    cluster['price'] = (cluster['price'] + wall['price']) / 2
                    cluster['ratio'] = max(cluster['ratio'], wall['ratio'])
                    cluster['distance_pct'] = min(cluster['distance_pct'], wall['distance_pct'])
                    found = True
                    break
            
            if not found:
                clustered.append(wall.copy())
        
        return clustered
    
    def _analyze_walls(self, bid_walls: List[Dict], ask_walls: List[Dict],
                       price: float) -> Dict[str, Any]:
        """Analyze walls for bias and strength."""
        total_bid_notional = sum(w['notional'] for w in bid_walls)
        total_ask_notional = sum(w['notional'] for w in ask_walls)
        total_notional = total_bid_notional + total_ask_notional
        
        if total_notional > 0:
            ratio = total_bid_notional / total_ask_notional if total_ask_notional > 0 else float('inf')
        else:
            ratio = 1.0
        
        return {
            'total_bid_notional': total_bid_notional,
            'total_ask_notional': total_ask_notional,
            'total_notional': total_notional,
            'ratio': ratio,
            'bid_count': len(bid_walls),
            'ask_count': len(ask_walls)
        }
    
    def _detect_whale_trades(self, trades: List[Dict]) -> List[Dict]:
        """Detect whale trades (large market orders)."""
        whale_trades = []
        
        if not trades:
            return whale_trades
        
        # Calculate average trade size
        sizes = [safe_float(t.get('qty', 0)) for t in trades]
        if not sizes:
            return whale_trades
        
        avg_size = np.mean(sizes)
        std_size = np.std(sizes)
        
        # Threshold for whale trade
        threshold = max(avg_size * 3, avg_size + std_size * 2)
        
        for trade in trades:
            qty = safe_float(trade.get('qty', 0))
            price = safe_float(trade.get('price', 0))
            notional = qty * price
            
            if qty > threshold and notional >= self.min_notional:
                is_buy = not trade.get('is_buyer_maker', False)  # Buyer is taker = buy
                
                whale_trades.append({
                    'price': price,
                    'qty': qty,
                    'notional': notional,
                    'side': 'BUY' if is_buy else 'SELL',
                    'time': trade.get('time', 0),
                    'ratio': qty / avg_size if avg_size > 0 else 0,
                    'is_whale_buy': is_buy
                })
        
        return whale_trades
    
    def _analyze_trade_bias(self, whale_trades: List[Dict]) -> Tuple[str, str]:
        """Analyze bias from whale trades."""
        if not whale_trades:
            return 'NEUTRAL', 'NONE'
        
        buy_volume = sum(t['qty'] for t in whale_trades if t['side'] == 'BUY')
        sell_volume = sum(t['qty'] for t in whale_trades if t['side'] == 'SELL')
        total = buy_volume + sell_volume
        
        if total == 0:
            return 'NEUTRAL', 'NONE'
        
        buy_pct = (buy_volume / total) * 100
        
        if buy_pct >= 60:
            bias = 'BUY'
            if buy_pct >= 80:
                strength = 'EXTREME'
            elif buy_pct >= 70:
                strength = 'STRONG'
            else:
                strength = 'MEDIUM'
        elif buy_pct <= 40:
            bias = 'SELL'
            if buy_pct <= 20:
                strength = 'EXTREME'
            elif buy_pct <= 30:
                strength = 'STRONG'
            else:
                strength = 'MEDIUM'
        else:
            bias = 'NEUTRAL'
            strength = 'WEAK'
        
        return bias, strength
    
    def _determine_overall_bias(self, bid_walls: List[Dict], ask_walls: List[Dict],
                               whale_trades: List[Dict], trade_bias: str) -> Tuple[str, str, int]:
        """
        Determine overall whale bias.
        
        Returns:
            Tuple of (bias, strength, score)
        """
        # Calculate wall bias
        wall_score = 0
        if bid_walls or ask_walls:
            bid_notional = sum(w['notional'] for w in bid_walls)
            ask_notional = sum(w['notional'] for w in ask_walls)
            total = bid_notional + ask_notional
            
            if total > 0:
                wall_score = (bid_notional - ask_notional) / total * 100
        
        # Trade bias score
        trade_score = 0
        if whale_trades:
            buy_volume = sum(t['qty'] for t in whale_trades if t['side'] == 'BUY')
            sell_volume = sum(t['qty'] for t in whale_trades if t['side'] == 'SELL')
            total = buy_volume + sell_volume
            
            if total > 0:
                trade_score = (buy_volume - sell_volume) / total * 100
        
        # Combined score (weighted)
        combined_score = wall_score * 0.6 + trade_score * 0.4
        
        # Determine bias
        if combined_score >= 15:
            bias = 'BUY'
        elif combined_score <= -15:
            bias = 'SELL'
        else:
            bias = 'NEUTRAL'
        
        # Determine strength
        abs_score = abs(combined_score)
        if abs_score >= 70:
            strength = 'EXTREME'
        elif abs_score >= 50:
            strength = 'STRONG'
        elif abs_score >= 30:
            strength = 'MEDIUM'
        elif abs_score >= 15:
            strength = 'WEAK'
        else:
            strength = 'NONE'
        
        # Score (0-100)
        score = int(clamp(50 + combined_score * 0.5, 0, 100))
        
        return bias, strength, score
    
    def _generate_note(self, bias: str, bid_walls: List[Dict], 
                      ask_walls: List[Dict], whale_trades: List[Dict]) -> str:
        """Generate a human-readable note about whale activity."""
        if not bid_walls and not ask_walls and not whale_trades:
            return "No whale activity detected"
        
        parts = []
        
        if bid_walls:
            total_bid = sum(w['notional'] for w in bid_walls)
            parts.append(f"Bid walls: {len(bid_walls)} walls, total {format_notional(total_bid)}")
        
        if ask_walls:
            total_ask = sum(w['notional'] for w in ask_walls)
            parts.append(f"Ask walls: {len(ask_walls)} walls, total {format_notional(total_ask)}")
        
        if whale_trades:
            buy_count = sum(1 for t in whale_trades if t['side'] == 'BUY')
            sell_count = sum(1 for t in whale_trades if t['side'] == 'SELL')
            parts.append(f"Whale trades: {len(whale_trades)} total ({buy_count} buys, {sell_count} sells)")
        
        if bias == 'BUY':
            parts.append("Whale volume is buying up")
        elif bias == 'SELL':
            parts.append("Whale volume is selling down")
        else:
            parts.append("Whale activity is balanced")
        
        return " ".join(parts)