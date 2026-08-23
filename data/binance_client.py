"""Async Binance Futures API client for public endpoints."""
import asyncio
import json
import aiohttp
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pathlib import Path
import sys

# Fix imports - absolute imports
from utils.config import load_config, get_project_root
from utils.helpers import retry_async, safe_float, format_timestamp


class BinanceError(Exception):
    """Custom exception for Binance API errors."""
    pass


class BinanceClient:
    """Async client for Binance Futures public API."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the client with configuration."""
        self.config = load_config(config_path)
        self.base_url = self.config.api.rest_url
        self.timeout = aiohttp.ClientTimeout(total=self.config.api.timeout_seconds)
        self.session: Optional[aiohttp.ClientSession] = None
        self._closed = False
    
    async def __aenter__(self):
        """Enter async context manager."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.close()
    
    async def start(self) -> None:
        """Initialize the client session."""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=20,
                ttl_dns_cache=300,
                enable_cleanup_closed=True
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout,
                headers={'User-Agent': 'CryptoAnalyzer/1.0'}
            )
            self._closed = False
    
    async def close(self) -> None:
        """Close the client session."""
        if self.session and not self.session.closed:
            await self.session.close()
        self._closed = True
    
    @retry_async(max_attempts=3, delay=1.0, backoff=2.0)
    async def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make a GET request to the Binance API with retry logic.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
        
        Returns:
            Parsed JSON response as dict
        
        Raises:
            BinanceError: On API error
        """
        if self._closed or self.session is None or self.session.closed:
            await self.start()
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    try:
                        error_data = await response.json()
                        error_msg = error_data.get('msg', 'Unknown error')
                    except:
                        error_msg = await response.text()
                    
                    raise BinanceError(
                        f"HTTP {response.status}: {error_msg} "
                        f"(endpoint: {endpoint})"
                    )
                
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    return await response.json()
                else:
                    raise BinanceError(f"Unexpected content type: {content_type}")
                
        except aiohttp.ClientError as e:
            raise BinanceError(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise BinanceError(f"Invalid JSON response: {e}")
    
    async def get_depth(self, symbol: str, limit: int = 1000) -> Dict:
        """
        Get order book depth for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            limit: Number of levels (max 1000)
        
        Returns:
            Order book data with 'bids' and 'asks'
        """
        endpoint = "/fapi/v1/depth"
        params = {
            'symbol': symbol.upper(),
            'limit': min(limit, 1000)
        }
        return await self._request(endpoint, params)
    
    async def get_klines(self, symbol: str, interval: str = '5m', 
                         limit: int = 500) -> List[List]:
        """
        Get kline/candlestick data for a symbol.
        
        Args:
            symbol: Trading pair symbol
            interval: Kline interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, etc.)
            limit: Number of klines to fetch (max 1000)
        
        Returns:
            List of kline data arrays
        """
        endpoint = "/fapi/v1/klines"
        params = {
            'symbol': symbol.upper(),
            'interval': interval,
            'limit': min(limit, 1000)
        }
        return await self._request(endpoint, params)
    
    async def get_agg_trades(self, symbol: str, limit: int = 1000) -> List[Dict]:
        """
        Get aggregated trade data.
        
        Args:
            symbol: Trading pair symbol
            limit: Number of trades to fetch (max 1000)
        
        Returns:
            List of trade data objects
        """
        endpoint = "/fapi/v1/aggTrades"
        params = {
            'symbol': symbol.upper(),
            'limit': min(limit, 1000)
        }
        return await self._request(endpoint, params)
    
    async def get_24hr_ticker(self, symbol: Optional[str] = None) -> Union[Dict, List[Dict]]:
        """
        Get 24-hour ticker statistics.
        
        Args:
            symbol: Trading pair symbol. If None, returns all tickers.
        
        Returns:
            Ticker data for the symbol or all symbols
        """
        endpoint = "/fapi/v1/ticker/24hr"
        params = {}
        if symbol:
            params['symbol'] = symbol.upper()
        return await self._request(endpoint, params)
    
    async def get_premium_index(self, symbol: str) -> Dict:
        """
        Get premium index (funding rate / mark price).
        
        Args:
            symbol: Trading pair symbol
        
        Returns:
            Premium index data
        """
        endpoint = "/fapi/v1/premiumIndex"
        params = {'symbol': symbol.upper()}
        return await self._request(endpoint, params)
    
    async def get_open_interest(self, symbol: str) -> Dict:
        """
        Get open interest data.
        
        Args:
            symbol: Trading pair symbol
        
        Returns:
            Open interest data
        """
        endpoint = "/fapi/v1/openInterest"
        params = {'symbol': symbol.upper()}
        return await self._request(endpoint, params)
    
    async def get_exchange_info(self) -> Dict:
        """
        Get exchange information (trading pairs, filters, etc.).
        
        Returns:
            Exchange information
        """
        endpoint = "/fapi/v1/exchangeInfo"
        return await self._request(endpoint)
    
    async def get_current_price(self, symbol: str) -> float:
        """
        Get current price for a symbol from ticker.
        
        Args:
            symbol: Trading pair symbol
        
        Returns:
            Current price
        """
        data = await self.get_24hr_ticker(symbol)
        if isinstance(data, dict):
            return safe_float(data.get('lastPrice', 0))
        return 0.0
    
    async def normalize_depth(self, symbol: str, limit: int = 1000) -> Dict[str, Any]:
        """
        Get and normalize order book depth.
        
        Returns normalized dict with:
            - symbol: str
            - timestamp: int
            - bids: List[List[float, float]]
            - asks: List[List[float, float]]
            - last_update_id: int
        """
        raw = await self.get_depth(symbol, limit)
        
        return {
            'symbol': raw.get('symbol', symbol),
            'timestamp': raw.get('E', int(datetime.utcnow().timestamp() * 1000)),
            'bids': [[safe_float(x[0]), safe_float(x[1])] for x in raw.get('bids', [])],
            'asks': [[safe_float(x[0]), safe_float(x[1])] for x in raw.get('asks', [])],
            'last_update_id': raw.get('lastUpdateId', 0)
        }
    
    async def normalize_klines(self, symbol: str, interval: str = '5m',
                               limit: int = 500) -> Dict[str, Any]:
        """
        Get and normalize kline data.
        
        Returns normalized dict with lists of:
            - timestamps
            - opens, highs, lows, closes
            - volumes
            - quote_volumes
        """
        raw = await self.get_klines(symbol, interval, limit)
        
        return {
            'symbol': symbol.upper(),
            'interval': interval,
            'timestamps': [int(k[0]) for k in raw],
            'opens': [safe_float(k[1]) for k in raw],
            'highs': [safe_float(k[2]) for k in raw],
            'lows': [safe_float(k[3]) for k in raw],
            'closes': [safe_float(k[4]) for k in raw],
            'volumes': [safe_float(k[5]) for k in raw],
            'quote_volumes': [safe_float(k[6]) for k in raw],
            'trades': [int(k[8]) for k in raw]
        }