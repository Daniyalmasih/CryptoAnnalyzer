"""Historical data management and caching."""
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

# Fix imports - absolute imports
from utils.config import get_project_root
from utils.helpers import safe_float
from utils.logger import get_logger
from data.binance_client import BinanceClient


class HistoricalData:
    """Fetches, caches, and manages historical price data."""
    
    def __init__(self, symbol: str, interval: str = '5m', 
                 max_bars: int = 500, config_path = None):
        """
        Initialize historical data manager.
        
        Args:
            symbol: Trading pair symbol
            interval: Kline interval
            max_bars: Maximum number of bars to keep
            config_path: Path to config file
        """
        self.symbol = symbol.upper()
        self.interval = interval
        self.max_bars = max_bars
        self.config_path = config_path
        self.logger = get_logger(f"historical.{symbol}")
        
        # Data storage
        self._data: Dict[str, List] = {
            'timestamps': [],
            'opens': [],
            'highs': [],
            'lows': [],
            'closes': [],
            'volumes': [],
            'quote_volumes': []
        }
        
        self._df: Optional[pd.DataFrame] = None
        self._cache_file = None
        self._client = None
        
        # Initialize cache path
        project_root = get_project_root()
        cache_dir = project_root / 'data_cache'
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = cache_dir / f"{symbol}_{interval}.json"
    
    def _df_from_data(self) -> pd.DataFrame:
        """Create DataFrame from stored data."""
        if not self._data['timestamps']:
            return pd.DataFrame()
        
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(self._data['timestamps'], unit='ms'),
            'open': self._data['opens'],
            'high': self._data['highs'],
            'low': self._data['lows'],
            'close': self._data['closes'],
            'volume': self._data['volumes'],
            'quote_volume': self._data['quote_volumes']
        })
        df.set_index('timestamp', inplace=True)
        return df
    
    def _save_cache(self) -> None:
        """Save historical data to cache file."""
        if not self._cache_file:
            return
        
        try:
            data = {
                'symbol': self.symbol,
                'interval': self.interval,
                'last_updated': datetime.utcnow().isoformat(),
                'data': {
                    'timestamps': self._data['timestamps'],
                    'opens': self._data['opens'],
                    'highs': self._data['highs'],
                    'lows': self._data['lows'],
                    'closes': self._data['closes'],
                    'volumes': self._data['volumes'],
                    'quote_volumes': self._data['quote_volumes']
                }
            }
            with open(self._cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to save cache: {e}")
    
    def _load_cache(self) -> bool:
        """Load historical data from cache file."""
        if not self._cache_file or not self._cache_file.exists():
            return False
        
        try:
            with open(self._cache_file, 'r') as f:
                data = json.load(f)
            
            # Check if data is for the correct symbol and interval
            if data.get('symbol') != self.symbol:
                return False
            if data.get('interval') != self.interval:
                return False
            
            cache_data = data.get('data', {})
            self._data['timestamps'] = cache_data.get('timestamps', [])
            self._data['opens'] = cache_data.get('opens', [])
            self._data['highs'] = cache_data.get('highs', [])
            self._data['lows'] = cache_data.get('lows', [])
            self._data['closes'] = cache_data.get('closes', [])
            self._data['volumes'] = cache_data.get('volumes', [])
            self._data['quote_volumes'] = cache_data.get('quote_volumes', [])
            
            self._df = self._df_from_data()
            
            self.logger.info(f"Loaded {len(self._data['timestamps'])} bars from cache")
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to load cache: {e}")
            return False
    
    async def fetch(self, limit: Optional[int] = None, use_cache: bool = True) -> bool:
        """
        Fetch historical data from Binance API or cache.
        
        Args:
            limit: Number of bars to fetch. If None, uses max_bars.
            use_cache: Whether to use cached data
        
        Returns:
            True if data was successfully loaded
        """
        if limit is None:
            limit = self.max_bars
        
        # Try cache first
        if use_cache and self._load_cache():
            # If we have enough data, return
            if len(self._data['timestamps']) >= limit:
                return True
        
        # Fetch from API
        try:
            if self._client is None:
                self._client = BinanceClient(self.config_path)
                await self._client.start()
            
            klines = await self._client.get_klines(self.symbol, self.interval, limit)
            
            # Extract data
            timestamps = [int(k[0]) for k in klines]
            opens = [safe_float(k[1]) for k in klines]
            highs = [safe_float(k[2]) for k in klines]
            lows = [safe_float(k[3]) for k in klines]
            closes = [safe_float(k[4]) for k in klines]
            volumes = [safe_float(k[5]) for k in klines]
            quote_volumes = [safe_float(k[6]) for k in klines]
            
            # Update data
            self._data['timestamps'] = timestamps
            self._data['opens'] = opens
            self._data['highs'] = highs
            self._data['lows'] = lows
            self._data['closes'] = closes
            self._data['volumes'] = volumes
            self._data['quote_volumes'] = quote_volumes
            
            self._df = self._df_from_data()
            
            # Cache the data
            self._save_cache()
            
            self.logger.info(f"Fetched {len(klines)} bars from API")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to fetch historical data: {e}")
            # Try to use cache even if outdated
            if use_cache and self._load_cache():
                return True
            return False
    
    async def update(self) -> bool:
        """
        Update historical data with latest bars.
        
        Returns:
            True if data was updated successfully
        """
        try:
            if self._client is None:
                self._client = BinanceClient(self.config_path)
                await self._client.start()
            
            # Get latest data (only 5 bars)
            klines = await self._client.get_klines(self.symbol, self.interval, 5)
            
            # Check if we already have the latest bar
            latest_timestamp = self._data['timestamps'][-1] if self._data['timestamps'] else 0
            
            new_bars = 0
            for k in klines:
                ts = int(k[0])
                if ts > latest_timestamp:
                    self._data['timestamps'].append(ts)
                    self._data['opens'].append(safe_float(k[1]))
                    self._data['highs'].append(safe_float(k[2]))
                    self._data['lows'].append(safe_float(k[3]))
                    self._data['closes'].append(safe_float(k[4]))
                    self._data['volumes'].append(safe_float(k[5]))
                    self._data['quote_volumes'].append(safe_float(k[6]))
                    new_bars += 1
            
            # Keep only max_bars
            if len(self._data['timestamps']) > self.max_bars:
                keep = self.max_bars
                self._data['timestamps'] = self._data['timestamps'][-keep:]
                self._data['opens'] = self._data['opens'][-keep:]
                self._data['highs'] = self._data['highs'][-keep:]
                self._data['lows'] = self._data['lows'][-keep:]
                self._data['closes'] = self._data['closes'][-keep:]
                self._data['volumes'] = self._data['volumes'][-keep:]
                self._data['quote_volumes'] = self._data['quote_volumes'][-keep:]
            
            if new_bars > 0:
                self._df = self._df_from_data()
                self._save_cache()
                self.logger.info(f"Added {new_bars} new bars")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update historical data: {e}")
            return False
    
    def get_data(self) -> Dict[str, List]:
        """Get all historical data."""
        return self._data.copy()
    
    def get_df(self) -> pd.DataFrame:
        """Get historical data as DataFrame."""
        if self._df is None:
            self._df = self._df_from_data()
        return self._df
    
    def get_latest_price(self) -> float:
        """Get latest close price."""
        if self._data['closes']:
            return self._data['closes'][-1]
        return 0.0
    
    def get_price_history(self, limit: Optional[int] = None) -> List[float]:
        """Get price history (closing prices)."""
        if limit is None:
            limit = len(self._data['closes'])
        return self._data['closes'][-limit:]
    
    def get_volume_history(self, limit: Optional[int] = None) -> List[float]:
        """Get volume history."""
        if limit is None:
            limit = len(self._data['volumes'])
        return self._data['volumes'][-limit:]
    
    async def close(self) -> None:
        """Close the client session."""
        if self._client:
            await self._client.close()
            self._client = None