# utils/config.py
import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv
import json
import logging

# Load environment variables from .env file
load_dotenv()


class Config:
    """
    Configuration class for the trading bot.
    Loads settings from environment variables and optional config file.
    """

    # Required Telegram settings
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    SESSION_STRING = os.getenv("SESSION_STRING", "")
    SOURCE_CHANNEL_ID = os.getenv("SOURCE_CHANNEL_ID", "")
    TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID", "")

    # Required Binance settings
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET_KEY = os.getenv("BINANCE_API_SECRET_KEY", "")

    # Optional risk management settings with defaults
    DEFAULT_RISK_PERCENT = float(os.getenv("DEFAULT_RISK_PERCENT", "2.0"))
    MAX_LEVERAGE = int(os.getenv("MAX_LEVERAGE", "20"))

    # Optional trading settings
    ENABLE_AUTO_SL = os.getenv("ENABLE_AUTO_SL", "true").lower() == "true"
    AUTO_SL_PERCENT = float(os.getenv("AUTO_SL_PERCENT", "5.0"))

    # Log settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "trading_bot.log")

    @classmethod
    def validate(cls) -> Dict[str, str]:
        """
        Validate that all required configuration is present.

        Returns:
            dict: Dictionary of missing or invalid configuration items
        """
        errors = {}

        # Check Telegram configuration
        if cls.API_ID == 0:
            errors["API_ID"] = "Missing or invalid Telegram API ID"
        if not cls.API_HASH:
            errors["API_HASH"] = "Missing Telegram API hash"
        if not cls.SOURCE_CHANNEL_ID:
            errors["SOURCE_CHANNEL_ID"] = "Missing source channel ID"
        if not cls.TARGET_CHANNEL_ID:
            errors["TARGET_CHANNEL_ID"] = "Missing target channel ID"

        # Check Binance configuration
        if not cls.BINANCE_API_KEY:
            errors["BINANCE_API_KEY"] = "Missing Binance API key"
        if not cls.BINANCE_API_SECRET_KEY:
            errors["BINANCE_API_SECRET_KEY"] = "Missing Binance API secret key"

        # Validate risk settings
        if cls.DEFAULT_RISK_PERCENT <= 0 or cls.DEFAULT_RISK_PERCENT > 10:
            errors["DEFAULT_RISK_PERCENT"] = "Risk percentage must be between 0.1 and 10"
        if cls.MAX_LEVERAGE <= 0 or cls.MAX_LEVERAGE > 125:
            errors["MAX_LEVERAGE"] = "Max leverage must be between 1 and 125"

        return errors

    @classmethod
    def get_log_level(cls) -> int:
        """
        Get the logging level from the configuration.

        Returns:
            int: Logging level constant
        """
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return levels.get(cls.LOG_LEVEL.upper(), logging.INFO)

    @classmethod
    def load_from_file(cls, filepath: str) -> None:
        """
        Load configuration from a JSON file.

        Args:
            filepath (str): Path to the configuration file
        """
        try:
            with open(filepath, 'r') as f:
                config_data = json.load(f)

            # Update class attributes from file
            for key, value in config_data.items():
                if hasattr(cls, key.upper()):
                    setattr(cls, key.upper(), value)

        except FileNotFoundError:
            print(f"Configuration file {filepath} not found, using environment variables")
        except json.JSONDecodeError:
            print(f"Error parsing configuration file {filepath}, using environment variables")

    @classmethod
    def as_dict(cls) -> Dict[str, Any]:
        """
        Return the configuration as a dictionary.

        Returns:
            dict: Configuration as a dictionary
        """
        return {
            key: value for key, value in cls.__dict__.items()
            if key.isupper() and not key.startswith('_')
        }