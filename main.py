import asyncio

from trading.trades import BinanceTrader
from utils.config import Config
from utils.logger import logger
from telegram.client import create_client
from telegram.handler import setup_handlers

async def main():
    try:
        BINANCE_API_KEY = Config.BINANCE_API_KEY
        BINANCE_API_SECRET_KEY = Config.BINANCE_API_SECRET_KEY
        # Create and connect client
        tg_client = await create_client()
        binance_trader = BinanceTrader(BINANCE_API_KEY, BINANCE_API_SECRET_KEY)

        # Set up message handlers
        setup_handlers(tg_client, binance_trader)

        logger.info('Listening for new messages...')
        await tg_client.run_until_disconnected()

    except Exception as error:
        logger.error(f'Error in main function: {error}')
        raise error

    finally:
        if 'client' in locals() and tg_client.is_connected():
            await tg_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())