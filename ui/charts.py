"""Chart rendering using simple text-based charts (no plotext dependency for stability)."""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import math

# Fix imports - absolute imports
from utils.helpers import format_price, format_pct
from utils.logger import get_logger


class ChartRenderer:
    """Renders charts for the terminal UI using simple text-based methods."""
    
    def __init__(self, theme=None):
        """Initialize chart renderer."""
        self.logger = get_logger("charts")
        self.theme = theme
    
    def render_candlestick(self, prices: List[Dict], width: int = 80, 
                          height: int = 20) -> str:
        """
        Render a simple text-based candlestick chart.
        
        Args:
            prices: List of price data with 'open', 'high', 'low', 'close'
            width: Chart width in characters
            height: Chart height in characters
        
        Returns:
            String representation of the chart
        """
        if not prices:
            return "No data available"
        
        try:
            # Extract data with validation
            opens = []
            highs = []
            lows = []
            closes = []
            
            for p in prices:
                try:
                    opens.append(float(p.get('open', 0)))
                    highs.append(float(p.get('high', 0)))
                    lows.append(float(p.get('low', 0)))
                    closes.append(float(p.get('close', 0)))
                except (ValueError, TypeError):
                    continue
            
            if not opens or len(opens) < 2:
                return "Insufficient valid candlestick data"
            
            # Create simple OHLC text representation
            result = []
            result.append("📊 CANDLESTICK SUMMARY")
            result.append("=" * 50)
            
            # Show last 20 candles
            display_count = min(20, len(opens))
            start_idx = len(opens) - display_count
            
            for i in range(start_idx, len(opens)):
                idx = i - start_idx
                o = opens[i]
                h = highs[i]
                l = lows[i]
                c = closes[i]
                
                # Determine if bullish or bearish
                if c >= o:
                    direction = "🟢"
                else:
                    direction = "🔴"
                
                # Create simple bar
                bar_len = 20
                normalized = (c - min(opens)) / (max(opens) - min(opens) + 0.001)
                bar = "█" * int(normalized * bar_len)
                
                result.append(f"{idx+1:2d} {direction} O:{format_price(o, 2)} H:{format_price(h, 2)} L:{format_price(l, 2)} C:{format_price(c, 2)}")
            
            result.append("=" * 50)
            result.append(f"Total Candles: {len(opens)} | Latest: {format_price(closes[-1], 2)}")
            
            return "\n".join(result)
            
        except Exception as e:
            self.logger.error(f"Candlestick chart failed: {e}")
            return f"Chart error: {str(e)[:50]}..."
    
    def render_line(self, prices: List[float], title: str = "Price", 
                   width: int = 80, height: int = 20, 
                   show_points: bool = True) -> str:
        """
        Render a simple text-based sparkline chart.
        
        Args:
            prices: List of price values
            title: Chart title
            width: Chart width in characters
            height: Chart height in characters
        
        Returns:
            String representation of the chart
        """
        if not prices:
            return "No data available"
        
        try:
            # Clean and validate prices
            clean_prices = []
            for p in prices:
                try:
                    val = float(p)
                    if not math.isnan(val) and not math.isinf(val) and val > 0:
                        clean_prices.append(val)
                except (ValueError, TypeError):
                    continue
            
            if len(clean_prices) < 2:
                return "Insufficient valid price data"
            
            # Get min and max
            min_price = min(clean_prices)
            max_price = max(clean_prices)
            price_range = max_price - min_price
            
            if price_range == 0:
                return f"💰 {title}: {format_price(clean_prices[0], 2)} (flat)"
            
            # Sparkline characters
            spark_chars = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
            
            # Show last 80 prices for sparkline
            display_prices = clean_prices[-80:] if len(clean_prices) > 80 else clean_prices
            
            # Create sparkline
            sparkline = ""
            for p in display_prices:
                normalized = (p - min_price) / price_range
                idx = int(normalized * 7)
                idx = min(7, max(0, idx))
                sparkline += spark_chars[idx]
            
            # Create result
            result = []
            result.append(f"📈 {title}")
            result.append("=" * 50)
            result.append(f"[green]{sparkline}[/green]")
            result.append("=" * 50)
            result.append(f"Min: [green]{format_price(min_price, 2)}[/green]")
            result.append(f"Max: [green]{format_price(max_price, 2)}[/green]")
            result.append(f"Current: [bold green]{format_price(clean_prices[-1], 2)}[/bold green]")
            result.append(f"Change: [{'green' if clean_prices[-1] > clean_prices[0] else 'red'}]{format_pct(((clean_prices[-1] - clean_prices[0]) / clean_prices[0]) * 100)}[/{'green' if clean_prices[-1] > clean_prices[0] else 'red'}]")
            result.append(f"[dim]Bars: {len(display_prices)} / {len(clean_prices)} total[/dim]")
            
            return "\n".join(result)
            
        except Exception as e:
            self.logger.error(f"Line chart failed: {e}")
            return f"Chart error: {str(e)[:50]}..."
    
    def render_depth_curve(self, bids: List[List[float]], 
                          asks: List[List[float]],
                          width: int = 80, height: int = 20) -> str:
        """
        Render simple text-based depth curve.
        
        Args:
            bids: Bid levels [[price, qty], ...]
            asks: Ask levels [[price, qty], ...]
            width: Chart width in characters
            height: Chart height in characters
        
        Returns:
            String representation of the depth curve
        """
        if not bids or not asks:
            return "No depth data available"
        
        try:
            # Clean and validate data
            bid_prices = []
            bid_qtys = []
            for b in bids:
                try:
                    price = float(b[0])
                    qty = float(b[1])
                    if price > 0 and qty > 0:
                        bid_prices.append(price)
                        bid_qtys.append(qty)
                except (ValueError, TypeError):
                    continue
            
            ask_prices = []
            ask_qtys = []
            for a in asks:
                try:
                    price = float(a[0])
                    qty = float(a[1])
                    if price > 0 and qty > 0:
                        ask_prices.append(price)
                        ask_qtys.append(qty)
                except (ValueError, TypeError):
                    continue
            
            if not bid_prices or not ask_prices:
                return "Insufficient valid depth data"
            
            # Calculate cumulative depth
            cum_bid = []
            total_bid = 0
            for qty in reversed(bid_qtys[:20]):
                total_bid += qty
                cum_bid.append(total_bid)
            cum_bid.reverse()
            
            cum_ask = []
            total_ask = 0
            for qty in ask_qtys[:20]:
                total_ask += qty
                cum_ask.append(total_ask)
            
            result = []
            result.append("📊 ORDER BOOK DEPTH")
            result.append("=" * 50)
            
            # Show best levels
            if bid_prices:
                result.append(f"Best Bid: {format_price(bid_prices[0], 2)} | Qty: {format_qty(bid_qtys[0])}")
            if ask_prices:
                result.append(f"Best Ask: {format_price(ask_prices[0], 2)} | Qty: {format_qty(ask_qtys[0])}")
            
            # Show spread
            spread = ask_prices[0] - bid_prices[0] if bid_prices and ask_prices else 0
            spread_pct = (spread / bid_prices[0]) * 100 if bid_prices and spread > 0 else 0
            result.append(f"Spread: {format_price(spread, 4)} ({format_pct(spread_pct)})")
            
            # Show total depth
            result.append(f"Total Bid Depth: {format_notional(sum(bid_qtys[:20]))}")
            result.append(f"Total Ask Depth: {format_notional(sum(ask_qtys[:20]))}")
            
            # Imbalance
            total_bid_sum = sum(bid_qtys[:20])
            total_ask_sum = sum(ask_qtys[:20])
            if total_bid_sum + total_ask_sum > 0:
                imbalance = (total_bid_sum - total_ask_sum) / (total_bid_sum + total_ask_sum) * 100
                result.append(f"Imbalance: {format_pct(imbalance)}")
            
            result.append("=" * 50)
            result.append(f"[dim]Showing top 20 levels / {len(bid_prices)} bids, {len(ask_prices)} asks[/dim]")
            
            return "\n".join(result)
            
        except Exception as e:
            self.logger.error(f"Depth curve failed: {e}")
            return f"Depth chart error: {str(e)[:50]}..."
    
    def render_volume_bars(self, volumes: List[float], 
                          colors: Optional[List[str]] = None,
                          width: int = 80, height: int = 15) -> str:
        """
        Render simple text-based volume bars.
        
        Args:
            volumes: List of volume values
            colors: Optional list of colors for each bar
            width: Chart width in characters
            height: Chart height in characters
        
        Returns:
            String representation of volume bars
        """
        if not volumes:
            return "No volume data available"
        
        try:
            # Clean and validate volumes
            clean_volumes = []
            for v in volumes:
                try:
                    val = float(v)
                    if not math.isnan(val) and not math.isinf(val) and val >= 0:
                        clean_volumes.append(val)
                except (ValueError, TypeError):
                    continue
            
            if not clean_volumes:
                return "No valid volume data available"
            
            # Show last 30 volumes
            display_volumes = clean_volumes[-30:] if len(clean_volumes) > 30 else clean_volumes
            max_vol = max(display_volumes) if display_volumes else 1
            
            result = []
            result.append("📊 VOLUME BARS")
            result.append("=" * 50)
            
            # Create volume bars
            bar_width = 40
            for i, vol in enumerate(display_volumes[-20:]):  # Show last 20
                normalized = vol / max_vol if max_vol > 0 else 0
                bar_len = int(normalized * bar_width)
                bar = "█" * bar_len
                
                # Color based on volume
                if vol > max_vol * 0.8:
                    color = "red"
                elif vol > max_vol * 0.5:
                    color = "yellow"
                else:
                    color = "green"
                
                result.append(f"[{color}]{bar} {format_notional(vol)}[/{color}]")
            
            result.append("=" * 50)
            result.append(f"Current: [green]{format_notional(clean_volumes[-1])}[/green]")
            result.append(f"Average: [dim]{format_notional(sum(clean_volumes) / len(clean_volumes))}[/dim]")
            result.append(f"Peak: [yellow]{format_notional(max_vol)}[/yellow]")
            result.append(f"[dim]Bars: {len(display_volumes)} / {len(clean_volumes)} total[/dim]")
            
            return "\n".join(result)
            
        except Exception as e:
            self.logger.error(f"Volume bars failed: {e}")
            return f"Volume chart error: {str(e)[:50]}..."
    
    def render_pressure_bars(self, buy_pct: float, sell_pct: float, 
                            width: int = 40) -> str:
        """
        Render pressure bars as text.
        
        Args:
            buy_pct: Buying pressure percentage
            sell_pct: Selling pressure percentage
            width: Total width of the bar
        
        Returns:
            String representation of pressure bars
        """
        try:
            # Convert to float and validate
            try:
                buy_pct = float(buy_pct)
                sell_pct = float(sell_pct)
            except (ValueError, TypeError):
                buy_pct = 50.0
                sell_pct = 50.0
            
            # Clamp values
            buy_pct = max(0, min(100, buy_pct))
            sell_pct = max(0, min(100, sell_pct))
            
            # Normalize
            total = buy_pct + sell_pct
            if total > 0:
                buy_norm = buy_pct / total
                sell_norm = sell_pct / total
            else:
                buy_norm = 0.5
                sell_norm = 0.5
            
            buy_width = int(width * buy_norm)
            sell_width = int(width * sell_norm)
            
            # Adjust for rounding
            while buy_width + sell_width < width:
                if buy_norm >= sell_norm:
                    buy_width += 1
                else:
                    sell_width += 1
            
            buy_bar = '█' * buy_width
            sell_bar = '█' * sell_width
            
            # Color codes (will be rendered by Rich)
            return f"[green]{buy_bar}[/green][red]{sell_bar}[/red]"
            
        except Exception as e:
            self.logger.error(f"Pressure bars failed: {e}")
            return "░░░░░░░░░░░░░░░░░░░░"