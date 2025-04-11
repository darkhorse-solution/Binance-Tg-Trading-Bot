import math
import asyncio
import time
import json
import os
from datetime import datetime, timedelta
from binance.client import Client
from utils.logger import logger, trading_failures_logger, profit_logger
from typing import Dict, List, Optional, Any, Tuple
from trading.risk import RiskManager
from utils.config import Config
from trading.symbol_mapper import SymbolMapper
import re


class BinanceTrader:
    """
    Class for interacting with Binance API to execute trades.
    """

    def __init__(self, api_key: str, api_secret: str,
                 default_risk_percent: float = 2.0, max_leverage: int = 20,
                 target_channel_id: int = None):
        """
        Initialize the Binance trader with API credentials.

        Args:
            api_key (str): Binance API key
            api_secret (str): Binance API secret
            default_risk_percent (float): Default percentage of account to risk per trade
            max_leverage (int): Maximum leverage to use
            target_channel_id (int, optional): Channel ID for notifications
        """
        self.client = Client(api_key, api_secret)

        # Initialize risk manager
        self.risk_manager = RiskManager(default_risk_percent, max_leverage)

        # Initialize symbol mapper with rate adjustment support
        self.symbol_mapper = SymbolMapper()

        # Caches for API data
        self._symbol_info_cache = {}
        self._leverage_cache = {}

        # Reference to Telegram client for notifications
        self.telegram_client = None
        self.target_channel_id = target_channel_id
        
        # Constants
        self.default_max_leverage = max_leverage

        # Dictionary to track ongoing monitoring tasks
        self._monitor_tasks = {}

        # Trading state tracking (for symbol mapping)
        self._active_trades = {}  # To track original symbol, mapped symbol, and rate

        # Initialize caches with common symbols at startup
        self._prefetch_common_symbols()
        self._prefetch_leverage_info()

    def _prefetch_common_symbols(self):
        """Prefetch information for common trading pairs to avoid API rate limits."""
        try:
            exchange_info = self.client.get_exchange_info()

            # Focus on futures symbols for leveraged trading
            for symbol_info in exchange_info['symbols'][:20]:  # Limit to top 20 to avoid rate limits
                symbol = symbol_info['symbol']
                self._symbol_info_cache[symbol] = symbol_info

            logger.info(f"Prefetched {len(self._symbol_info_cache)} common symbols")
        except Exception as e:
            logger.warning(f"Failed to prefetch symbols: {e}")
            
    def _prefetch_leverage_info(self):
        """Prefetch leverage information for common futures symbols."""
        try:
            # Get all leverage brackets at once to reduce API calls
            all_brackets = self.client.futures_leverage_bracket()
            
            # Process and cache the results
            for item in all_brackets:
                symbol = item['symbol']
                if 'brackets' in item and len(item['brackets']) > 0:
                    max_leverage = item['brackets'][0]['initialLeverage']
                    self._leverage_cache[symbol] = max_leverage
                    
            logger.info(f"Prefetched leverage info for {len(self._leverage_cache)} symbols")
        except Exception as e:
            logger.warning(f"Failed to prefetch leverage info: {e}")

    def set_telegram_client(self, client):
        """
        Set the Telegram client for sending notifications.
        
        Args:
            client: Telegram client instance
        """
        self.telegram_client = client

    async def handle_trading_failure(self, symbol: str, message: str, error: Exception, original_signal: str):
        """
        Handle a trading failure by logging and sending notification.
        
        Args:
            symbol (str): The trading symbol
            message (str): Description of the failure
            error (Exception): The exception that occurred
            original_signal (str): The original signal message
        """
        # Log to specialized logger
        error_msg = f"Symbol: {symbol}, Error: {str(error)}, Message: {message}"
        trading_failures_logger.error(error_msg)
        trading_failures_logger.info(f"Original signal: {original_signal}")
        
        # Send message to channel if client is available and notifications are enabled
        if self.telegram_client and self.target_channel_id and Config.ENABLE_FAILURE_NOTIFICATIONS:
            notification = (
                f"❌ TRADE EXECUTION FAILED\n\n"
                f"Pair: {symbol}\n"
                f"Reason: {message}\n"
                f"Error: {str(error)}\n\n"
                f"This trading signal could not be processed automatically."
            )
            
            try:
                await self.telegram_client.send_message(self.target_channel_id, notification)
                logger.info(f"Sent trading failure notification for {symbol}")
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")

    async def send_entry_message(self, symbol: str, position_type: str, leverage: int, 
                               entry_price: float, sl_price: float, tp_price: float,
                               position_size: float):
        """
        Send a message when a new position is entered.
        
        Args:
            symbol (str): Trading symbol
            position_type (str): 'LONG' or 'SHORT'
            leverage (int): Leverage used
            entry_price (float): Entry price
            sl_price (float): Stop loss price
            tp_price (float): Take profit price
            position_size (float): Position size
        """
        if not self.telegram_client or not self.target_channel_id or not Config.ENABLE_ENTRY_NOTIFICATIONS:
            logger.warning("Cannot send entry message: Telegram client or target channel not set, or notifications disabled")
            return
            
        try:
            # Calculate SL and TP percentages
            if position_type == 'LONG':
                sl_percent = ((entry_price - sl_price) / entry_price) * 100 * leverage
                tp_percent = ((tp_price - entry_price) / entry_price) * 100 * leverage
                emoji = "🟢"
            else:  # SHORT
                sl_percent = ((sl_price - entry_price) / entry_price) * 100 * leverage
                tp_percent = ((entry_price - tp_price) / entry_price) * 100 * leverage
                emoji = "🔴"
                
            # Format the message
            message = (
                f"{emoji} NEW TRADE ENTRY\n\n"
                f"Pair: {symbol}\n"
                f"Position: {position_type}\n"
                f"Leverage: {leverage}x\n"
                f"Entry Price: {entry_price:.4f}\n"
                f"Size: {position_size:.4f}\n\n"
                f"Stop Loss: {sl_price:.4f} ({sl_percent:.2f}%)\n"
                f"Take Profit: {tp_price:.4f} ({tp_percent:.2f}%)\n\n"
                f"#{position_type.lower()} #{symbol}"
            )
            
            # Send the message
            await self.telegram_client.send_message(self.target_channel_id, message)
            logger.info(f"Sent entry message for {symbol}")
            
        except Exception as e:
            logger.error(f"Error sending entry message: {e}")

    def get_symbol_info(self, symbol: str) -> Dict:
        """
        Get information about a trading symbol, using cache when possible.

        Args:
            symbol (str): The trading symbol

        Returns:
            dict: Symbol information
        """
        if symbol in self._symbol_info_cache:
            return self._symbol_info_cache[symbol]

        try:
            symbol_info = self.client.get_symbol_info(symbol)
            if symbol_info:
                self._symbol_info_cache[symbol] = symbol_info
            return symbol_info
        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None
            
    def get_max_leverage(self, symbol: str) -> int:
        """
        Get the maximum allowed leverage for a symbol.
        
        Args:
            symbol (str): The trading symbol
            
        Returns:
            int: Maximum allowed leverage, or 0 if not supported
        """
        # Check cache first
        if symbol in self._leverage_cache:
            return self._leverage_cache[symbol]
            
        try:
            # Try to get leverage brackets from Binance
            brackets = self.client.futures_leverage_bracket(symbol=symbol)
            
            # If we got a valid response, the symbol is supported
            if brackets and len(brackets) > 0 and 'brackets' in brackets[0]:
                # Get the maximum leverage from the first bracket
                max_lev = brackets[0]['brackets'][0]['initialLeverage']
                self._leverage_cache[symbol] = max_lev
                logger.info(f"Maximum leverage for {symbol}: {max_lev}x")
                return max_lev
                
            return 0
        except Exception as e:
            # If we get an error, the symbol might not be supported
            logger.warning(f"Failed to get leverage info for {symbol}: {e}")
            self._leverage_cache[symbol] = 0
            return 0

    def get_price_precision(self, symbol):
        """
        Get the allowed price precision for the symbol.
        :param symbol: Trading pair symbol.
        :return: Allowed price precision.
        """
        try:
            info = self.client.futures_exchange_info()

            for item in info['symbols']:
                if item['symbol'] == symbol:
                    for f in item['filters']:
                        if f['filterType'] == 'PRICE_FILTER':
                            return int(round(-math.log(float(f['tickSize']), 10), 0))
        except Exception as e:
            logger.error(f'get_price_precision {e}')
            return None
        
    def get_balance_in_quote(self, quote_symbol):
        """
        Get balance of specific symbol in future account.
        :param quote_symbol: Symbol ex: USDT
        :return: balance of symbol
        """
        try:
            balances = self.client.futures_account_balance()

            for b in balances:
                if b['asset'] == quote_symbol.upper():
                    return float(b['balance'])

        except Exception as e:
            logger.error(f"{e}, get_balance_in_quote")

    def get_precise_quantity(self, symbol, quantity):
        """
        Get correct quantity with specific symbol and quantity by stepSize in filter => LOT_SIZE not PRICE_FILTER
        :param symbol: current symbol
        :param quantity: quantity
        :return: correct quantity by
        """
        try:
            info = self.client.futures_exchange_info()

            for item in info['symbols']:
                if item['symbol'] == symbol:
                    for f in item['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            step_size = float(f['stepSize'])
                            break

            precision = int(round(-math.log(step_size, 10), 0))
            quantity = float(round(quantity, precision))

            return quantity

        except Exception as e:
            logger.error(f'get_precise_quantity {e}')
            return None

    def get_last_price(self, pair):
        """
        Get latest symbol price
        :param pair: currencies pair  ex: BNBUSDT
        :return: currency of price by USDT: example
        """
        try:
            prices = self.client.futures_symbol_ticker()

            for price in prices:
                if price['symbol'] == pair:
                    return float(price['price'])

        except Exception as e:
            logger.error(f'get_last_price {e}')

    def calculate_coin_amount_to_buy(self, pair, leverage):
        """
        Calculate coin amount based on either wallet ratio or constant amount,
        depending on configuration setting.
        
        Args:
            pair (str): coin symbol pair ex: BNBUSDT
            leverage (int): leverage value
            
        Returns:
            tuple: (coin_amount, coin_price)
        """
        try:
            QUOTE_ASSET = Config.QUOTE_ASSET
            trading_mode = Config.TRADING_MODE.lower()
            
            if trading_mode == "fixed":
                # Fixed amount mode
                CONSTANT_AMOUNT = Config.CONSTANT_AMOUNT
                amount_to_trade_in_quote = CONSTANT_AMOUNT * leverage - 2
                logger.info(f"Using fixed amount mode: {CONSTANT_AMOUNT} {QUOTE_ASSET}")
            else:
                # Wallet ratio mode (default)
                WALLET_RATIO = Config.WALLET_RATIO
                account_balance = self.get_balance_in_quote(QUOTE_ASSET)
                amount_to_trade_in_quote = ((account_balance / 100) * WALLET_RATIO) * leverage - 2
                logger.info(f"Using wallet ratio mode: {WALLET_RATIO}% of {account_balance} {QUOTE_ASSET}")

            coin_price = self.get_last_price(pair)
            coin_amount = amount_to_trade_in_quote / coin_price
            coin_amount = self.get_precise_quantity(pair, coin_amount)
            logger.info(f"Amount to buy: {coin_amount} × {leverage} × {coin_price}")
            return coin_amount, coin_price

        except Exception as e:
            logger.error(f'calculate_coin_amount_to_buy {e}')
            raise e

    async def _create_entry_order(self, symbol: str, side: str,
                                  quantity: float, price: float) -> Dict:
        """
        Create an entry order (limit or market).

        Args:
            symbol (str): Trading symbol
            side (str): SIDE_BUY or SIDE_SELL
            quantity (float): Order quantity
            price (float): Order price

        Returns:
            dict: Order response
        """
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",  # Use correct string constant
                quantity=quantity,
            )

            logger.info(f"Created entry order for {symbol}, {side} at {price}: {order['orderId']}")
            return order

        except Exception as e:
            logger.error(f"Error creating entry order: {e}")
            return {"error": str(e)}

    async def _create_stop_loss_order(self, symbol: str, side: str,
                                      quantity: float, leverage: int, entry_price: float, sl_percent: float) -> Dict:
        """
        Create a stop loss order.

        Args:
            symbol (str): Trading symbol
            side (str): SIDE_BUY or SIDE_SELL (opposite of entry order)
            quantity (float): Order quantity
            leverage (int): Leverage used
            entry_price (float): Entry price
            sl_percent (float): Stop loss percentage

        Returns:
            dict: Order response
        """
        price_precision = self.get_price_precision(symbol)
        if side == 'BUY':
            sl_price = entry_price * (leverage - sl_percent / 100) / leverage
        else:
            sl_price = entry_price * (leverage + sl_percent / 100) / leverage
        sl_price = round(sl_price, price_precision)

        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side='SELL' if side == 'BUY' else 'BUY',
                type="STOP_MARKET",
                stopPrice=sl_price,
                closePosition=True  # Close the entire position
            )

            logger.info(f"Created stop loss order for {symbol} at {sl_price}: {order['orderId']}")
            return order

        except Exception as e:
            logger.error(f"Error creating stop loss order: {e}")
            return {"error": str(e)}

    async def _create_take_profit_order(self, symbol: str, side: str,
                                        quantity: float, leverage, entry_price, tp_percent) -> Dict:
        """
        Create a take profit order.

        Args:
            symbol (str): Trading symbol
            side (str): SIDE_BUY or SIDE_SELL (opposite of entry order)
            quantity (float): Order quantity
            leverage (int): Leverage used
            entry_price (float): Entry price
            tp_percent (float): Take profit percentage

        Returns:
            dict: Order response
        """
        price_precision = self.get_price_precision(symbol)
        if side == 'BUY':
            tp_price = entry_price * (leverage + tp_percent / 100) / leverage
        else:
            tp_price = entry_price * (leverage - tp_percent / 100) / leverage

        tp_price = round(tp_price, price_precision)

        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side='SELL' if side == 'BUY' else 'BUY',
                type="TAKE_PROFIT_MARKET",
                stopPrice=tp_price,
                closePosition=True  # Close the entire position
            )

            logger.info(f"Created take profit order for {symbol} at {tp_price}: {order['orderId']}")
            return order

        except Exception as e:
            logger.error(f"Error creating take profit order: {e}")
            return {"error": str(e)}

    async def close_position(self, symbol: str) -> Dict:
        """
        Close any open position for a symbol immediately.
        
        Args:
            symbol (str): The trading symbol
            
        Returns:
            dict: Result of the operation
        """
        result = {
            'success': False,
            'message': '',
            'order': None
        }
        
        try:
            # Get current position information
            position_info = self.client.futures_position_information(symbol=symbol)
            
            # Find the position for this symbol with non-zero amount
            position = next((p for p in position_info if p['symbol'] == symbol and float(p['positionAmt']) != 0), None)
            
            if not position:
                result['success'] = True
                result['message'] = f"No open position found for {symbol}"
                return result
                
            # Determine side for market order (opposite of current position)
            position_amt = float(position['positionAmt'])
            side = "SELL" if position_amt > 0 else "BUY"
            
            # Create market order to close position
            close_order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=abs(position_amt),
                reduceOnly=True  # Important: ensures we only reduce positions
            )
            
            result['success'] = True
            result['message'] = f"Successfully closed position for {symbol}"
            result['order'] = close_order
            
            logger.info(f"Closed position for {symbol}: {position_amt}")
            return result
            
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            result['success'] = False
            result['message'] = f"Failed to close position: {str(e)}"
            return result

    async def cancel_all_open_orders(self, symbol: str) -> Dict:
        """
        Cancel all open orders for a symbol.
        
        Args:
            symbol (str): The trading symbol
            
        Returns:
            dict: Result with status and details
        """
        result = {
            'success': False,
            'message': '',
            'canceled_orders': []
        }
        
        try:
            # Get all open orders for the symbol
            open_orders = self.client.futures_get_open_orders(symbol=symbol)
            
            if not open_orders:
                result['success'] = True
                result['message'] = f"No open orders found for {symbol}"
                return result
                
            # Cancel all orders
            cancel_result = self.client.futures_cancel_all_open_orders(symbol=symbol)
            
            result['success'] = True
            result['message'] = f"Successfully canceled {len(open_orders)} orders for {symbol}"
            result['canceled_orders'] = [order['orderId'] for order in open_orders]
            result['api_response'] = cancel_result
            
            logger.info(f"Canceled {len(open_orders)} orders for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Error canceling orders for {symbol}: {e}")
            result['success'] = False
            result['message'] = f"Failed to cancel orders: {str(e)}"
            return result

    async def calculate_profit(self, symbol: str, entry_price: float, exit_price: float, position_size: float, position_type: str, leverage: int) -> Dict:
        """
        Calculate profit or loss from a trade.
        
        Args:
            symbol (str): Trading symbol
            entry_price (float): Entry price
            exit_price (float): Exit price
            position_size (float): Position size
            position_type (str): 'LONG' or 'SHORT'
            leverage (int): Leverage used
            
        Returns:
            dict: Profit details including absolute and percentage values
        """
        try:
            # Calculate absolute profit in quote currency
            if position_type == 'LONG':
                price_diff_percent = ((exit_price / entry_price) - 1) * 100
                percentage_profit = price_diff_percent * leverage
                absolute_profit = (exit_price - entry_price) * position_size
            else:  # SHORT
                price_diff_percent = ((entry_price / exit_price) - 1) * 100
                percentage_profit = price_diff_percent * leverage
                absolute_profit = (entry_price - exit_price) * position_size
                
            return {
                'absolute_profit': absolute_profit,
                'percentage_profit': percentage_profit,
                'leveraged_percentage': percentage_profit,
                'price_diff_percent': price_diff_percent,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'position_size': position_size,
                'symbol': symbol,
                'position_type': position_type,
                'leverage': leverage
            }
            
        except Exception as e:
            logger.error(f"Error calculating profit: {e}")
            return {
                'absolute_profit': 0,
                'percentage_profit': 0,
                'error': str(e)
            }

    async def send_profit_message(self, profit_data: Dict):
        """
        Send profit result message to the channel.
        
        Args:
            profit_data (dict): Profit calculation details
        """
        if not self.telegram_client or not self.target_channel_id or not Config.ENABLE_PROFIT_NOTIFICATIONS:
            logger.warning("Cannot send profit message: Telegram client or target channel not set, or notifications disabled")
            return
            
        try:
            # Format profit/loss indicator and emoji
            if profit_data['absolute_profit'] > 0:
                result_type = "PROFIT"
                emoji = "🟢"
            else:
                result_type = "LOSS"
                emoji = "🔴"
                
            # Format the exit type
            exit_type = profit_data.get('exit_type', 'unknown')
            if exit_type == 'take_profit':
                exit_description = "TAKE PROFIT"
            elif exit_type == 'stop_loss':
                exit_description = "STOP LOSS"
            elif exit_type == 'manual_or_liquidation':
                exit_description = "MANUAL OR LIQUIDATION"
            else:
                exit_description = "UNKNOWN"
                
            # Use display values if available
            display_symbol = profit_data.get('display_symbol', profit_data['symbol'])
            entry_price = profit_data.get('display_entry_price', profit_data['entry_price'])
            exit_price = profit_data.get('display_exit_price', profit_data['exit_price'])
                
            # Format the message
            message = (
                f"{emoji} TRADE {result_type} - {exit_description}\n\n"
                f"Pair: {display_symbol}\n"
                f"Position: {profit_data['position_type']}\n"
                f"Leverage: {profit_data['leverage']}x\n"
                f"Entry: {entry_price:.4f}\n"
                f"Exit: {exit_price:.4f}\n"
                f"Size: {profit_data['position_size']:.4f}\n\n"
                f"P/L: {profit_data['absolute_profit']:.4f} USDT ({profit_data['leveraged_percentage']:.2f}%)\n"
                f"Raw Price Change: {profit_data['price_diff_percent']:.2f}%\n\n"
                f"#trade #{display_symbol} #{profit_data['position_type'].lower()} #{exit_type}"
            )
            
            # Send the message
            await self.telegram_client.send_message(self.target_channel_id, message)
            
            # Also log to the profit logger
            profit_logger.info(
                f"{display_symbol} {profit_data['position_type']} - {exit_description} - " +
                f"P/L: {profit_data['absolute_profit']:.4f} USDT ({profit_data['leveraged_percentage']:.2f}%)"
            )
            
            logger.info(f"Sent profit result message for {display_symbol}")
            
        except Exception as e:
            logger.error(f"Error sending profit message: {e}")

    async def monitor_order_execution(self, symbol: str, entry_order_id: int, sl_order_id: int, tp_order_id: int, 
                             entry_price: float, position_size: float, position_type: str, leverage: int,
                             original_symbol: str = None, rate_multiplier: float = 1.0):
        """
        Monitor order execution and clean up related orders when one gets triggered.
        Also sends profit result messages when the trade is completed.
        
        Args:
            symbol (str): The trading symbol
            entry_order_id (int): Entry order ID
            sl_order_id (int): Stop loss order ID
            tp_order_id (int): Take profit order ID
            entry_price (float): Entry price
            position_size (float): Position size
            position_type (str): 'LONG' or 'SHORT'
            leverage (int): Leverage used
            original_symbol (str, optional): Original symbol from signal
            rate_multiplier (float, optional): Rate multiplier used for price adjustment
        """
        # Use original symbol for display if provided, otherwise use actual symbol
        display_symbol = original_symbol if original_symbol else symbol
        
        try:
            # For positions that already exist, we don't need to check entry order
            check_entry = entry_order_id < 1000000000000  # If it's a real order ID, not our dummy timestamp
            
            if check_entry:
                # Wait for entry order to be filled
                entry_filled = False
                check_attempts = 0
                
                while not entry_filled and check_attempts < 6:  # Check for 3 minutes max
                    try:
                        order_status = self.client.futures_get_order(symbol=symbol, orderId=entry_order_id)
                        if order_status['status'] == 'FILLED':
                            entry_filled = True
                            
                            # Get actual filled price and quantity
                            try:
                                actual_entry_price = float(order_status['avgPrice'])
                                if actual_entry_price > 0:
                                    entry_price = actual_entry_price
                            except (KeyError, ValueError):
                                pass
                                
                            try:
                                actual_position_size = float(order_status['executedQty'])
                                if actual_position_size > 0:
                                    position_size = actual_position_size
                            except (KeyError, ValueError):
                                pass
                                
                            logger.info(f"Entry order {entry_order_id} filled at {entry_price}")
                        else:
                            await asyncio.sleep(30)
                            check_attempts += 1
                    except Exception as e:
                        logger.error(f"Error checking entry order: {e}")
                        await asyncio.sleep(30)
                        check_attempts += 1
                
                if not entry_filled:
                    logger.warning(f"Entry order {entry_order_id} not filled after timeout")
                    # Continue monitoring anyway, in case it gets filled later
            else:
                # For existing positions, consider entry already filled
                entry_filled = True
                logger.info(f"Monitoring existing position for {symbol} at {entry_price}")
                    
            # Monitor the position until it's closed
            position_closed = False
            exit_price = 0
            exit_type = "unknown"
            exit_processed = False
            
            # Dynamic sleep time management
            base_sleep_time = 20  # Start with 20 seconds between checks
            check_count = 0
            
            while not position_closed:
                # Adjust sleep time based on check count (max 2 minutes)
                sleep_time = min(base_sleep_time + (check_count // 5) * 10, 120)
                check_count += 1
                
                try:
                    # Check if SL order was filled
                    try:
                        sl_status = self.client.futures_get_order(symbol=symbol, orderId=sl_order_id)
                        if sl_status['status'] == 'FILLED' and not exit_processed:
                            position_closed = True
                            exit_type = "stop_loss"
                            exit_processed = True
                            
                            # Get the exit price
                            if 'avgPrice' in sl_status and float(sl_status['avgPrice']) > 0:
                                exit_price = float(sl_status['avgPrice'])
                            else:
                                exit_price = float(sl_status['stopPrice'])
                            
                            # Cancel TP order
                            try:
                                self.client.futures_cancel_order(symbol=symbol, orderId=tp_order_id)
                            except Exception as e:
                                logger.error(f"Error canceling TP after SL hit: {e}")
                    except Exception as e:
                        # If we can't check SL, it might be gone/filled
                        logger.warning(f"Could not check SL order {sl_order_id}: {e}")
                    
                    if position_closed:
                        break
                    
                    # Small pause between API calls
                    await asyncio.sleep(1)
                    
                    # Check if TP order was filled
                    try:
                        tp_status = self.client.futures_get_order(symbol=symbol, orderId=tp_order_id)
                        if tp_status['status'] == 'FILLED' and not exit_processed:
                            position_closed = True
                            exit_type = "take_profit"
                            exit_processed = True
                            
                            # Get the exit price
                            if 'avgPrice' in tp_status and float(tp_status['avgPrice']) > 0:
                                exit_price = float(tp_status['avgPrice'])
                            else:
                                exit_price = float(tp_status['stopPrice'])
                            
                            # Cancel SL order
                            try:
                                self.client.futures_cancel_order(symbol=symbol, orderId=sl_order_id)
                            except Exception as e:
                                logger.error(f"Error canceling SL after TP hit: {e}")
                    except Exception as e:
                        # If we can't check TP, it might be gone/filled
                        logger.warning(f"Could not check TP order {tp_order_id}: {e}")
                    
                    if position_closed:
                        break
                    
                    # Less frequent position check (once every 3 iterations)
                    if check_count % 3 == 0:
                        # Check if position still exists
                        try:
                            position_info = self.client.futures_position_information(symbol=symbol)
                            position = next((p for p in position_info if p['symbol'] == symbol 
                                            and float(p['positionAmt']) != 0), None)
                            
                            if not position and not exit_processed:
                                position_closed = True
                                exit_type = "manual_or_liquidation"
                                exit_processed = True
                                
                                # Get current price as exit price
                                try:
                                    exit_price = self.get_last_price(symbol)
                                except:
                                    exit_price = entry_price  # Fallback to entry price
                                
                                await self.cancel_all_open_orders(symbol)
                        except Exception as e:
                            logger.error(f"Error checking position: {e}")
                    
                    if not position_closed:
                        await asyncio.sleep(sleep_time)
                        
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(60)  # Sleep longer on error
            
            # Position is now closed, calculate and report profit
            if position_closed and exit_price > 0 and exit_processed:
                try:
                    # Calculate profit
                    profit_data = await self.calculate_profit(
                        symbol=symbol,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        position_size=position_size,
                        position_type=position_type,
                        leverage=leverage
                    )
                    
                    profit_data['exit_type'] = exit_type
                    
                    # For display, convert prices back to original if needed
                    if rate_multiplier != 1.0 and rate_multiplier > 0:
                        display_entry_price = entry_price / rate_multiplier
                        display_exit_price = exit_price / rate_multiplier
                        
                        # Update display prices but keep actual profit calculation
                        profit_data['display_symbol'] = display_symbol
                        profit_data['display_entry_price'] = display_entry_price
                        profit_data['display_exit_price'] = display_exit_price
                    else:
                        profit_data['display_symbol'] = display_symbol
                        profit_data['display_entry_price'] = entry_price
                        profit_data['display_exit_price'] = exit_price
                    
                    # Log profit details
                    profit_message = (
                        f"{display_symbol} {position_type} - {exit_type.upper()} - " +
                        f"Entry: {profit_data['display_entry_price']:.4f}, Exit: {profit_data['display_exit_price']:.4f}, " +
                        f"P/L: {profit_data['absolute_profit']:.4f} USDT ({profit_data['leveraged_percentage']:.2f}%)"
                    )
                    profit_logger.info(profit_message)
                    
                    # Always send profit message for any exit type
                    await self.send_profit_message(profit_data)
                    logger.info(f"Sent profit message for {exit_type} exit")
                    
                except Exception as e:
                    logger.error(f"Error processing profit result: {e}")
                    
            # Final cleanup
            try:
                await self.cancel_all_open_orders(symbol)
            except Exception as e:
                logger.error(f"Error in final order cleanup: {e}")
                
        except Exception as e:
            logger.error(f"Error in order execution monitor for {symbol}: {e}")

    def setup_order_monitor(self, symbol: str, entry_order_id: int, sl_order_id: int, tp_order_id: int,
                        entry_price: float, position_size: float, position_type: str, leverage: int,
                        original_symbol: str = None, rate_multiplier: float = 1.0):
        """
        Set up monitoring for order execution with support for symbol mapping and rate adjustment.
        
        Args:
            symbol (str): The actual trading symbol used
            entry_order_id (int): Entry order ID
            sl_order_id (int): Stop loss order ID
            tp_order_id (int): Take profit order ID
            entry_price (float): Entry price (adjusted if using mapped symbol)
            position_size (float): Position size
            position_type (str): 'LONG' or 'SHORT'
            leverage (int): Leverage used
            original_symbol (str, optional): Original symbol from signal
            rate_multiplier (float, optional): Rate multiplier used for price adjustment
        """
        # Start the monitor in a separate task to avoid blocking
        task = asyncio.create_task(self.monitor_order_execution(
            symbol, entry_order_id, sl_order_id, tp_order_id, 
            entry_price, position_size, position_type, leverage,
            original_symbol, rate_multiplier
        ))
        
        # Store the task reference for tracking
        task_key = f"{symbol}_{entry_order_id}"
        self._monitor_tasks[task_key] = task
        
        logger.info(f"Set up order execution monitor for {symbol} in background task")

    async def load_and_monitor_active_positions(self):
        """
        Load all active positions from Binance and set up monitoring for them.
        This should be called when the bot starts to ensure all open positions are tracked.
        """
        try:
            logger.info("Loading active positions from Binance...")
            
            # Get all open positions
            positions = self.client.futures_position_information()
            active_positions = [p for p in positions if float(p['positionAmt']) != 0]
            
            if not active_positions:
                logger.info("No active positions found on Binance")
                return
            
            logger.info(f"Found {len(active_positions)} active positions")
            
            # For each active position, find associated orders and set up monitoring
            for position in active_positions:
                symbol = position['symbol']
                position_amt = float(position['positionAmt'])
                position_type = "LONG" if position_amt > 0 else "SHORT"
                entry_price = float(position['entryPrice'])
                leverage = min(self.get_max_leverage(symbol), int(Config.MAX_LEVERAGE))
                
                # Get open orders for this symbol
                try:
                    open_orders = self.client.futures_get_open_orders(symbol=symbol)
                    
                    # Find stop loss and take profit orders
                    sl_order = next((o for o in open_orders if o['type'] in ['STOP_MARKET', 'STOP'] 
                                    and ((position_amt > 0 and o['side'] == 'SELL') 
                                        or (position_amt < 0 and o['side'] == 'BUY'))), None)
                    
                    tp_order = next((o for o in open_orders if o['type'] in ['TAKE_PROFIT_MARKET', 'TAKE_PROFIT'] 
                                    and ((position_amt > 0 and o['side'] == 'SELL') 
                                        or (position_amt < 0 and o['side'] == 'BUY'))), None)
                    
                    # If we have both SL and TP orders, set up monitoring
                    if sl_order and tp_order:
                        logger.info(f"Setting up monitoring for existing position: {symbol} {position_type}")
                        
                        # Use a dummy entry order ID (we don't need it since position is already filled)
                        dummy_entry_id = int(time.time() * 1000)  # Use current timestamp as dummy ID
                        
                        # Set up monitoring with the found orders
                        self.setup_order_monitor(
                            symbol=symbol,
                            entry_order_id=dummy_entry_id,
                            sl_order_id=sl_order['orderId'],
                            tp_order_id=tp_order['orderId'],
                            entry_price=entry_price,
                            position_size=abs(position_amt),
                            position_type=position_type,
                            leverage=leverage
                        )
                        
                    else:
                        # If we don't have both SL and TP orders, log but don't monitor
                        logger.warning(f"Found position for {symbol} but not all required orders (SL: {bool(sl_order)}, TP: {bool(tp_order)})")
                        
                except Exception as e:
                    logger.error(f"Error processing position for {symbol}: {e}")
                    
        except Exception as e:
            logger.error(f"Error loading active positions: {e}")

    async def set_leverage_for_symbol(self, symbol: str, leverage: int) -> bool:
        """
        Set the leverage for a specific symbol on Binance Futures.
        
        Args:
            symbol (str): Trading symbol
            leverage (int): Leverage to set
            
        Returns:
            bool: True if leverage was set successfully, False otherwise
        """
        try:
            response = self.client.futures_change_leverage(
                symbol=symbol, 
                leverage=leverage
            )
            
            actual_leverage = int(response['leverage'])
            logger.info(f"Set leverage for {symbol} to {actual_leverage}x")
            
            # Update the cache with the new leverage
            self._leverage_cache[symbol] = actual_leverage
            
            return True
        except Exception as e:
            logger.error(f"Failed to set leverage for {symbol} to {leverage}x: {e}")
            return False

    async def execute_signal(self, signal: Dict) -> Dict:
        """
        Execute trades based on a parsed signal.

        Args:
            signal (dict): The parsed signal data

        Returns:
            dict: Trade execution results
        """
        original_symbol = signal['binance_symbol']
        position_type = signal['position_type']
        original_entry_price = self.get_last_price(original_symbol)
        original_stop_loss = signal.get('stop_loss')
        original_take_profit_levels = signal['take_profit_levels']
        original_message = signal.get('original_message', 'Unknown message')

        results = {
            'original_symbol': original_symbol,
            'position': position_type,
            'entry_order': None,
            'stop_loss_order': None,
            'take_profit_orders': [],
            'errors': [],
            'warnings': []
        }

        try:
            # Step 1: Check the maximum supported leverage and apply symbol mapping if needed
            max_leverage = min(self.get_max_leverage(original_symbol), int(Config.MAX_LEVERAGE))
            
            # Initialize variables for potential mapping
            symbol = original_symbol
            entry_price = original_entry_price
            stop_loss = original_stop_loss
            take_profit_levels = original_take_profit_levels.copy() if original_take_profit_levels else []
            rate_multiplier = 1.0
            
            if max_leverage == 0:
                # Symbol is not supported, check if we have a mapping
                mapped_symbol, rate = self.symbol_mapper.get_mapped_symbol(original_symbol)
                
                if mapped_symbol:
                    logger.info(f"Using mapped symbol with rate adjustment: {original_symbol} -> {mapped_symbol} (rate: {rate})")
                    symbol = mapped_symbol
                    rate_multiplier = rate
                    
                    # Adjust prices according to the rate
                    entry_price = original_entry_price * rate
                    
                    if original_stop_loss:
                        stop_loss = original_stop_loss * rate
                    
                    # Adjust all take profit levels
                    for i, tp in enumerate(take_profit_levels):
                        tp['price'] = tp['price'] * rate
                    
                    # Try again with the mapped symbol
                    max_leverage = min(self.get_max_leverage(symbol), int(Config.MAX_LEVERAGE))
                    results['mapped_symbol'] = mapped_symbol
                    results['rate_multiplier'] = rate
                    
                    # Store the mapping for future reference (needed for profit calculation)
                    self._active_trades[symbol] = {
                        'original_symbol': original_symbol,
                        'rate': rate
                    }
                
                # If still not supported after mapping
                if max_leverage == 0:
                    await self.handle_trading_failure(
                        original_symbol, 
                        "Symbol not supported on Binance Futures", 
                        Exception("Unsupported symbol"), 
                        original_message
                    )
                    results['errors'].append(f"Symbol {original_symbol} not supported on Binance Futures")
                    return results
            
            # Step 2: Set the leverage on Binance
            leverage_set = await self.set_leverage_for_symbol(symbol, max_leverage)
            if not leverage_set:
                await self.handle_trading_failure(
                    original_symbol, 
                    "Failed to set leverage on Binance", 
                    Exception("Leverage setting failed"), 
                    original_message
                )
                results['errors'].append(f"Failed to set leverage to {max_leverage}x for {symbol}")
                return results
            
            # Store adjusted values in results
            results['symbol'] = symbol
            results['entry_price'] = entry_price
            results['stop_loss'] = stop_loss
            results['take_profit_levels'] = take_profit_levels
            
            # Step 3: Calculate position size using risk management
            try:
                position_size, _ = self.calculate_coin_amount_to_buy(
                    symbol, max_leverage
                )
                results['position_size'] = position_size
            except Exception as e:
                await self.handle_trading_failure(
                    original_symbol, 
                    "Failed to calculate position size", 
                    e, 
                    original_message
                )
                results['errors'].append(f"Position sizing error: {str(e)}")
                return results

            # Step 4: Create the main entry order
            side = "BUY" if position_type == 'LONG' else "SELL"
            try:
                entry_order = await self._create_entry_order(symbol, side, position_size, entry_price)
                results['entry_order'] = entry_order
                
                if not entry_order or 'orderId' not in entry_order:
                    raise Exception("Failed to create entry order")
                    
            except Exception as e:
                await self.handle_trading_failure(
                    original_symbol, 
                    "Failed to create entry order", 
                    e, 
                    original_message
                )
                results['errors'].append(f"Entry order error: {str(e)}")
                return results

            # Step 5: Create take profit and stop loss orders with adjusted prices
            try:
                tp_result = await self._create_take_profit_order(
                    symbol, side, position_size, 20, entry_price, Config.DEFAULT_TP_PERCENT
                )
                results['take_profit_orders'].append(tp_result)
                
                sl_result = await self._create_stop_loss_order(
                    symbol, side, position_size, 20, entry_price, Config.DEFAULT_SL_PERCENT
                )
                results['stop_loss_order'] = sl_result
                
                # Get the actual prices from the orders for notifications
                sl_price = float(sl_result['stopPrice']) if 'stopPrice' in sl_result else 0
                tp_price = float(tp_result['stopPrice']) if 'stopPrice' in tp_result else 0
                
                # Send entry message with all details
                # Note: For display, convert back to original prices if needed
                display_entry_price = entry_price
                display_sl_price = sl_price
                display_tp_price = tp_price
                
                if rate_multiplier != 1.0:
                    # Convert back to original prices for display
                    display_entry_price = entry_price / rate_multiplier
                    display_sl_price = sl_price / rate_multiplier
                    display_tp_price = tp_price / rate_multiplier
                
                if Config.ENABLE_ENTRY_NOTIFICATIONS:
                    await self.send_entry_message(
                        symbol=original_symbol,  # Use original symbol for display
                        position_type=position_type,
                        leverage=max_leverage,
                        entry_price=display_entry_price,
                        sl_price=display_sl_price,
                        tp_price=display_tp_price,
                        position_size=position_size
                    )
                
            except Exception as e:
                logger.error(f"Error creating TP/SL orders for {symbol}: {e}")
                results['warnings'].append(f"Created entry order, but failed to set TP/SL: {str(e)}")
                # We still return success since the main order was placed

            # Step 6: Set up order monitoring to clean up orders when SL or TP is triggered
            if (results['entry_order'] and 'orderId' in results['entry_order'] and
                results['stop_loss_order'] and 'orderId' in results['stop_loss_order'] and
                results['take_profit_orders'] and 'orderId' in results['take_profit_orders'][0]):
                
                self.setup_order_monitor(
                    symbol,
                    results['entry_order']['orderId'],
                    results['stop_loss_order']['orderId'],
                    results['take_profit_orders'][0]['orderId'],
                    entry_price,
                    position_size,
                    position_type,
                    max_leverage,
                    original_symbol=original_symbol,  # Pass original symbol for proper display
                    rate_multiplier=rate_multiplier  # Pass rate for price adjustments
                )
                results['order_monitoring'] = True

            return results

        except Exception as e:
            error_msg = f"Error executing signal for {original_symbol}: {e}"
            logger.error(error_msg)
            
            # Handle any unexpected errors
            await self.handle_trading_failure(
                original_symbol, 
                "Unexpected error during trade execution", 
                e, 
                original_message
            )
            
            results['errors'].append(error_msg)
            return results

    async def adjust_stop_loss_for_profit_target(self, symbol: str, profit_target: float) -> dict:
        """
        Adjust the stop loss order for an open position based on current price,
        using the default SL percentage as if creating a new order.
        
        Args:
            symbol (str): The trading symbol
            profit_target (float): Not used directly, just triggers the adjustment
            
        Returns:
            dict: Result with status, message, and SL details
        """
        result = {
            'success': False,
            'message': '',
            'original_sl_price': None,
            'new_sl_price': None
        }
        
        try:
            # Check if this is a mapped symbol that needs rate adjustment
            original_symbol = symbol
            rate_multiplier = 1.0
            
            if symbol in self._active_trades:
                trade_info = self._active_trades[symbol]
                original_symbol = trade_info.get('original_symbol', symbol)
                rate_multiplier = trade_info.get('rate', 1.0)
                
            # Get current position information
            position_info = self.client.futures_position_information(symbol=symbol)
            
            # Find the position for this symbol with non-zero amount
            position = next((p for p in position_info if p['symbol'] == symbol and float(p['positionAmt']) != 0), None)
            
            if not position:
                result['message'] = f"No open position found for {symbol}"
                return result
            
            # Determine position details
            position_amt = float(position['positionAmt'])
            position_type = "LONG" if position_amt > 0 else "SHORT"
            entry_price = float(position['entryPrice'])
            
            # Get the current market price
            current_price = self.get_last_price(symbol)
            if not current_price:
                result['message'] = f"Could not get current price for {symbol}"
                return result
                
            logger.info(f"Current market price for {symbol}: {current_price}")
            
            # Get open orders for this symbol
            open_orders = self.client.futures_get_open_orders(symbol=symbol)
            
            # Find existing stop loss order
            sl_order = next((o for o in open_orders if o['type'] in ['STOP_MARKET', 'STOP'] 
                            and ((position_amt > 0 and o['side'] == 'SELL') 
                                or (position_amt < 0 and o['side'] == 'BUY'))), None)
            
            if not sl_order:
                result['message'] = f"No stop loss order found for {symbol}"
                return result
            
            # Get the current SL price
            current_sl_price = float(sl_order['stopPrice'])
            logger.info(f"Current SL price for {symbol}: {current_sl_price}")
            
            # Get leverage - for calculating SL distances
            try:
                # Try first from position info
                if 'leverage' in position:
                    leverage = int(position['leverage'])
                else:
                    # Fallback to the cached leverage
                    leverage = self.get_max_leverage(symbol)
                    
                # Cap at max leverage
                leverage = min(leverage, int(Config.MAX_LEVERAGE))
                logger.info(f"Using leverage: {leverage}x")
            except Exception as e:
                logger.error(f"Error getting leverage, using default: {e}")
                leverage = int(Config.MAX_LEVERAGE)
                
            # Get the default SL percentage from config
            default_sl_percent = float(Config.DEFAULT_SL_PERCENT)
            logger.info(f"Using default SL percent: {default_sl_percent}%")
            
            # Calculate new SL price based on current price and default SL percentage
            if position_type == "LONG":
                # For LONG positions, SL is below current price
                new_sl_price = current_price * (1 - (default_sl_percent / (100 * leverage)))
            else:  # SHORT
                # For SHORT positions, SL is above current price
                new_sl_price = current_price * (1 + (default_sl_percent / (100 * leverage)))
            
            # Get price precision for formatting
            price_precision = self.get_price_precision(symbol)
            new_sl_price = round(new_sl_price, price_precision)
            
            logger.info(f"Calculated new SL price for {symbol}: {new_sl_price}")
            
            # Check if the new SL is an improvement
            is_better_sl = False
            if position_type == "LONG" and new_sl_price > current_sl_price:
                is_better_sl = True
            elif position_type == "SHORT" and new_sl_price < current_sl_price:
                is_better_sl = True
                
            if not is_better_sl:
                result['message'] = f"Current SL is already better than calculated new SL. No adjustment needed."
                result['success'] = True  # Still mark as success since no action was required
                return result
            
            # Cancel existing SL order
            try:
                self.client.futures_cancel_order(
                    symbol=symbol,
                    orderId=sl_order['orderId']
                )
                logger.info(f"Canceled existing SL order {sl_order['orderId']} for {symbol}")
            except Exception as e:
                logger.error(f"Error canceling existing SL order: {e}")
                result['message'] = f"Failed to cancel existing SL order: {str(e)}"
                return result
            
            # Create new SL order
            try:
                new_sl_order = self.client.futures_create_order(
                    symbol=symbol,
                    side='SELL' if position_type == 'LONG' else 'BUY',
                    type="STOP_MARKET",
                    stopPrice=new_sl_price,
                    closePosition=True  # Close the entire position
                )
                
                logger.info(f"Created new SL order for {symbol} at {new_sl_price}: {new_sl_order['orderId']}")
                
                # Calculate raw price movements for reporting
                if position_type == "LONG":
                    old_raw_percent = ((current_sl_price - entry_price) / entry_price) * 100
                    new_raw_percent = ((new_sl_price - entry_price) / entry_price) * 100
                    old_leveraged = old_raw_percent * leverage
                    new_leveraged = new_raw_percent * leverage
                else:  # SHORT
                    old_raw_percent = ((entry_price - current_sl_price) / entry_price) * 100
                    new_raw_percent = ((entry_price - new_sl_price) / entry_price) * 100
                    old_leveraged = old_raw_percent * leverage
                    new_leveraged = new_raw_percent * leverage
                
                result['success'] = True
                result['message'] = f"Successfully adjusted SL from {current_sl_price} to {new_sl_price}"
                result['original_sl_price'] = current_sl_price
                result['new_sl_price'] = new_sl_price
                result['new_sl_order'] = new_sl_order
                result['original_sl_percent'] = old_leveraged
                result['new_sl_percent'] = new_leveraged
                
                # If successful and we need to display original prices
                if rate_multiplier != 1.0:
                    # Store both actual and display prices
                    result['actual_original_sl_price'] = result['original_sl_price']
                    result['actual_new_sl_price'] = result['new_sl_price']
                    
                    # Convert to display prices
                    result['original_sl_price'] = result['original_sl_price'] / rate_multiplier
                    result['new_sl_price'] = result['new_sl_price'] / rate_multiplier
                    result['display_symbol'] = original_symbol
                
                # Send notification about SL adjustment
                if self.telegram_client and self.target_channel_id:
                    notification = (
                        f"🔄 STOP LOSS ADJUSTED\n\n"
                        f"Pair: {original_symbol}\n"
                        f"Position: {'🟢 LONG' if position_type == 'LONG' else '🔴 SHORT'}\n"
                        f"Leverage: {leverage}x\n"
                        f"Entry Price: {entry_price / rate_multiplier if rate_multiplier != 1.0 else entry_price}\n"
                        f"Current Price: {current_price / rate_multiplier if rate_multiplier != 1.0 else current_price}\n"
                        f"Original SL: {result['original_sl_price']} ({old_leveraged:.2f}%)\n"
                        f"New SL: {result['new_sl_price']} ({new_leveraged:.2f}%)\n"
                        f"Default SL Distance: {default_sl_percent}%\n\n"
                        f"#Binance #{original_symbol}"
                    )
                    
                    await self.telegram_client.send_message(self.target_channel_id, notification)
                
                return result
                
            except Exception as e:
                logger.error(f"Error creating new SL order: {e}")
                result['message'] = f"Failed to create new SL order: {str(e)}"
                return result
                
        except Exception as e:
            logger.error(f"Error adjusting stop loss for {symbol}: {e}")
            result['message'] = f"Error: {str(e)}"
            return result