"""Textual terminal application."""
from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Header, Footer, Static
from textual.reactive import reactive
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import sys
import traceback

from ui.dashboard import Dashboard
from ui.theme import load_theme
from core import (
    OrderBookAnalyzer, PressureCalculator, TrendAnalyzer,
    VolumeAnalyzer, WhaleDetector
)
from data import BinanceClient, WebSocketHandler, HistoricalData
from utils.config import load_config
from utils.logger import get_logger, log_json_snapshot
from utils.helpers import format_timestamp


class TerminalApp(App):
    """Main Textual application for the terminal UI."""
    
    CSS = """
    App {
        background: #000000;
        color: #00ff00;
    }
    Header {
        background: #003300;
        color: #00ff00;
    }
    Footer {
        background: #001100;
        color: #006600;
    }
    Static {
        background: #000000;
        color: #00ff00;
        padding: 1;
    }
    ScrollableContainer {
        background: #000000;
    }
    """
    
    def __init__(self, symbol: str = "BTCUSDT", config_path=None, no_ws: bool = False):
        super().__init__()
        self.symbol = symbol
        self.config_path = config_path
        self.no_ws = no_ws
        self.config = load_config(config_path)
        self.logger = get_logger("terminal_app")
        
        # Analysis components
        self.binance_client = BinanceClient(config_path)
        self.ws_handler = WebSocketHandler(config_path)
        self.historical = HistoricalData(symbol, config_path=config_path)
        
        self.orderbook_analyzer = OrderBookAnalyzer(config_path)
        self.pressure_calculator = PressureCalculator(config_path)
        self.trend_analyzer = TrendAnalyzer(config_path)
        self.volume_analyzer = VolumeAnalyzer(config_path)
        self.whale_detector = WhaleDetector(config_path)
        
        # State
        self._running = False
        self._paused = False
        self.dashboard = Dashboard(load_theme(self.config.theme))
        self.current_analysis = None
        self.engine = "python"
        self._analysis_task = None
        self._update_count = 0
        
        # Try Rust engine
        try:
            import crypto_rust_engine
            self.engine = "rust"
            self.logger.info("Using Rust engine")
        except ImportError:
            self.logger.info("Using Python fallback")
        
        # WebSocket callbacks
        self.ws_handler.add_callback('depth', self._on_depth_update)
        self.ws_handler.add_callback('trade', self._on_trade_update)
        self.ws_handler.add_callback('error', self._on_ws_error)
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(Static("🔄 Initializing...", id="dashboard"), id="main")
        yield Footer()
    
    async def on_mount(self) -> None:
        """Called when app mounts."""
        self.logger.info(f"Starting Terminal App for {self.symbol}")
        self.query_one("#dashboard").update("🔄 Loading market data...\n\nPlease wait...")
        
        # Start WebSocket if enabled
        if self.config.use_websocket and not self.no_ws:
            asyncio.create_task(self.ws_handler.start(self.symbol))
        
        # Start analysis
        self._start_analysis()
    
    def _start_analysis(self) -> None:
        """Start analysis loop."""
        async def analysis_loop():
            self._running = True
            refresh_interval = self.config.ui.refresh_interval_ms / 1000.0
            
            # Initial fetch
            try:
                await asyncio.wait_for(self.historical.fetch(limit=100), timeout=15.0)
            except Exception as e:
                self.logger.error(f"Historical fetch error: {e}")
            
            # Run first analysis
            await self._run_analysis()
            
            # Main loop
            while self._running:
                try:
                    if not self._paused:
                        await self._run_analysis()
                    await asyncio.sleep(refresh_interval)
                except Exception as e:
                    self.logger.error(f"Analysis loop error: {e}")
                    await asyncio.sleep(refresh_interval * 2)
        
        self._analysis_task = asyncio.create_task(analysis_loop())
    
    async def _run_analysis(self) -> None:
        """Run analysis cycle."""
        try:
            # Get order book
            try:
                order_book = await asyncio.wait_for(
                    self._get_order_book(), timeout=15.0
                )
            except:
                order_book = {'bids': [], 'asks': []}
            
            price = self._get_current_price(order_book)
            hist_data = self.historical.get_data()
            trades = self.ws_handler.get_trades(100)
            
            # Get mark data
            try:
                mark_data = await asyncio.wait_for(
                    self._get_mark_data(), timeout=5.0
                )
            except:
                mark_data = {'mark_price': 0, 'funding_rate': 0}
            
            # Run analyses
            book_analysis = self.orderbook_analyzer.analyze(order_book)
            pressure = self.pressure_calculator.calculate_pressure(order_book, trades, price)
            trend = self.trend_analyzer.analyze(
                hist_data.get('closes', []),
                hist_data.get('highs', []),
                hist_data.get('lows', []),
                hist_data.get('closes', [])
            )
            volume = self.volume_analyzer.analyze(hist_data.get('volumes', []), trades)
            whales = self.whale_detector.detect(order_book, trades, price)
            
            # Build result
            self.current_analysis = self._build_analysis_result(
                price, mark_data, book_analysis, pressure, trend, volume, whales
            )
            
            # Update dashboard
            self.dashboard.update(self.current_analysis)
            
            # Render and update UI - FIXED: Directly pass the rendered Layout
            try:
                rendered = self.dashboard.render()
                # Textual can handle Layout objects directly
                self.query_one("#dashboard").update(rendered)
                self._update_count += 1
                self.logger.info(f"Dashboard updated #{self._update_count}")
            except Exception as e:
                self.logger.error(f"Render error: {e}")
                self.query_one("#dashboard").update(f"[red]Error: {str(e)[:100]}[/red]")
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            self.query_one("#dashboard").update(f"[red]Error: {str(e)[:100]}[/red]")
    
    async def _get_order_book(self) -> Dict[str, Any]:
        """Get order book."""
        if self.config.use_websocket and not self.no_ws:
            book = self.ws_handler.get_order_book(self.symbol)
            if book and book.is_initialized():
                return book.get_depth(min(100, self.config.orderbook.depth))
        
        return await self.binance_client.normalize_depth(
            self.symbol, min(100, self.config.orderbook.depth)
        )
    
    def _get_current_price(self, order_book: Dict[str, Any]) -> float:
        """Get current price."""
        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        if bids and asks:
            return (bids[0][0] + asks[0][0]) / 2
        return self.historical.get_latest_price()
    
    async def _get_mark_data(self) -> Dict[str, Any]:
        """Get mark price."""
        try:
            data = await self.binance_client.get_premium_index(self.symbol)
            return {
                'mark_price': data.get('markPrice', 0),
                'funding_rate': data.get('lastFundingRate', 0)
            }
        except:
            return {'mark_price': 0, 'funding_rate': 0}
    
    def _build_analysis_result(self, price, mark_data, book, pressure, trend, volume, whales):
        """Build result."""
        trend_score = trend.get('score', 50)
        pressure_imbalance = pressure.get('imbalance', 0)
        whale_score = whales.get('score', 50)
        
        bias_score = (trend_score * 0.3 + (50 + pressure_imbalance) * 0.4 + whale_score * 0.3)
        
        if bias_score > 60:
            bias = "BULLISH"
            confidence = int(min(100, (bias_score - 50) * 2 + 50))
        elif bias_score < 40:
            bias = "BEARISH"
            confidence = int(min(100, (50 - bias_score) * 2 + 50))
        else:
            bias = "NEUTRAL"
            confidence = 50
        
        return {
            'symbol': self.symbol,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'engine': self.engine,
            'current_price': price,
            'mark_price': mark_data.get('mark_price', 0),
            'funding_rate': mark_data.get('funding_rate', 0),
            'open_interest': 0,
            'price_history': self.historical.get_price_history(100),
            'order_book': {**book, **pressure},
            'trend': trend,
            'volume': volume,
            'whales': whales,
            'summary': {'bias': bias, 'confidence': confidence}
        }
    
    async def _on_depth_update(self, data): pass
    async def _on_trade_update(self, data): pass
    async def _on_ws_error(self, data): 
        self.logger.error(f"WS error: {data}")
    
    async def on_key(self, event) -> None:
        """Handle keys."""
        key = event.key.lower()
        if key == "q":
            self._running = False
            await self.ws_handler.stop()
            await self.binance_client.close()
            await self.historical.close()
            self.exit()
        elif key == "r":
            await self._run_analysis()
        elif key == "p":
            self._paused = not self._paused
            self.logger.info(f"Paused: {self._paused}")