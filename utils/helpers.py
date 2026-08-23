"""Helper functions for formatting, calculations, and async utilities."""
import asyncio
import time
import math
from typing import Any, Callable, List, Optional, Union, Awaitable, TypeVar
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from pathlib import Path
import numpy as np


T = TypeVar('T')


def format_price(value: float, decimals: int = 2) -> str:
    """Format a price value with appropriate decimal places."""
    if value is None or math.isnan(value) or math.isinf(value):
        return "0.00"
    return f"{value:.{decimals}f}"


def format_notional(value: float) -> str:
    """Format notional value with K/M/B suffixes."""
    if value is None or math.isnan(value) or math.isinf(value):
        return "$0.00"
    
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"${value/1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif abs_val >= 1_000:
        return f"${value/1_000:.2f}K"
    else:
        return f"${value:.2f}"


def format_qty(value: float) -> str:
    """Format quantity with appropriate decimal places."""
    if value is None or math.isnan(value) or math.isinf(value):
        return "0"
    
    if abs(value) >= 1000:
        return f"{value:.1f}"
    elif abs(value) >= 1:
        return f"{value:.2f}"
    elif abs(value) >= 0.01:
        return f"{value:.4f}"
    else:
        return f"{value:.8f}"


def format_pct(value: float) -> str:
    """Format percentage value."""
    if value is None or math.isnan(value) or math.isinf(value):
        return "0.0%"
    return f"{value:.1f}%"


def bar_string(value: float, max_value: float = 100, width: int = 20, 
               fill_char: str = '█', empty_char: str = '░') -> str:
    """
    Create a horizontal bar string.
    
    Args:
        value: Current value
        max_value: Maximum value for scaling
        width: Total width in characters
        fill_char: Character for filled portion
        empty_char: Character for empty portion
    
    Returns:
        String representation of the bar
    """
    if max_value <= 0:
        return empty_char * width
    
    ratio = max(0, min(1, value / max_value))
    filled = int(ratio * width)
    remaining = width - filled
    
    return fill_char * filled + empty_char * remaining


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = value.replace(',', '')
            return float(value)
        if isinstance(value, Decimal):
            return float(value)
        return default
    except (ValueError, TypeError):
        return default


def calculate_ema(values: List[float], period: int) -> List[float]:
    """
    Calculate Exponential Moving Average.
    
    Args:
        values: List of values
        period: EMA period
    
    Returns:
        List of EMA values (same length as input, first period-1 values are NaN)
    """
    if not values or period <= 0:
        return []
    
    result = [float('nan')] * len(values)
    if len(values) < period:
        return result
    
    # Calculate SMA for first period
    sma = sum(values[:period]) / period
    result[period - 1] = sma
    
    # Multiplier
    multiplier = 2.0 / (period + 1)
    
    # Calculate EMA
    for i in range(period, len(values)):
        result[i] = (values[i] - result[i-1]) * multiplier + result[i-1]
    
    return result


def calculate_sma(values: List[float], period: int) -> List[float]:
    """
    Calculate Simple Moving Average.
    
    Args:
        values: List of values
        period: SMA period
    
    Returns:
        List of SMA values (same length as input, first period-1 values are NaN)
    """
    if not values or period <= 0:
        return []
    
    result = [float('nan')] * len(values)
    if len(values) < period:
        return result
    
    for i in range(period - 1, len(values)):
        result[i] = sum(values[i - period + 1:i + 1]) / period
    
    return result


def calculate_rsi(values: List[float], period: int = 14) -> List[float]:
    """
    Calculate Relative Strength Index.
    
    Args:
        values: List of values
        period: RSI period
    
    Returns:
        List of RSI values (same length as input, first period values are NaN)
    """
    if not values or period <= 0 or len(values) < period + 1:
        return [float('nan')] * len(values)
    
    result = [float('nan')] * len(values)
    
    # Calculate gains and losses
    gains = []
    losses = []
    
    for i in range(1, len(values)):
        diff = values[i] - values[i-1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    
    # Initial average
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))
    
    # Smooth averages for remaining periods
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            result[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i + 1] = 100.0 - (100.0 / (1.0 + rs))
    
    return result


def calculate_adx(high: List[float], low: List[float], close: List[float], 
                  period: int = 14) -> List[float]:
    """
    Calculate Average Directional Index.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ADX period
    
    Returns:
        List of ADX values
    """
    n = len(high)
    if n < period + 1:
        return [float('nan')] * n
    
    result = [float('nan')] * n
    
    # Calculate +DM and -DM
    plus_dm = [0.0] * (n - 1)
    minus_dm = [0.0] * (n - 1)
    tr = [0.0] * (n - 1)
    
    for i in range(n - 1):
        high_diff = high[i + 1] - high[i]
        low_diff = low[i] - low[i + 1]
        
        if high_diff > low_diff and high_diff > 0:
            plus_dm[i] = high_diff
        else:
            plus_dm[i] = 0.0
            
        if low_diff > high_diff and low_diff > 0:
            minus_dm[i] = low_diff
        else:
            minus_dm[i] = 0.0
        
        tr[i] = max(high[i + 1] - low[i + 1],
                   abs(high[i + 1] - close[i]),
                   abs(low[i + 1] - close[i]))
    
    # Smooth with Wilder's method
    atr = [0.0] * (n - 1)
    atr[period - 1] = sum(tr[:period]) / period
    
    plus_di = [0.0] * (n - 1)
    minus_di = [0.0] * (n - 1)
    
    plus_smooth = sum(plus_dm[:period])
    minus_smooth = sum(minus_dm[:period])
    
    for i in range(period, len(tr)):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
        plus_smooth = plus_smooth * (period - 1) / period + plus_dm[i]
        minus_smooth = minus_smooth * (period - 1) / period + minus_dm[i]
        
        if atr[i] != 0:
            plus_di[i] = 100.0 * plus_smooth / atr[i]
            minus_di[i] = 100.0 * minus_smooth / atr[i]
    
    # Calculate DX and ADX
    dx = [0.0] * n
    for i in range(period, len(plus_di)):
        if plus_di[i] + minus_di[i] != 0:
            dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i])
    
    # Smooth DX to get ADX
    if len(dx) > period + period:
        adx_values = [float('nan')] * n
        adx_smooth = sum(dx[period:period + period]) / period
        adx_values[period + period - 1] = adx_smooth
        
        for i in range(period + period, len(dx)):
            adx_smooth = (adx_smooth * (period - 1) + dx[i]) / period
            adx_values[i] = adx_smooth
        
        return adx_values
    
    return result


def calculate_atr(high: List[float], low: List[float], close: List[float], 
                  period: int = 14) -> List[float]:
    """
    Calculate Average True Range.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period
    
    Returns:
        List of ATR values
    """
    n = len(high)
    if n < period + 1:
        return [float('nan')] * n
    
    tr = [0.0] * (n - 1)
    for i in range(n - 1):
        tr[i] = max(high[i + 1] - low[i + 1],
                   abs(high[i + 1] - close[i]),
                   abs(low[i + 1] - close[i]))
    
    atr = [float('nan')] * n
    atr[period] = sum(tr[:period]) / period
    
    for i in range(period, len(tr)):
        atr[i + 1] = (atr[i] * (period - 1) + tr[i]) / period
    
    return atr


def calculate_stddev(values: List[float], period: int = 20) -> float:
    """Calculate standard deviation of values."""
    if not values or len(values) < period:
        return 0.0
    
    recent = values[-period:]
    return float(np.std(recent) if recent else 0.0)


def format_timestamp(dt: Union[datetime, float]) -> str:
    """Format a datetime or timestamp as ISO string."""
    if isinstance(dt, (int, float)):
        dt = datetime.utcfromtimestamp(dt)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


# ============ RETRY DECORATOR - FIXED ============
def retry_async(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator for async functions with retry logic.
    
    Usage:
        @retry_async(max_attempts=3, delay=1.0, backoff=2.0)
        async def my_function():
            ...
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay in seconds
        backoff: Backoff multiplier
    
    Returns:
        Decorated async function
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator


async def rate_limit_async(func, *args, **kwargs):
    """
    Simple rate limiter wrapper for async functions.
    
    Args:
        func: Async function to call
        *args: Positional arguments
        **kwargs: Keyword arguments
    
    Returns:
        Result of the function call
    """
    return await func(*args, **kwargs)


class RateLimiter:
    """Async rate limiter with token bucket."""
    
    def __init__(self, rate: float, per: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            rate: Number of requests allowed per period
            per: Period in seconds
        """
        self.rate = rate
        self.per = per
        self.tokens = rate
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens += elapsed * (self.rate / self.per)
            
            if self.tokens > self.rate:
                self.tokens = self.rate
            
            self.last_refill = now
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (self.per / self.rate)
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


def ensure_dir_exists(path: Union[str, Path]) -> None:
    """Ensure a directory exists, creating it if necessary."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)