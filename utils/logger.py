# utils/logger.py
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

def setup_logging(config):
    """
    Set up all loggers with a single configuration function
    """
    # Create logs directory
    log_dir = "logs"
    Path(log_dir).mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(config.get_log_level())
    
    # Console handler for all logs
    console_handler = logging.StreamHandler()
    console_handler.setLevel(config.get_log_level())
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Create specialized loggers with a single approach
    loggers = {
        'main': {
            'name': 'trading_bot',
            'file': os.path.join(log_dir, config.LOG_FILE or "trading_bot.log"),
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'failures': {
            'name': 'trading_failures',
            'file': os.path.join(log_dir, "trading_failures.log"),
            'format': '%(asctime)s - TRADING FAILURE - %(message)s'
        },
        'profits': {
            'name': 'trade_profits',
            'file': os.path.join(log_dir, "trade_profits.log"),
            'format': '%(asctime)s - TRADE RESULT - %(message)s'
        }
    }
    
    # Set up each logger
    configured_loggers = {}
    for key, cfg in loggers.items():
        logger = logging.getLogger(cfg['name'])
        logger.setLevel(config.get_log_level())
        
        # Add file handler
        file_handler = RotatingFileHandler(
            cfg['file'], 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(config.get_log_level())
        formatter = logging.Formatter(cfg['format'])
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        configured_loggers[key] = logger
    
    return configured_loggers

# Import configuration
from utils.config import Config

# Initialize all loggers at once
loggers = setup_logging(Config)

# Export the loggers for use in the application
logger = loggers['main']
trading_failures_logger = loggers['failures'] 
profit_logger = loggers['profits']