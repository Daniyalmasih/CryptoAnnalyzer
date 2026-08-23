"""Theme management for terminal UI."""
import json
from typing import Dict, Any, Optional
from pathlib import Path

# Fix imports - absolute imports
from utils.config import get_project_root
from utils.logger import get_logger


class Theme:
    """UI theme with colors and styles."""
    
    def __init__(self, theme_data: Dict[str, Any]):
        """Initialize theme from data."""
        self.name = theme_data.get('name', 'terminal')
        self.colors = theme_data.get('colors', {})
        self.styles = theme_data.get('styles', {})
        self.textual_css = theme_data.get('textual_css', [])
    
    def get_color(self, name: str, default: str = '#00ff00') -> str:
        """Get a color by name."""
        return self.colors.get(name, default)
    
    def get_style(self, name: str, default: str = 'green on black') -> str:
        """Get a style by name."""
        return self.styles.get(name, default)
    
    def get_textual_css(self) -> str:
        """Get Textual CSS as a single string."""
        return '\n'.join(self.textual_css)
    
    @classmethod
    def load(cls, theme_name: str = 'terminal') -> 'Theme':
        """Load a theme by name."""
        try:
            project_root = get_project_root()
            theme_path = project_root / 'assets' / 'themes' / f'{theme_name}.json'
            
            if theme_path.exists():
                with open(theme_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return cls(data)
        except Exception as e:
            logger = get_logger()
            logger.warning(f"Failed to load theme {theme_name}: {e}")
        
        # Return default theme
        return cls.default_theme()
    
    @classmethod
    def default_theme(cls) -> 'Theme':
        """Get default terminal theme."""
        return cls({
            'name': 'terminal',
            'colors': {
                'background': '#000000',
                'foreground': '#00ff00',
                'highlight': '#00ff00',
                'dim': '#006600',
                'bright': '#00ff44',
                'error': '#ff0000',
                'warning': '#ffff00',
                'success': '#00ff00',
                'info': '#00ccff',
                'panel_border': '#00ff00',
                'panel_bg': '#001100',
                'header_bg': '#003300',
                'footer_bg': '#001100'
            },
            'styles': {
                'header': 'bold green on black',
                'subheader': 'dim green on black',
                'value': 'bright_green on black',
                'label': 'green on black',
                'positive': 'bright_green on black',
                'negative': 'bright_red on black',
                'neutral': 'yellow on black',
                'warning': 'yellow on black',
                'error': 'red on black',
                'panel_border': 'green on black',
                'chart': 'green on black'
            },
            'textual_css': [
                '.app { background: #000000; color: #00ff00; }',
                '.header { background: #003300; color: #00ff00; }',
                '.panel { border: solid #00ff00; background: #001100; }',
                '.panel-title { color: #00ff00; }',
                '.footer { background: #001100; color: #006600; }',
                '.positive { color: #00ff44; }',
                '.negative { color: #ff0044; }',
                '.neutral { color: #ffff00; }',
                'ScrollView { scrollbar-background: #003300; scrollbar-color: #00ff00; }'
            ]
        })


def load_theme(theme_name: str = 'terminal') -> 'Theme':
    """Load a theme by name."""
    return Theme.load(theme_name)