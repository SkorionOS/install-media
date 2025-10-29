"""
Unified logging utilities for the installer.
Provides consistent logging with timestamps, levels, and traceback support.
All output goes to stdout (captured by tee in installer-modular launcher).
"""

import sys
import traceback
from datetime import datetime
from typing import Optional


class InstallerLogger:
    """Simple logger that writes to stdout with timestamps and traceback support."""
    
    def __init__(self, component: str = 'installer'):
        self.component = component
    
    def _log(self, level: str, msg: str, exc_info: bool = False):
        """Internal logging method."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        full_msg = f"[{timestamp}] [{level}] [{self.component}] {msg}"
        print(full_msg, flush=True)
        
        if exc_info:
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
    
    def debug(self, msg: str):
        """Log debug message."""
        self._log('DEBUG', msg)
    
    def info(self, msg: str):
        """Log info message."""
        self._log('INFO', msg)
    
    def warning(self, msg: str):
        """Log warning message."""
        self._log('WARN', msg)
    
    def error(self, msg: str, exc_info: bool = True):
        """Log error message with optional traceback."""
        self._log('ERROR', msg, exc_info=exc_info)
    
    def exception(self, msg: str):
        """Log exception with full traceback (use in except blocks)."""
        self._log('ERROR', msg, exc_info=True)


def get_logger(component: str = 'installer') -> InstallerLogger:
    """Get logger instance for a component."""
    return InstallerLogger(component)

