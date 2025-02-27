import asyncio
from utils.logger import logger
from telegram.client import create_client
from telegram.handler import setup_handlers


async def main():
    try:
        # Create and connect client
        client = await create_client()

        # Set up message handlers
        setup_handlers(client)

        logger.info('Listening for new messages...')
        await client.run_until_disconnected()

    except Exception as error:
        logger.error(f'Error in main function: {error}')
        raise error

    finally:
        if 'client' in locals() and client.is_connected():
            await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())