"""
CloudVerse Google Drive Bot - Logging Configuration Module

This module provides a comprehensive, professional logging system for the
CloudVerse Bot application. It implements centralized logging with multiple
handlers, custom formatters, and specialized loggers for different components.

Key Features:
- Centralized logging configuration for consistent behavior
- Multiple log handlers (console, file, rotating file)
- Color-coded console output for better readability
- Component-specific loggers (security, database, drive, etc.)
- Automatic log rotation to prevent disk space issues
- Configurable log levels via environment variables
- Professional log formatting with timestamps and context

Logging Architecture:
1. Console Handler: Real-time colored output for development
2. File Handler: Persistent logging to files for production
3. Rotating File Handler: Automatic log rotation for long-running instances
4. Component Loggers: Specialized loggers for different modules

Log Categories:
- General Application Logs: Overall bot operation and flow
- Security Logs: Access control, authentication, and security events
- Database Logs: Database operations, queries, and transactions
- Drive Logs: Google Drive API interactions and file operations
- Error Logs: Exception handling and error tracking

Usage:
    from .Logger import get_logger
    logger = get_logger(__name__)
    logger.info("Application started")

Author: CloudVerse Team
License: Open Source
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime
from .config import LOG_LEVEL

# ============================================================================
# LOGGING DIRECTORY AND CONFIGURATION SETUP
# ============================================================================

# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Define log levels mapping for easy configuration
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

# ============================================================================
# CUSTOM FORMATTERS - Enhanced log formatting with colors and context
# ============================================================================

class ColoredFormatter(logging.Formatter):
    """
    Custom log formatter that adds color coding to console output.
    
    This formatter enhances the readability of console logs by applying
    different colors to different log levels. It maintains the standard
    log format while adding visual distinction for easier debugging.
    
    Color Scheme:
        - DEBUG: Cyan (detailed debugging information)
        - INFO: Green (general information messages)
        - WARNING: Yellow (warning messages that need attention)
        - ERROR: Red (error messages indicating problems)
        - CRITICAL: Magenta (critical errors requiring immediate attention)
        
    Features:
        - ANSI color codes for terminal compatibility
        - Automatic color reset to prevent formatting issues
        - Fallback to standard formatting if colors aren't supported
        - Preserves all standard log record information
    """
    
    # ANSI color codes for different log levels
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan - for detailed debugging info
        'INFO': '\033[32m',       # Green - for general information
        'WARNING': '\033[33m',    # Yellow - for warnings
        'ERROR': '\033[31m',      # Red - for errors
        'CRITICAL': '\033[35m',   # Magenta - for critical issues
        'RESET': '\033[0m'        # Reset to default color
    }
    
    def format(self, record):
        """
        Format a log record with appropriate color coding.
        
        Args:
            record (LogRecord): The log record to format
            
        Returns:
            str: Formatted log message with color codes
        """
        # Apply color to the log level name
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        
        # Use parent formatter for the actual formatting
        formatted = super().format(record)
        return formatted

class CloudVerseLogger:
    """Centralized logger configuration for CloudVerse Bot"""
    
    _loggers = {}
    _configured = False
    
    @classmethod
    def setup_logging(cls):
        """Setup logging configuration once"""
        if cls._configured:
            return
            
        # Get log level from config
        log_level = LOG_LEVELS.get(LOG_LEVEL.upper(), logging.INFO)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        
        colored_formatter = ColoredFormatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(colored_formatter)
        root_logger.addHandler(console_handler)
        
        # Main log file handler (rotating)
        main_log_file = LOGS_DIR / "cloudverse_bot.log"
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        
        # Error log file handler
        error_log_file = LOGS_DIR / "errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=5*1024*1024,   # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(error_handler)
        
        # Database operations log
        db_log_file = LOGS_DIR / "database.log"
        db_handler = logging.handlers.RotatingFileHandler(
            db_log_file,
            maxBytes=5*1024*1024,   # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        db_handler.setLevel(logging.DEBUG)
        db_handler.setFormatter(detailed_formatter)
        
        # Add filter for database operations
        db_handler.addFilter(lambda record: 'database' in record.name.lower() or 'db' in record.name.lower())
        root_logger.addHandler(db_handler)
        
        # Upload operations log
        upload_log_file = LOGS_DIR / "uploads.log"
        upload_handler = logging.handlers.RotatingFileHandler(
            upload_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        upload_handler.setLevel(logging.INFO)
        upload_handler.setFormatter(detailed_formatter)
        
        # Add filter for upload operations
        upload_handler.addFilter(lambda record: any(keyword in record.name.lower() 
                                                  for keyword in ['upload', 'drive', 'file']))
        root_logger.addHandler(upload_handler)
        
        # Admin actions log
        admin_log_file = LOGS_DIR / "admin_actions.log"
        admin_handler = logging.handlers.RotatingFileHandler(
            admin_log_file,
            maxBytes=5*1024*1024,   # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        admin_handler.setLevel(logging.INFO)
        admin_handler.setFormatter(detailed_formatter)
        
        # Add filter for admin operations
        admin_handler.addFilter(lambda record: any(keyword in record.getMessage().lower() 
                                                 for keyword in ['admin', 'whitelist', 'blacklist', 'ban', 'promote']))
        root_logger.addHandler(admin_handler)
        
        cls._configured = True
        
        # Log the setup completion
        setup_logger = cls.get_logger('Logger')
        setup_logger.info(f"Logging system initialized with level: {LOG_LEVEL}")
        setup_logger.info(f"Log files location: {LOGS_DIR}")
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get a logger instance with the given name"""
        if not cls._configured:
            cls.setup_logging()
        
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            cls._loggers[name] = logger
        
        return cls._loggers[name]

# Convenience function for getting loggers
def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance. If name is None, uses the caller's module name."""
    if name is None:
        # Get the caller's module name
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return CloudVerseLogger.get_logger(name)

# Initialize logging on import
CloudVerseLogger.setup_logging()

# Create specialized loggers for different components
database_logger = get_logger('cloudverse.database')
upload_logger = get_logger('cloudverse.upload')
admin_logger = get_logger('cloudverse.admin')
drive_logger = get_logger('cloudverse.drive')
telegram_logger = get_logger('cloudverse.telegram')
security_logger = get_logger('cloudverse.security')

# Export commonly used loggers
__all__ = [
    'get_logger',
    'CloudVerseLogger',
    'database_logger',
    'upload_logger', 
    'admin_logger',
    'drive_logger',
    'telegram_logger',
    'security_logger'
]