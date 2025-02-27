from telethon import events
from utils.config import Config
from utils.logger import logger
from trading.parser import parse_trading_signal
from trading.formatter import format_trading_signal


def setup_handlers(client):
    """
    Set up message handlers for the Telegram client.

    Args:
        client: The Telegram client
    """

    @client.on(events.NewMessage(chats=[Config.SOURCE_CHANNEL_ID]))
    async def handle_new_message(event):
        if event.message.reply_to:
            # Ignore replied messages
            return

        message = event.message
        logger.info(f"New message received: {message.text[:50]}...")

        signal = parse_trading_signal(message.text)

        if signal:
            formatted_message = format_trading_signal(signal)

            # Send formatted message to target channel
            try:
                await client.send_message(Config.TARGET_CHANNEL_ID, formatted_message)
                logger.info("Signal processed and forwarded successfully!")
            except Exception as e:
                logger.error(f"Error sending message: {e}")
        else:
            logger.info("Message received but not a valid trading signal")