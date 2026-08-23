"""WebSocket handler for Binance Futures streaming data."""
import asyncio
import json
import websockets
from typing import Dict, List, Optional, Any, Callable, Awaitable, Deque
from collections import deque
from datetime import datetime
import sys
import time

# Fix imports - absolute imports
from utils.config import load_config
from utils.helpers import safe_float, format_timestamp
from utils.logger import get_logger


class OrderBookManager:
    """Maintains local order book from WebSocket depth updates."""
    
    def __init__(self, symbol: str):
        """
        Initialize order book manager.
        
        Args:
            symbol: Trading pair symbol
        """
        self.symbol = symbol.upper()
        self.bids: Dict[float, float] = {}
        self.asks: Dict[float, float] = {}
        self.last_update_id: int = 0
        self._last_received_u: int = 0
        self._last_processed_u: int = 0
        self._initialized = False
        self._snapshot_attempts = 0
        self.logger = get_logger(f"orderbook.{symbol}")
    
    def apply_snapshot(self, data: Dict) -> bool:
        """
        Apply a full snapshot to the order book.
        
        Args:
            data: Snapshot data with 'bids', 'asks', and 'lastUpdateId'
        
        Returns:
            True if snapshot applied successfully
        """
        try:
            last_update_id = data.get('lastUpdateId', 0)
            if last_update_id == 0:
                return False
            
            # Clear existing data
            self.bids.clear()
            self.asks.clear()
            
            # Add bids
            for bid in data.get('bids', []):
                price = safe_float(bid[0])
                qty = safe_float(bid[1])
                if price > 0 and qty > 0:
                    self.bids[price] = qty
            
            # Add asks
            for ask in data.get('asks', []):
                price = safe_float(ask[0])
                qty = safe_float(ask[1])
                if price > 0 and qty > 0:
                    self.asks[price] = qty
            
            self.last_update_id = last_update_id
            self._last_processed_u = last_update_id
            self._last_received_u = last_update_id
            self._initialized = True
            self._snapshot_attempts = 0
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to apply snapshot: {e}")
            return False
    
    def apply_update(self, data: Dict) -> bool:
        """
        Apply a depth update to the order book.
        
        Args:
            data: Update data with 'bids', 'asks', 'U', 'u'
        
        Returns:
            True if update applied successfully
        """
        if not self._initialized:
            return False
        
        try:
            u = data.get('u', 0)
            U = data.get('U', 0)
            
            if u == 0 or U == 0:
                return False
            
            # Check for gap or outdated update
            if self._last_processed_u > 0 and U > self._last_processed_u + 1:
                self.logger.warning(
                    f"Gap detected: last={self._last_processed_u}, U={U}, u={u}"
                )
                return False
            
            if self._last_processed_u > 0 and u <= self._last_processed_u:
                # Old update, ignore
                return False
            
            # Apply bid updates
            for bid in data.get('bids', []):
                price = safe_float(bid[0])
                qty = safe_float(bid[1])
                if price > 0:
                    if qty > 0:
                        self.bids[price] = qty
                    else:
                        self.bids.pop(price, None)
            
            # Apply ask updates
            for ask in data.get('asks', []):
                price = safe_float(ask[0])
                qty = safe_float(ask[1])
                if price > 0:
                    if qty > 0:
                        self.asks[price] = qty
                    else:
                        self.asks.pop(price, None)
            
            self._last_processed_u = u
            self._last_received_u = u
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to apply update: {e}")
            return False
    
    def get_ordered_bids(self, limit: int = 1000) -> List[List[float]]:
        """Get sorted bid levels (highest to lowest)."""
        sorted_bids = sorted(self.bids.items(), key=lambda x: x[0], reverse=True)
        return [[price, qty] for price, qty in sorted_bids[:limit]]
    
    def get_ordered_asks(self, limit: int = 1000) -> List[List[float]]:
        """Get sorted ask levels (lowest to highest)."""
        sorted_asks = sorted(self.asks.items(), key=lambda x: x[0])
        return [[price, qty] for price, qty in sorted_asks[:limit]]
    
    def get_best_bid(self) -> float:
        """Get best bid price."""
        if not self.bids:
            return 0.0
        return max(self.bids.keys())
    
    def get_best_ask(self) -> float:
        """Get best ask price."""
        if not self.asks:
            return 0.0
        return min(self.asks.keys())
    
    def get_mid_price(self) -> float:
        """Get mid price."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid > 0 and best_ask > 0:
            return (best_bid + best_ask) / 2
        return 0.0
    
    def get_depth(self, limit: int = 1000) -> Dict:
        """Get current order book depth."""
        return {
            'symbol': self.symbol,
            'timestamp': int(datetime.utcnow().timestamp() * 1000),
            'bids': self.get_ordered_bids(limit),
            'asks': self.get_ordered_asks(limit),
            'last_update_id': self.last_update_id
        }
    
    def is_initialized(self) -> bool:
        """Check if order book is initialized."""
        return self._initialized
    
    def get_snapshot_attempts(self) -> int:
        """Get number of snapshot attempts."""
        return self._snapshot_attempts
    
    def increment_snapshot_attempts(self) -> None:
        """Increment snapshot attempt counter."""
        self._snapshot_attempts += 1


class WebSocketHandler:
    """Handles WebSocket connections and data streams."""
    
    def __init__(self, config_path = None):
        """
        Initialize WebSocket handler.
        
        Args:
            config_path: Path to config file
        """
        self.config = load_config(config_path)
        self.ws_url = self.config.api.ws_url
        self.logger = get_logger("websocket")
        self.websocket = None
        self._running = False
        self._tasks = []
        
        # Data buffers
        self.trade_buffer: Deque[Dict] = deque(maxlen=1000)
        self.kline_buffer: Dict[str, Dict] = {}
        
        # Order books by symbol
        self.order_books: Dict[str, OrderBookManager] = {}
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'depth': [],
            'trade': [],
            'kline': [],
            'mark_price': [],
            'error': []
        }
        
        # Reconnection
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._reconnect_attempts = 0
    
    def add_callback(self, event_type: str, callback: Callable[[Dict], Awaitable[None]]):
        """
        Add a callback for WebSocket events.
        
        Args:
            event_type: 'depth', 'trade', 'kline', 'mark_price', or 'error'
            callback: Async function that takes event data
        """
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
    
    def remove_callback(self, event_type: str, callback: Callable) -> bool:
        """Remove a callback."""
        if event_type in self._callbacks:
            try:
                self._callbacks[event_type].remove(callback)
                return True
            except ValueError:
                pass
        return False
    
    async def _on_message(self, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # Check if it's a stream message
            if 'stream' in data:
                stream = data['stream']
                event_data = data.get('data', {})
                
                # Route by stream type
                if 'depth' in stream:
                    await self._handle_depth(stream, event_data)
                elif 'aggTrade' in stream:
                    await self._handle_trade(stream, event_data)
                elif 'kline' in stream:
                    await self._handle_kline(stream, event_data)
                elif 'markPrice' in stream:
                    await self._handle_mark_price(stream, event_data)
            else:
                # Direct message (like subscription confirmation)
                self.logger.debug(f"Received direct message: {data}")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")
            await self._trigger_callbacks('error', {'error': str(e)})
    
    async def _handle_depth(self, stream: str, data: Dict) -> None:
        """Handle depth stream update."""
        symbol = stream.split('@')[0].upper()
        
        # Get or create order book manager
        if symbol not in self.order_books:
            return
        
        book = self.order_books[symbol]
        
        # Check if it's a snapshot or update
        if 'bids' in data and 'asks' in data and 'lastUpdateId' in data:
            # This is a snapshot
            if book.apply_snapshot(data):
                await self._trigger_callbacks('depth', {
                    'type': 'snapshot',
                    'symbol': symbol,
                    'data': book.get_depth()
                })
        elif 'bids' in data or 'asks' in data:
            # This is an update
            if 'U' in data and 'u' in data:
                if book.apply_update(data):
                    await self._trigger_callbacks('depth', {
                        'type': 'update',
                        'symbol': symbol,
                        'data': book.get_depth()
                    })
                else:
                    # Update failed, need resync
                    self.logger.warning(f"Depth update failed for {symbol}, requesting resync")
                    await self._trigger_callbacks('depth', {
                        'type': 'resync_needed',
                        'symbol': symbol
                    })
    
    async def _handle_trade(self, stream: str, data: Dict) -> None:
        """Handle trade stream update."""
        symbol = stream.split('@')[0].upper()
        
        # Normalize trade data
        trade_data = {
            'symbol': symbol,
            'id': data.get('a', 0),
            'price': safe_float(data.get('p', 0)),
            'qty': safe_float(data.get('q', 0)),
            'time': data.get('T', 0),
            'is_buyer_maker': data.get('m', False),
            'timestamp': format_timestamp(data.get('T', 0) / 1000)
        }
        
        # Add to buffer
        self.trade_buffer.append(trade_data)
        
        # Trigger callbacks
        await self._trigger_callbacks('trade', trade_data)
    
    async def _handle_kline(self, stream: str, data: Dict) -> None:
        """Handle kline stream update."""
        symbol = stream.split('@')[0].upper()
        kline = data.get('k', {})
        
        if kline:
            kline_data = {
                'symbol': symbol,
                'interval': kline.get('i', ''),
                'time': kline.get('t', 0),
                'open': safe_float(kline.get('o', 0)),
                'high': safe_float(kline.get('h', 0)),
                'low': safe_float(kline.get('l', 0)),
                'close': safe_float(kline.get('c', 0)),
                'volume': safe_float(kline.get('v', 0)),
                'is_closed': kline.get('x', False),
                'timestamp': format_timestamp(kline.get('t', 0) / 1000)
            }
            
            # Store in buffer
            key = f"{symbol}_{kline_data['interval']}"
            self.kline_buffer[key] = kline_data
            
            # Trigger callbacks
            await self._trigger_callbacks('kline', kline_data)
    
    async def _handle_mark_price(self, stream: str, data: Dict) -> None:
        """Handle mark price stream update."""
        symbol = stream.split('@')[0].upper()
        
        mark_data = {
            'symbol': symbol,
            'mark_price': safe_float(data.get('p', 0)),
            'index_price': safe_float(data.get('i', 0)),
            'funding_rate': safe_float(data.get('r', 0)),
            'next_funding_time': data.get('T', 0),
            'timestamp': data.get('E', 0)
        }
        
        await self._trigger_callbacks('mark_price', mark_data)
    
    async def _trigger_callbacks(self, event_type: str, data: Dict) -> None:
        """Trigger all callbacks for an event type."""
        if event_type not in self._callbacks:
            return
        
        for callback in self._callbacks[event_type]:
            try:
                await callback(data)
            except Exception as e:
                self.logger.error(f"Callback error for {event_type}: {e}")
    
    async def _connect(self) -> bool:
        """Establish WebSocket connection."""
        try:
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5
            )
            self.logger.info(f"Connected to WebSocket: {self.ws_url}")
            self._reconnect_attempts = 0
            self._reconnect_delay = 1.0
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect WebSocket: {e}")
            return False
    
    async def _subscribe(self, streams: List[str]) -> bool:
        """Subscribe to streams."""
        if not self.websocket:
            return False
        
        try:
            payload = {
                'method': 'SUBSCRIBE',
                'params': streams,
                'id': int(time.time() * 1000)
            }
            await self.websocket.send(json.dumps(payload))
            
            # Wait for confirmation
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get('result') is not None:
                self.logger.info(f"Subscribed to streams: {streams}")
                return True
            else:
                self.logger.error(f"Subscription failed: {data}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to subscribe: {e}")
            return False
    
    async def _listen(self) -> None:
        """Listen for WebSocket messages."""
        if not self.websocket:
            return
        
        try:
            async for message in self.websocket:
                await self._on_message(message)
        except websockets.WebSocketException as e:
            self.logger.warning(f"WebSocket disconnected: {e}")
        except Exception as e:
            self.logger.error(f"WebSocket listen error: {e}")
    
    async def start(self, symbol: str, streams: Optional[List[str]] = None) -> None:
        """
        Start WebSocket connection and subscriptions.
        
        Args:
            symbol: Trading pair symbol
            streams: Optional list of stream names. If None, subscribes to all.
        """
        symbol = symbol.upper()
        
        if self._running:
            self.logger.warning("WebSocket already running")
            return
        
        self._running = True
        
        # Create order book manager
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBookManager(symbol)
        
        # Default streams
        if streams is None:
            streams = [
                f"{symbol.lower()}@depth",
                f"{symbol.lower()}@aggTrade",
                f"{symbol.lower()}@kline_5m",
                f"{symbol.lower()}@markPrice"
            ]
        
        # Main connection loop with reconnection
        while self._running:
            try:
                if await self._connect():
                    if await self._subscribe(streams):
                        await self._listen()
                    else:
                        await asyncio.sleep(self._reconnect_delay)
                else:
                    await asyncio.sleep(self._reconnect_delay)
                
                # Reconnection backoff
                self._reconnect_attempts += 1
                self._reconnect_delay = min(
                    self._reconnect_delay * 1.5,
                    self._max_reconnect_delay
                )
                
            except asyncio.CancelledError:
                self.logger.info("WebSocket listener cancelled")
                break
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(self._reconnect_delay)
    
    async def stop(self) -> None:
        """Stop WebSocket connection."""
        self._running = False
        
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
            self.websocket = None
        
        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        self._tasks.clear()
        self.logger.info("WebSocket stopped")
    
    def get_order_book(self, symbol: str) -> Optional[OrderBookManager]:
        """Get order book manager for a symbol."""
        return self.order_books.get(symbol.upper())
    
    def get_trades(self, limit: int = 100) -> List[Dict]:
        """Get recent trades from buffer."""
        return list(self.trade_buffer)[-limit:]
    
    def get_last_kline(self, symbol: str, interval: str = '5m') -> Optional[Dict]:
        """Get latest kline data for a symbol."""
        key = f"{symbol.upper()}_{interval}"
        return self.kline_buffer.get(key)