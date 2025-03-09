# main.py
import asyncio
import sys

from trading.bot import TradingBot
from utils.config import Config
from utils.logger import logger


async def main():
    try:
        # Validate configuration
        config_errors = Config.validate()
        if config_errors:
            logger.error("Configuration errors detected:")
            for key, error in config_errors.items():
                logger.error(f"  - {key}: {error}")
            logger.error("Please check your .env file and restart the application.")
            sys.exit(1)

        # Initialize the trading bot with all required components
        trading_bot = TradingBot()

        # Start the bot
        logger.info('Starting Trading Bot...')
        await trading_bot.start()

        # Run until disconnected or interrupted
        logger.info('Bot running. Press Ctrl+C to stop.')
        await trading_bot.run()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as error:
        logger.error(f'Error in main function: {error}')
        raise error
    finally:
        if 'trading_bot' in locals():
            await trading_bot.stop()


if __name__ == "__main__":
    asyncio.run(main())