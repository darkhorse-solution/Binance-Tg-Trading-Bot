# trading/telegram_handler.py
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from utils.logger import logger
from typing import Dict, Any, Callable, Awaitable, Optional
import re


class TelegramHandler:
    """
    Handles Telegram messages processing and integration with trading system.
    """

    def __init__(self, client: TelegramClient, source_channel_id: int, target_channel_id: int):
        """
        Initialize the Telegram handler.

        Args:
            client (TelegramClient): Connected Telegram client
            source_channel_id (int): Channel ID to monitor for signals
            target_channel_id (int): Channel ID to forward processed signals
        """
        self.client = client
        self.source_channel_id = source_channel_id
        self.target_channel_id = target_channel_id
        self.signal_callback = None

    def register_signal_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        """
        Register a callback function to be called when a valid signal is received.

        Args:
            callback (Callable): Callback function that receives the signal dict
        """
        self.signal_callback = callback

    def setup_handlers(self):
        """Set up message handlers for the Telegram client."""

        @self.client.on(events.NewMessage(chats=[self.source_channel_id]))
        async def handle_new_message(event):
            """Handle new messages from the source channel."""
            if event.message.reply_to:
                # Ignore replied messages
                return

            message = event.message
            logger.info(f"New message received from channel {self.source_channel_id}")
            logger.debug(f"Message content: {message.text[:100]}...")

            # Process the message
            await self._process_message(message)

    async def _process_message(self, message):
        """
        Process a message to extract trading signals and forward if valid.

        Args:
            message: Telegram message object
        """
        try:
            # Check if this is likely a trading signal
            if not self._is_potential_signal(message.text):
                logger.info("Message does not appear to be a trading signal, ignoring")
                return

            # If we have a signal processor callback, use it
            if self.signal_callback:
                await self.signal_callback(message.text)

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _is_potential_signal(self, text: str) -> bool:
        """
        Check if a message appears to be a trading signal.

        Args:
            text (str): Message text

        Returns:
            bool: True if the message looks like a trading signal
        """
        # Check for common signal indicators
        signal_indicators = [
            r"(\w+)/(\w+)",  # Trading pair format (e.g., BTC/USDT)
            r"(long|short)",  # Position type
            r"\d+x",  # Leverage
            r"entry",  # Entry price
            r"tp\d+",  # Take profit
            r"target",  # Target
            r"stop loss|sl"  # Stop loss
        ]

        # Check if at least 3 indicators are present (to reduce false positives)
        matches = 0
        for pattern in signal_indicators:
            if re.search(pattern, text.lower()):
                matches += 1

        return matches >= 3

    async def send_formatted_signal(self, formatted_message: str) -> bool:
        """
        Send a formatted signal to the target channel.

        Args:
            formatted_message (str): Formatted message to send

        Returns:
            bool: True if message was sent successfully
        """
        try:
            await self.client.send_message(self.target_channel_id, formatted_message)
            logger.info(f"Sent formatted signal to channel {self.target_channel_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending formatted signal: {e}")
            return False