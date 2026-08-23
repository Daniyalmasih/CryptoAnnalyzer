"""Configuration management with dataclass-based loading and deep merging."""
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, Union, List
from pathlib import Path


@dataclass
class OrderbookConfig:
    depth: int = 1000
    cluster_bps: int = 5
    refresh_ms: int = 1000


@dataclass
class WhaleConfig:
    wall_multiplier: float = 5.0
    min_notional: float = 500000.0
    min_ratio: float = 3.0
    cluster_radius_bps: int = 2


@dataclass
class TrendConfig:
    ema_fast: int = 12
    ema_slow: int = 26
    rsi_period: int = 14
    adx_period: int = 14
    strong_threshold: int = 70
    medium_threshold: int = 40
    weak_threshold: int = 20


@dataclass
class VolumeConfig:
    very_high_ratio: float = 2.0
    high_ratio: float = 1.5
    low_ratio: float = 0.7
    very_low_ratio: float = 0.4
    spike_multiplier: float = 2.0


@dataclass
class APIConfig:
    rest_url: str = "https://fapi.binance.com"
    ws_url: str = "wss://fstream.binance.com/stream"
    timeout_seconds: int = 10
    retry_attempts: int = 3
    backoff_seconds: int = 1


@dataclass
class LoggingConfig:
    level: str = "INFO"
    console: bool = True
    file: bool = True
    jsonl: bool = True
    max_bytes: int = 10485760
    backup_count: int = 5


@dataclass
class UIConfig:
    refresh_interval_ms: int = 1000
    max_chart_bars: int = 500
    max_tape_trades: int = 1000


@dataclass
class Config:
    default_symbol: str = "BTCUSDT"
    interval: str = "5m"
    orderbook: OrderbookConfig = field(default_factory=OrderbookConfig)
    whale: WhaleConfig = field(default_factory=WhaleConfig)
    trend: TrendConfig = field(default_factory=TrendConfig)
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    theme: str = "terminal"
    use_rust: bool = True
    use_websocket: bool = True
    api: APIConfig = field(default_factory=APIConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary with nested dataclasses expanded."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """Create Config from dictionary, handling nested dataclasses."""
        # Handle nested dataclasses
        for key, subcls in {
            'orderbook': OrderbookConfig,
            'whale': WhaleConfig,
            'trend': TrendConfig,
            'volume': VolumeConfig,
            'api': APIConfig,
            'logging': LoggingConfig,
            'ui': UIConfig
        }.items():
            if key in data and isinstance(data[key], dict):
                data[key] = subcls(**data[key])
        return cls(**data)


def get_project_root() -> Path:
    """Get the project root directory, handling PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys._MEIPASS)
    else:
        # Running as script
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / 'config').exists() and (parent / 'src').exists():
                return parent
        # Fallback to current directory
        return Path.cwd()


def load_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """
    Load configuration from JSON file, merging with defaults.
    
    Args:
        config_path: Path to config file. If None, uses config/settings.json.
    
    Returns:
        Config object with loaded settings merged with defaults.
    """
    if config_path is None:
        project_root = get_project_root()
        config_path = project_root / 'config' / 'settings.json'
    else:
        config_path = Path(config_path)
    
    # Start with default config
    config = Config()
    
    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Deep merge: update only keys that exist in loaded data
            config_dict = config.to_dict()
            _deep_merge(config_dict, data)
            config = Config.from_dict(config_dict)
    except Exception as e:
        print(f"Warning: Failed to load config from {config_path}: {e}")
        # Return defaults
    
    return config


def save_config(config: Config, config_path: Optional[Union[str, Path]] = None) -> None:
    """Save configuration to JSON file."""
    if config_path is None:
        project_root = get_project_root()
        config_path = project_root / 'config' / 'settings.json'
    else:
        config_path = Path(config_path)
    
    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """
    Deep merge two dictionaries.
    
    Args:
        base: Base dictionary to update (modified in place)
        override: Dictionary with values to override
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value