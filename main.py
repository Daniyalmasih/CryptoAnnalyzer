#!/usr/bin/env python
"""Main entry point for CryptoAnalyzer."""
import sys
import os
import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import load_config, get_project_root
from utils.logger import setup_logger, get_logger, log_json_snapshot
from utils.helpers import format_timestamp
from data import BinanceClient, HistoricalData
from core import (
    OrderBookAnalyzer, PressureCalculator, TrendAnalyzer,
    VolumeAnalyzer, WhaleDetector
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="CryptoAnalyzer - Binance Futures Market Analysis Terminal"
    )
    parser.add_argument(
        "--symbol", "-s",
        default="BTCUSDT",
        help="Trading pair symbol (default: BTCUSDT)"
    )
    parser.add_argument(
        "--interval", "-i",
        default="5m",
        help="Timeframe interval (default: 5m)"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=1000,
        help="Order book depth (default: 1000)"
    )
    parser.add_argument(
        "--theme",
        default="terminal",
        help="UI theme (default: terminal)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one analysis cycle and exit"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON only (implies --once)"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save JSON output to file"
    )
    parser.add_argument(
        "--no-rust",
        action="store_true",
        help="Disable Rust engine (force Python fallback)"
    )
    parser.add_argument(
        "--no-ws",
        action="store_true",
        help="Disable WebSocket (use REST only)"
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=1000,
        help="Refresh interval in ms (default: 1000)"
    )
    parser.add_argument(
        "--list-symbols",
        action="store_true",
        help="List available symbols and exit"
    )
    parser.add_argument(
        "--config",
        help="Path to config file"
    )
    return parser.parse_args()


def check_engine(no_rust: bool = False) -> str:
    """Check which engine is available."""
    if no_rust:
        print("⚠️  Rust engine disabled by user flag")
        return "python"
    
    try:
        import crypto_rust_engine
        version = getattr(crypto_rust_engine, "__version__", "unknown")
        print(f"✅ Rust engine v{version} loaded successfully")
        return "rust"
    except ImportError as e:
        print(f"ℹ️  Rust engine not available: {e}")
        print("   Using Python fallback engine (slower)")
        return "python"
    except Exception as e:
        print(f"⚠️  Rust engine error: {e}")
        print("   Using Python fallback engine (slower)")
        return "python"


async def run_once_analysis(args):
    """Run a single analysis cycle and print results."""
    # Setup
    config = load_config(args.config)
    logger = get_logger()
    
    # Check engine
    engine = check_engine(args.no_rust)
    
    # Initialize clients
    client = BinanceClient(args.config)
    await client.start()
    
    historical = HistoricalData(args.symbol, args.interval, args.depth, args.config)
    await historical.fetch()
    
    # Initialize analyzers
    orderbook_analyzer = OrderBookAnalyzer(args.config)
    pressure_calculator = PressureCalculator(args.config)
    trend_analyzer = TrendAnalyzer(args.config)
    volume_analyzer = VolumeAnalyzer(args.config)
    whale_detector = WhaleDetector(args.config)
    
    try:
        # Get data
        order_book = await client.normalize_depth(args.symbol, args.depth)
        
        # Get price
        price = historical.get_latest_price()
        if price <= 0:
            price = await client.get_current_price(args.symbol)
        
        # Get mark data
        try:
            mark_data = await client.get_premium_index(args.symbol)
            mark_price = mark_data.get('markPrice', 0)
            funding_rate = mark_data.get('lastFundingRate', 0)
        except:
            mark_price = 0
            funding_rate = 0
        
        # Get trades
        try:
            trades = await client.get_agg_trades(args.symbol, 100)
        except:
            trades = []
        
        # Get historical data
        hist_data = historical.get_data()
        
        # Run analyses
        book_analysis = orderbook_analyzer.analyze(order_book)
        pressure = pressure_calculator.calculate_pressure(order_book, trades, price)
        trend = trend_analyzer.analyze(
            hist_data.get('closes', []),
            hist_data.get('highs', []),
            hist_data.get('lows', []),
            hist_data.get('closes', [])
        )
        volume = volume_analyzer.analyze(
            hist_data.get('volumes', []),
            trades
        )
        whales = whale_detector.detect(order_book, trades, price)
        
        # Build result
        # Determine overall bias
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
        
        note_parts = []
        if trend.get('label') != 'NEUTRAL':
            note_parts.append(trend.get('label', '').lower())
        if pressure.get('direction') != 'NEUTRAL':
            note_parts.append(f"{pressure.get('direction', '').lower()} pressure")
        if whales.get('bias') != 'NEUTRAL':
            note_parts.append(f"whale {whales.get('bias', '').lower()}")
        
        note = ", ".join(note_parts) if note_parts else "Market is balanced"
        
        result = {
            'symbol': args.symbol,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'engine': engine,
            'current_price': price,
            'mark_price': mark_price,
            'funding_rate': funding_rate,
            'open_interest': 0,
            'order_book': {**book_analysis, **pressure},
            'trend': trend,
            'volume': volume,
            'whales': whales,
            'summary': {
                'bias': bias,
                'confidence': confidence,
                'note': note
            }
        }
        
        # Output
        if args.json:
            print(json.dumps(result, indent=2))
        
        if args.save:
            log_json_snapshot(result, f"analysis_{args.symbol}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
            print(f"✅ Saved analysis to logs/")
        
        if not args.json:
            # Pretty print summary
            print("\n" + "="*60)
            print(f"🔷 CRYPTOANALYZER - {args.symbol}")
            print("="*60)
            print(f"📊 Price: ${price:,.2f}")
            print(f"📈 Trend: {trend.get('label', 'NEUTRAL')} (Confidence: {trend.get('confidence', 0)}%)")
            print(f"⚖️  Pressure: Buy {pressure.get('buying_pressure', 50):.1f}% / Sell {pressure.get('selling_pressure', 50):.1f}%")
            print(f"📊 Volume: {volume.get('status', 'NORMAL')} ({format_volume(volume.get('current', 0))})")
            print(f"🐋 Whales: {whales.get('count', 0)} detected, Bias: {whales.get('bias', 'NEUTRAL')}")
            print(f"🎯 Summary: {bias} (Confidence: {confidence}%)")
            print(f"💡 {note}")
            print("="*60)
            print(f"⚙️  Engine: {engine.upper()}")
            print(f"🔄 Refreshed: {format_timestamp(datetime.utcnow())}")
            print("="*60)
    
    finally:
        await client.close()
        await historical.close()


def format_volume(value: float) -> str:
    """Format volume with appropriate suffix."""
    if value >= 1_000_000:
        return f"{value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"{value/1_000:.2f}K"
    else:
        return f"{value:.2f}"


def list_symbols():
    """List available symbols from config."""
    try:
        config_path = Path(__file__).parent.parent / 'config' / 'symbols.json'
        if config_path.exists():
            with open(config_path, 'r') as f:
                data = json.load(f)
            watchlist = data.get('watchlist', [])
            print("\n📋 Available Symbols:")
            print("-" * 40)
            for item in watchlist:
                symbol = item.get('symbol', '')
                name = item.get('display_name', '')
                category = item.get('category', '')
                print(f"  {symbol:10} {name:15} [{category}]")
            print("-" * 40)
            print(f"Total: {len(watchlist)} symbols")
        else:
            print("❌ symbols.json not found")
    except Exception as e:
        print(f"❌ Error loading symbols: {e}")


def setup_windows_event_loop():
    """Configure Windows event loop policy if needed."""
    if sys.platform == 'win32':
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except:
            pass


def main():
    """Main entry point."""
    args = parse_args()
    
    # Setup logging
    setup_logger()
    logger = get_logger()
    
    # Setup Windows event loop
    setup_windows_event_loop()
    
    # List symbols if requested
    if args.list_symbols:
        list_symbols()
        return 0
    
    # Once mode
    if args.once or args.json:
        return asyncio.run(run_once_analysis(args))
    
    # TUI mode
        # TUI mode
    try:
        print("🚀 Starting CryptoAnalyzer Terminal...")
        print(f"📊 Symbol: {args.symbol}")
        print(f"⚙️  Refresh: {args.refresh}ms")
        print("Press '?' for help, 'Q' to quit\n")
        
        from ui.terminal_app import TerminalApp
        
        # Override config with args
        config = load_config(args.config)
        config.default_symbol = args.symbol
        config.ui.refresh_interval_ms = args.refresh
        config.theme = args.theme
        config.use_rust = not args.no_rust
        config.use_websocket = not args.no_ws
        
        # Start app with no_ws flag
        app = TerminalApp(args.symbol, args.config, no_ws=args.no_ws)
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error: {e}")
        print("Check logs/cryptoanalyzer.log for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())