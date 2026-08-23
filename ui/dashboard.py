"""Rich-based dashboard layout for terminal UI."""
from typing import Dict, Any, Optional, List
from datetime import datetime
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
import math

from ui.theme import Theme
from utils.helpers import (
    format_price, format_notional, format_qty, format_pct,
    bar_string, format_timestamp
)
from utils.logger import get_logger


class Dashboard:
    """Main dashboard layout with all panels."""
    
    def __init__(self, theme: Optional[Theme] = None):
        self.logger = get_logger("dashboard")
        self.theme = theme or Theme.default_theme()
        self.analysis_result = None
        self.last_update = None
    
    def update(self, analysis_result: Dict[str, Any]) -> None:
        self.analysis_result = analysis_result
        self.last_update = datetime.utcnow()
    
    def render(self) -> Layout:
        """Render the full dashboard layout."""
        layout = Layout()
        
        layout.split(
            Layout(name="header", size=4),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        layout["body"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=3)
        )
        
        layout["left"].split(
            Layout(name="orderbook", size=15),
            Layout(name="pressure", size=8),
            Layout(name="trend", size=8),
            Layout(name="volume", size=8)
        )
        
        layout["right"].split(
            Layout(name="chart", size=20),
            Layout(name="whales", size=10),
            Layout(name="status", size=4)
        )
        
        layout["header"].update(self._render_header())
        layout["orderbook"].update(self._render_orderbook())
        layout["pressure"].update(self._render_pressure())
        layout["trend"].update(self._render_trend())
        layout["volume"].update(self._render_volume())
        layout["chart"].update(self._render_chart())
        layout["whales"].update(self._render_whales())
        layout["status"].update(self._render_status())
        layout["footer"].update(self._render_footer())
        
        return layout
    
    def _render_header(self) -> Panel:
        if not self.analysis_result:
            return Panel("Loading...", style="green on black")
        
        symbol = self.analysis_result.get('symbol', '---')
        price = self.analysis_result.get('current_price', 0)
        mark_price = self.analysis_result.get('mark_price', 0)
        funding = self.analysis_result.get('funding_rate', 0)
        oi = self.analysis_result.get('open_interest', 0)
        
        try:
            price = float(price) if price else 0
            mark_price = float(mark_price) if mark_price else 0
            funding = float(funding) if funding else 0
            oi = float(oi) if oi else 0
        except:
            price = 0
        
        header_text = Text()
        header_text.append(f"🔷 {symbol} ", style="bold green")
        header_text.append(f"Price: {format_price(price, 2)} ", style="bold bright_green")
        header_text.append(f"Mark: {format_price(mark_price, 2)} ", style="dim green")
        header_text.append(f"Funding: {format_pct(funding * 100)} ", style="yellow")
        header_text.append(f"OI: {format_notional(oi)}", style="dim green")
        
        return Panel(header_text, border_style="green", box=box.ROUNDED)
    
    def _render_orderbook(self) -> Panel:
        if not self.analysis_result:
            return Panel("Loading...", title="📊 Order Book", border_style="green")
        
        book_data = self.analysis_result.get('order_book', {})
        
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        table.add_column("Metric", style="green")
        table.add_column("Value", style="bright_green")
        
        try:
            best_bid = float(book_data.get('best_bid', 0))
            best_ask = float(book_data.get('best_ask', 0))
            spread = float(book_data.get('spread', 0))
            spread_pct = float(book_data.get('spread_pct', 0))
            total_bid = float(book_data.get('total_bid_qty', 0))
            total_ask = float(book_data.get('total_ask_qty', 0))
            imbalance = float(book_data.get('imbalance', 0))
        except:
            best_bid = 0
            best_ask = 0
            spread = 0
            spread_pct = 0
            total_bid = 0
            total_ask = 0
            imbalance = 0
        
        table.add_row("Best Bid", format_price(best_bid, 2))
        table.add_row("Best Ask", format_price(best_ask, 2))
        table.add_row("Spread", f"{spread:.4f} ({format_pct(spread_pct)})")
        table.add_row("Bid Depth", format_notional(total_bid))
        table.add_row("Ask Depth", format_notional(total_ask))
        table.add_row("Imbalance", format_pct(imbalance))
        
        support = book_data.get('support', [])
        resistance = book_data.get('resistance', [])
        
        if support:
            table.add_row("Support", ', '.join([format_price(float(s), 2) for s in support[:3] if s]))
        if resistance:
            table.add_row("Resistance", ', '.join([format_price(float(r), 2) for r in resistance[:3] if r]))
        
        return Panel(table, title="📊 Order Book", border_style="green")
    
    def _render_pressure(self) -> Panel:
        if not self.analysis_result:
            return Panel("Loading...", title="⚖️ Pressure", border_style="green")
        
        book_data = self.analysis_result.get('order_book', {})
        
        try:
            buy_pressure = float(book_data.get('buying_pressure', 50))
            sell_pressure = float(book_data.get('selling_pressure', 50))
            direction = book_data.get('predicted_direction', 'NEUTRAL')
            confidence = int(float(book_data.get('confidence', 0)))
            predicted = float(book_data.get('predicted_price', 0))
            reason = book_data.get('reason', '')
        except:
            buy_pressure = 50.0
            sell_pressure = 50.0
            direction = 'NEUTRAL'
            confidence = 0
            predicted = 0
            reason = ''
        
        content = []
        bar_width = 40
        buy_bar = bar_string(buy_pressure, 100, bar_width, '█', '░')
        sell_bar = bar_string(sell_pressure, 100, bar_width, '█', '░')
        
        content.append(f"[green]Buy:  {buy_bar} {format_pct(buy_pressure)}[/green]")
        content.append(f"[red]Sell: {sell_bar} {format_pct(sell_pressure)}[/red]")
        content.append("")
        
        if direction == 'UP':
            dir_color = "green"
            dir_symbol = "▲"
        elif direction == 'DOWN':
            dir_color = "red"
            dir_symbol = "▼"
        else:
            dir_color = "yellow"
            dir_symbol = "◆"
        
        content.append(f"[{dir_color}]{dir_symbol} Direction: {direction} (Confidence: {confidence}%)[/{dir_color}]")
        if predicted > 0:
            content.append(f"🎯 Target: {format_price(predicted, 2)}")
        if reason:
            content.append(f"[dim]💡 {reason[:80]}...[/dim]")
        
        return Panel("\n".join(content), title="⚖️ Buying Pressure", border_style="green")
    
    def _render_trend(self) -> Panel:
        if not self.analysis_result:
            return Panel("Loading...", title="📈 Trend", border_style="green")
        
        trend_data = self.analysis_result.get('trend', {})
        
        try:
            label = trend_data.get('label', 'NEUTRAL')
            score = float(trend_data.get('score', 50))
            confidence = int(float(trend_data.get('confidence', 0)))
            rsi = float(trend_data.get('rsi', 50))
            adx = float(trend_data.get('adx', 0))
        except:
            label = 'NEUTRAL'
            score = 50
            confidence = 0
            rsi = 50
            adx = 0
        
        content = []
        color = "green" if "UPTREND" in label else "red" if "DOWNTREND" in label else "yellow"
        content.append(f"[{color}]📊 {label}[/{color}]")
        content.append(f"Score: {score:.1f}/100")
        content.append(f"Confidence: {confidence}%")
        content.append(f"RSI: {rsi:.1f} | ADX: {adx:.1f}")
        bar = bar_string(score, 100, 20)
        content.append(f"[{color}]{bar}[/{color}]")
        
        return Panel("\n".join(content), title="📈 Trend Analysis", border_style="green")
    
    def _render_volume(self) -> Panel:
        if not self.analysis_result:
            return Panel("Loading...", title="📊 Volume", border_style="green")
        
        vol_data = self.analysis_result.get('volume', {})
        
        try:
            current = float(vol_data.get('current', 0))
            average = float(vol_data.get('average', 0))
            status = vol_data.get('status', 'NORMAL')
            direction = vol_data.get('direction', 'BALANCED')
            buy_pct = float(vol_data.get('buy_pct', 50))
            sell_pct = float(vol_data.get('sell_pct', 50))
            cvd = float(vol_data.get('cvd', 0))
        except:
            current = 0
            average = 0
            status = 'NORMAL'
            direction = 'BALANCED'
            buy_pct = 50
            sell_pct = 50
            cvd = 0
        
        content = []
        status_colors = {'VERY_HIGH': 'red', 'HIGH': 'yellow', 'NORMAL': 'green', 'LOW': 'dim', 'VERY_LOW': 'dim'}
        color = status_colors.get(status, 'green')
        content.append(f"Volume: [{color}]{status}[/{color}]")
        content.append(f"Current: {format_notional(current)}")
        content.append(f"Average: {format_notional(average)}")
        content.append(f"Ratio: {current/average:.2f}x" if average > 0 else "Ratio: N/A")
        content.append(f"Buy: {format_pct(buy_pct)} | Sell: {format_pct(sell_pct)}")
        dir_color = "green" if direction == "BUY_DOMINANT" else "red" if direction == "SELL_DOMINANT" else "yellow"
        content.append(f"Direction: [{dir_color}]{direction}[/{dir_color}]")
        cvd_color = "green" if cvd > 0 else "red" if cvd < 0 else "yellow"
        content.append(f"CVD: [{cvd_color}]{cvd:.2f}[/{cvd_color}]")
        
        return Panel("\n".join(content), title="📊 Volume Analysis", border_style="green")
    
    def _render_chart(self) -> Panel:
        if not self.analysis_result:
            return Panel("Loading...", title="📈 Chart", border_style="green")
        
        trend_data = self.analysis_result.get('trend', {})
        prices = trend_data.get('trend_line', [])
        
        if not prices:
            price_history = self.analysis_result.get('price_history', [])
            if price_history:
                prices = price_history
        
        clean_prices = []
        for p in prices:
            try:
                val = float(p)
                if not math.isnan(val) and not math.isinf(val) and val > 0:
                    clean_prices.append(val)
            except:
                continue
        
        if clean_prices and len(clean_prices) > 1:
            try:
                symbol = self.analysis_result.get('symbol', '')
                min_price = min(clean_prices)
                max_price = max(clean_prices)
                current = clean_prices[-1]
                
                spark_chars = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
                price_range = max_price - min_price if max_price > min_price else 1
                display_prices = clean_prices[-60:] if len(clean_prices) > 60 else clean_prices
                sparkline = ""
                for p in display_prices:
                    normalized = (p - min_price) / price_range
                    idx = int(normalized * 7)
                    idx = min(7, max(0, idx))
                    sparkline += spark_chars[idx]
                
                content = [
                    f"[green]📈 {symbol} Price Chart[/green]",
                    f"[dim]{sparkline}[/dim]",
                    f"Min: [green]{format_price(min_price, 2)}[/green]",
                    f"Max: [green]{format_price(max_price, 2)}[/green]",
                    f"Current: [bold green]{format_price(current, 2)}[/bold green]",
                    f"[dim]Bars: {len(display_prices)}[/dim]"
                ]
                return Panel("\n".join(content), title="📈 Price Chart", border_style="green")
            except Exception as e:
                return Panel(f"Chart error: {str(e)[:50]}...", title="📈 Chart", border_style="green")
        
        return Panel("No valid chart data", title="📈 Chart", border_style="green")
    
    def _render_whales(self) -> Panel:
        if not self.analysis_result:
            return Panel("Loading...", title="🐋 Whale Detection", border_style="green")
        
        whale_data = self.analysis_result.get('whales', {})
        
        if not whale_data.get('detected', False):
            return Panel("No whale activity detected", title="🐋 Whale Detection", border_style="green")
        
        content = []
        try:
            count = int(whale_data.get('count', 0))
            bias = whale_data.get('bias', 'NEUTRAL')
            strength = whale_data.get('strength', 'NONE')
            note = whale_data.get('note', '')
        except:
            count = 0
            bias = 'NEUTRAL'
            strength = 'NONE'
            note = ''
        
        bias_color = "green" if bias == "BUY" else "red" if bias == "SELL" else "yellow"
        content.append(f"Bias: [{bias_color}]{bias}[/{bias_color}]")
        content.append(f"Strength: {strength}")
        content.append(f"Count: {count}")
        
        bid_walls = whale_data.get('bid_walls', [])
        ask_walls = whale_data.get('ask_walls', [])
        
        if bid_walls:
            content.append(f"Bid Walls: {len(bid_walls)}")
        if ask_walls:
            content.append(f"Ask Walls: {len(ask_walls)}")
        if note:
            content.append(f"[dim]{note[:60]}...[/dim]")
        
        return Panel("\n".join(content), title="🐋 Whale Detection", border_style="green")
    
    def _render_status(self) -> Panel:
        if not self.analysis_result:
            return Panel("Status: Initializing...", border_style="green")
        
        summary = self.analysis_result.get('summary', {})
        bias = summary.get('bias', 'NEUTRAL')
        confidence = int(float(summary.get('confidence', 0))) if summary.get('confidence') else 0
        
        bias_color = "green" if bias == "BULLISH" else "red" if bias == "BEARISH" else "yellow"
        status_text = f"Bias: [{bias_color}]{bias}[/{bias_color}] | Confidence: {confidence}%"
        
        return Panel(status_text, border_style="green")
    
    def _render_footer(self) -> Panel:
        keybinds = "Q:Quit R:Refresh S:Symbol 1-5:TF W:Whales C:Chart E:Export P:Pause ?:Help"
        if self.last_update:
            footer = f"Last Update: {format_timestamp(self.last_update)} | {keybinds}"
        else:
            footer = keybinds
        return Panel(footer, border_style="green", box=box.SIMPLE)