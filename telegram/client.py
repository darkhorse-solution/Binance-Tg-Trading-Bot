from telethon import TelegramClient
from telethon.sessions import StringSession
from utils.config import Config
from utils.logger import logger


async def create_client():
    """
    Create and connect to a Telegram client.

    Returns:
        TelegramClient: Connected Telegram client
    """
    logger.info('Initializing Telegram client...')
    print(Config.API_ID)

    client = TelegramClient(
        StringSession(Config.SESSION_STRING),
        Config.API_ID,
        Config.API_HASH,
        connection_retries=5,
        use_ipv6=True,
        timeout=30
    )

    logger.info('Connecting to Telegram...')
    await client.connect()

    if not await client.is_user_authorized():
        # Phone number authentication
        phone = input('Phone number (include country code, e.g., +1234567890): ')
        logger.info(f'Sending code to: {phone}')
        await client.send_code_request(phone)

        # Code verification
        code = input('Enter the code you received: ')
        await client.sign_in(phone, code)

        if await client.is_user_authorized():
            logger.info('Authentication successful!')
            session_string = client.session.save()
            logger.info(f'Your session string (save this): {session_string}')

    logger.info('Client setup complete')
    return client