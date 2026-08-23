"""Volume analysis with buy/sell split and tape reading."""
from typing import Dict, List, Optional, Any, Tuple
import math
import numpy as np
from collections import deque

# Fix imports - absolute imports
from utils.helpers import safe_float, clamp
from utils.logger import get_logger


class VolumeAnalyzer:
    """Analyzes volume with buy/sell split, CVD, and tape reading."""
    
    def __init__(self, config_path = None):
        """Initialize volume analyzer."""
        self.logger = get_logger("volume_analyzer")
        self.config_path = config_path
        
        # Default parameters
        self.very_high_ratio = 2.0
        self.high_ratio = 1.5
        self.low_ratio = 0.7
        self.very_low_ratio = 0.4
        self.spike_multiplier = 2.0
        
        # Cumulative volume delta
        self.cvd = 0.0
        self._cvd_history = deque(maxlen=100)
    
    def analyze(self, volume_data: List[float], 
                trades: Optional[List[Dict]] = None,
                klines: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Analyze volume with buy/sell split and tape reading.
        
        Args:
            volume_data: List of historical volumes
            trades: Optional list of recent trades
            klines: Optional list of kline data with buy/sell info
        
        Returns:
            Volume analysis results
        """
        try:
            if not volume_data:
                return self._empty_result()
            
            current_volume = volume_data[-1] if volume_data else 0
            
            # Calculate average volume
            avg_volume = np.mean(volume_data) if volume_data else 0
            
            # Calculate ratio
            ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Determine status
            status = self._determine_status(ratio)
            
            # Analyze buy/sell split from trades or klines
            buy_volume, sell_volume = self._analyze_buy_sell_split(trades, klines)
            
            # Calculate percentages
            total_volume = buy_volume + sell_volume
            if total_volume > 0:
                buy_pct = (buy_volume / total_volume) * 100
                sell_pct = (sell_volume / total_volume) * 100
            else:
                buy_pct = 50.0
                sell_pct = 50.0
            
            # Determine direction
            direction = self._determine_direction(buy_pct)
            
            # Detect spikes
            spike = self._detect_spike(volume_data)
            
            # Calculate CVD (Cumulative Volume Delta)
            cvd = self._update_cvd(trades)
            
            # Tape analysis
            tape = self._analyze_tape(trades)
            
            return {
                'current': current_volume,
                'average': avg_volume,
                'ratio': ratio,
                'status': status,
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'buy_pct': buy_pct,
                'sell_pct': sell_pct,
                'direction': direction,
                'spike': spike,
                'cvd': cvd,
                'tape': tape,
                'volume_profile': self._calculate_volume_profile(volume_data)
            }
            
        except Exception as e:
            self.logger.error(f"Volume analysis failed: {e}")
            return self._empty_result()
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty volume result."""
        return {
            'current': 0.0,
            'average': 0.0,
            'ratio': 1.0,
            'status': 'NORMAL',
            'buy_volume': 0.0,
            'sell_volume': 0.0,
            'buy_pct': 50.0,
            'sell_pct': 50.0,
            'direction': 'BALANCED',
            'spike': False,
            'cvd': 0.0,
            'tape': {'buy_pct': 50.0, 'sell_pct': 50.0, 'trades': 0},
            'volume_profile': []
        }
    
    def _determine_status(self, ratio: float) -> str:
        """Determine volume status label."""
        if ratio >= self.very_high_ratio:
            return 'VERY_HIGH'
        elif ratio >= self.high_ratio:
            return 'HIGH'
        elif ratio >= self.low_ratio:
            return 'NORMAL'
        elif ratio >= self.very_low_ratio:
            return 'LOW'
        else:
            return 'VERY_LOW'
    
    def _analyze_buy_sell_split(self, trades: Optional[List[Dict]],
                               klines: Optional[List[Dict]]) -> Tuple[float, float]:
        """
        Analyze buy vs sell volume from trades or klines.
        
        Returns:
            Tuple of (buy_volume, sell_volume)
        """
        buy_volume = 0.0
        sell_volume = 0.0
        
        # Prefer trades data
        if trades:
            for trade in trades:
                qty = safe_float(trade.get('qty', 0))
                is_buyer_maker = trade.get('is_buyer_maker', False)
                price = safe_float(trade.get('price', 0))
                notional = qty * price
                
                # In Binance, is_buyer_maker=False means buyer is taker (buy)
                if not is_buyer_maker:
                    buy_volume += qty
                else:
                    sell_volume += qty
        
        # Fallback to klines
        elif klines:
            for k in klines:
                taker_buy_vol = safe_float(k.get('takerBuyVol', 0))
                taker_sell_vol = safe_float(k.get('takerSellVol', 0))
                buy_volume += taker_buy_vol
                sell_volume += taker_sell_vol
        
        return buy_volume, sell_volume
    
    def _determine_direction(self, buy_pct: float) -> str:
        """Determine volume direction."""
        if buy_pct >= 55:
            return 'BUY_DOMINANT'
        elif buy_pct <= 45:
            return 'SELL_DOMINANT'
        else:
            return 'BALANCED'
    
    def _detect_spike(self, volume_data: List[float]) -> bool:
        """Detect if current volume is a spike."""
        if len(volume_data) < 20:
            return False
        
        current = volume_data[-1]
        recent = volume_data[-20:-1]
        
        if not recent:
            return False
        
        mean = np.mean(recent)
        std = np.std(recent)
        
        if std > 0:
            z_score = (current - mean) / std
            return z_score > 2.0  # 2 standard deviations
        
        return False
    
    def _update_cvd(self, trades: Optional[List[Dict]]) -> float:
        """
        Update Cumulative Volume Delta.
        
        Returns:
            Current CVD value
        """
        if not trades:
            return self.cvd
        
        for trade in trades:
            qty = safe_float(trade.get('qty', 0))
            is_buyer_maker = trade.get('is_buyer_maker', False)
            
            # Buy = positive delta, Sell = negative delta
            if not is_buyer_maker:
                self.cvd += qty
            else:
                self.cvd -= qty
            
            self._cvd_history.append(self.cvd)
        
        return self.cvd
    
    def _analyze_tape(self, trades: Optional[List[Dict]]) -> Dict[str, Any]:
        """Analyze tape reading (buy vs sell flow)."""
        if not trades:
            return {'buy_pct': 50.0, 'sell_pct': 50.0, 'trades': 0}
        
        buy_count = 0
        sell_count = 0
        buy_volume = 0.0
        sell_volume = 0.0
        
        for trade in trades:
            qty = safe_float(trade.get('qty', 0))
            is_buyer_maker = trade.get('is_buyer_maker', False)
            
            if not is_buyer_maker:
                buy_count += 1
                buy_volume += qty
            else:
                sell_count += 1
                sell_volume += qty
        
        total = buy_count + sell_count
        if total > 0:
            buy_pct = (buy_count / total) * 100
            sell_pct = (sell_count / total) * 100
        else:
            buy_pct = 50.0
            sell_pct = 50.0
        
        return {
            'buy_pct': buy_pct,
            'sell_pct': sell_pct,
            'trades': total,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume
        }
    
    def _calculate_volume_profile(self, volume_data: List[float]) -> List[Dict]:
        """Calculate volume distribution profile."""
        if len(volume_data) < 10:
            return []
        
        # Sort volumes and create bins
        sorted_vol = sorted(volume_data)
        n_bins = min(10, len(sorted_vol) // 2)
        
        if n_bins < 2:
            return []
        
        bin_size = len(sorted_vol) // n_bins
        profile = []
        
        for i in range(n_bins):
            start = i * bin_size
            end = start + bin_size if i < n_bins - 1 else len(sorted_vol)
            bin_vols = sorted_vol[start:end]
            
            if bin_vols:
                profile.append({
                    'min': min(bin_vols),
                    'max': max(bin_vols),
                    'avg': np.mean(bin_vols),
                    'count': len(bin_vols)
                })
        
        return profile