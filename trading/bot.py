# trading/bot.py
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from trading.signal import SignalParser, SignalFormatter
from trading.trader import BinanceTrader
from utils.logger import logger
from utils.config import Config


class TradingBot:
    """
    Main trading bot that integrates Telegram client and Binance trading.
    """

    def __init__(self):
        """
        Initialize the trading bot with all required components.

        Args:
            api_id (int): Telegram API ID
            api_hash (str): Telegram API hash
            session_string (str): Telegram session string for authentication
            binance_api_key (str): Binance API key
            binance_api_secret (str): Binance API secret
            source_channel_id (int): Channel ID to listen for signals
            target_channel_id (int): Channel ID to forward processed signals
        """
        self.api_id = Config.API_ID
        self.api_hash = Config.API_HASH
        self.session_string = Config.SESSION_STRING
        self.source_channel_id = int(Config.SOURCE_CHANNEL_ID)
        self.target_channel_id = int(Config.TARGET_CHANNEL_ID)

        # Initialize components
        self.client = None
        self.trader = BinanceTrader(Config.BINANCE_API_KEY, Config.BINANCE_API_SECRET_KEY, target_channel_id=self.target_channel_id if Config.ENABLE_FAILURE_NOTIFICATIONS else None)
        self.parser = SignalParser()
        self.formatter = SignalFormatter()

    async def start(self):
        """Start the Telegram client and set up handlers."""
        logger.info('Initializing Telegram client...')

        # Create and connect to Telegram
        self.client = TelegramClient(
            StringSession(self.session_string),
            self.api_id,
            self.api_hash,
            connection_retries=5,
            use_ipv6=True,
            timeout=30
        )

        await self.client.connect()
        await self._authenticate()
        
        # IMPORTANT: Set the telegram client in the trader here
        self.trader.set_telegram_client(self.client)
        self.trader.target_channel_id = self.target_channel_id  # Explicitly set target channel
        
        self._setup_handlers()
        logger.info('Bot started successfully')

    async def run(self):
        """Run the bot until disconnected."""
        await self.client.run_until_disconnected()

    async def stop(self):
        """Stop the bot and disconnect from Telegram."""
        if self.client and self.client.is_connected():
            logger.info('Disconnecting from Telegram...')
            await self.client.disconnect()
            logger.info('Disconnected')

    async def _authenticate(self):
        """Authenticate with Telegram if needed."""
        if not await self.client.is_user_authorized():
            # Phone number authentication
            phone = input('Phone number (include country code, e.g., +1234567890): ')
            logger.info(f'Sending code to: {phone}')
            await self.client.send_code_request(phone)

            # Code verification
            code = input('Enter the code you received: ')
            await self.client.sign_in(phone, code)

            if await self.client.is_user_authorized():
                logger.info('Authentication successful!')
                session_string = self.client.session.save()
                logger.info(f'Your session string (save this): {session_string}')
                
    def _setup_handlers(self):
        """Set up message handlers for the Telegram client."""
        from utils.config import Config

        @self.client.on(events.NewMessage(chats=[self.source_channel_id]))
        async def handle_new_message(event):
            if event.message.reply_to:
                # Ignore replied messages
                return

            message = event.message
            logger.info(f"New message received: {message.text[:50]}...")

            # Parse the signal
            signal = self.parser.parse(message.text)

            if signal:
                # Format the signal for readability
                formatted_message = self.formatter.format(signal)

                # Execute trading orders
                await self._execute_trades(signal)

                # Send formatted message to target channel if not empty and entry notifications are disabled
                # This prevents duplicate messages when entry notifications are enabled
                if formatted_message and not Config.ENABLE_ENTRY_NOTIFICATIONS:
                    try:
                        await self.client.send_message(self.target_channel_id, formatted_message)
                        logger.info("Signal processed and forwarded successfully!")
                    except Exception as e:
                        logger.error(f"Error sending message: {e}")
            else:
                logger.info("Message received but not a valid trading signal")

    async def _execute_trades(self, signal):
        """
        Execute the trades based on the parsed signal.

        Args:
            signal (dict): Parsed trading signal
        """
        try:
            # Execute the trade with the signal data
            result = await self.trader.execute_signal(signal)
            logger.info(f"Trade execution result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error executing trades: {e}")
            return None