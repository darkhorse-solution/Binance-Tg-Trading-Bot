# utils/logger.py
import logging
import os
from datetime import datetime
from pathlib import Path


class Logger:
    """
    Logger class for the trading bot.
    """

    def __init__(self, name='trading_bot', log_level=logging.INFO, log_file=None):
        """
        Initialize the logger.

        Args:
            name (str): Logger name
            log_level (int): Logging level
            log_file (str, optional): Path to log file
        """
        self._logger = logging.getLogger(name)
        self._logger.setLevel(log_level)
        self._log_file = log_file
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up logging handlers for console and file if specified."""
        # Clear any existing handlers
        if self._logger.handlers:
            self._logger.handlers.clear()

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._logger.level)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)

        # Add console handler to logger
        self._logger.addHandler(console_handler)

        # Add file handler if log file is specified
        if self._log_file:
            # Create logs directory if it doesn't exist
            log_dir = os.path.dirname(self._log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # Create file handler
            file_handler = logging.FileHandler(self._log_file)
            file_handler.setLevel(self._logger.level)
            file_handler.setFormatter(formatter)

            # Add file handler to logger
            self._logger.addHandler(file_handler)

    def set_level(self, level):
        """
        Set the logging level.

        Args:
            level (int): Logging level
        """
        self._logger.setLevel(level)
        for handler in self._logger.handlers:
            handler.setLevel(level)

    def debug(self, message):
        """Log a debug message."""
        self._logger.debug(message)

    def info(self, message):
        """Log an info message."""
        self._logger.info(message)

    def warning(self, message):
        """Log a warning message."""
        self._logger.warning(message)

    def error(self, message):
        """Log an error message."""
        self._logger.error(message)

    def critical(self, message):
        """Log a critical message."""
        self._logger.critical(message)

    def exception(self, message):
        """Log an exception message with traceback."""
        self._logger.exception(message)


def create_trading_failures_logger():
    """
    Create a specialized logger for tracking trading failures.
    
    Returns:
        Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    Path(log_dir).mkdir(exist_ok=True)
    
    log_file = os.path.join(log_dir, "trading_failures.log")
    
    # Create a custom logger
    failures_logger = logging.getLogger("trading_failures")
    failures_logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    if failures_logger.handlers:
        failures_logger.handlers.clear()
    
    # Create handlers
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - TRADING FAILURE - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Add handlers to logger
    failures_logger.addHandler(file_handler)
    
    return failures_logger


def create_profit_logger():
    """
    Create a specialized logger for tracking trade profits.
    
    Returns:
        Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    Path(log_dir).mkdir(exist_ok=True)
    
    log_file = os.path.join(log_dir, "trade_profits.log")
    
    # Create a custom logger
    profit_logger = logging.getLogger("trade_profits")
    profit_logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    if profit_logger.handlers:
        profit_logger.handlers.clear()
    
    # Create handlers
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - TRADE RESULT - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Add handlers to logger
    profit_logger.addHandler(file_handler)
    
    return profit_logger


# Import configuration for log settings
from utils.config import Config

# Create logger instances
logger = Logger(
    name='trading_bot',
    log_level=Config.get_log_level(),
    log_file=Config.LOG_FILE
)

# Initialize the specialized loggers
trading_failures_logger = create_trading_failures_logger()
profit_logger = create_profit_logger()