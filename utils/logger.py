"""Logging setup and JSONL snapshot writer."""
import logging
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any
import traceback
import numpy as np


def setup_logger(name: str = 'cryptoanalyzer', level: Optional[str] = None) -> logging.Logger:
    """
    Set up console and file logging.
    
    Args:
        name: Logger name
        level: Log level string (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Configured Logger instance
    """
    if level is None:
        # Try to get from config, fallback to INFO
        try:
            from .config import load_config
            config = load_config()
            level = config.logging.level
        except:
            level = 'INFO'
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers = []  # Clear existing handlers
    
    # Console handler with color
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    
    # Simple format for console (colors handled by Rich elsewhere)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console.setFormatter(console_format)
    logger.addHandler(console)
    
    # File handler
    try:
        from .config import get_project_root
        project_root = get_project_root()
        log_dir = project_root / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / 'cryptoanalyzer.log'
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10_485_760,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not set up file logging: {e}")
    
    return logger


def get_logger(name: str = 'cryptoanalyzer') -> logging.Logger:
    """Get or create a logger instance."""
    return logging.getLogger(name)


def _convert_to_json_serializable(obj: Any) -> Any:
    """
    Convert numpy types and other non-JSON-serializable objects to JSON-serializable types.
    """
    if obj is None:
        return None
    if isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {key: _convert_to_json_serializable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_convert_to_json_serializable(item) for item in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def log_json_snapshot(data: Dict[str, Any], filename: Optional[str] = None) -> None:
    """
    Write a JSON snapshot to the logs directory as a .jsonl entry.
    
    Args:
        data: Dictionary containing the snapshot data
        filename: Optional custom filename. If None, uses date-based naming.
    """
    try:
        from .config import get_project_root
        
        project_root = get_project_root()
        log_dir = project_root / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.utcnow().strftime('%Y%m%d')
            filename = f'snapshots_{timestamp}.jsonl'
        elif not filename.endswith('.jsonl') and not filename.endswith('.json'):
            filename += '.jsonl'
        
        filepath = log_dir / filename
        
        # Add timestamp if not present
        if 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        
        # Convert numpy types to JSON-serializable
        serializable_data = _convert_to_json_serializable(data)
        
        with open(filepath, 'a', encoding='utf-8') as f:
            json.dump(serializable_data, f, ensure_ascii=False)
            f.write('\n')
    except Exception as e:
        logger = get_logger()
        logger.error(f"Failed to write JSON snapshot: {e}")