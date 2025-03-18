import math
import asyncio
from datetime import datetime, timedelta
from binance.client import Client
from utils.logger import logger, trading_failures_logger, profit_logger
from typing import Dict, List, Optional, Any, Tuple
from trading.risk import RiskManager
from utils.config import Config
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

        # Caches for API data
        self._symbol_info_cache = {}
        self._leverage_cache = {}

        # Reference to Telegram client for notifications
        self.telegram_client = None
        self.target_channel_id = target_channel_id
        
        # Constants
        self.default_max_leverage = max_leverage

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
        calculate coin amount based on wallet ratio and leverage, coin price and set with precision_quantity
        :param pair: coin symbol pair ex: BNBUSDT
        :return: coin amount and coin price
        """
        try:
            QUOTE_ASSET = Config.QUOTE_ASSET
            WALLET_RATIO = Config.WALLET_RATIO
            account_balance = self.get_balance_in_quote(QUOTE_ASSET)
            amount_to_trade_in_quote = ((account_balance / 100) * WALLET_RATIO) * leverage

            coin_price = self.get_last_price(pair)
            coin_amount = amount_to_trade_in_quote / coin_price
            coin_amount = self.get_precise_quantity(pair, coin_amount)
            logger.info(f"amount to buy {coin_amount} x {leverage} * {coin_price}")
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
                quantity=quantity
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
                
            # Format the message
            message = (
                f"{emoji} TRADE {result_type} - {exit_description}\n\n"
                f"Pair: {profit_data['symbol']}\n"
                f"Position: {profit_data['position_type']}\n"
                f"Leverage: {profit_data['leverage']}x\n"
                f"Entry: {profit_data['entry_price']:.4f}\n"
                f"Exit: {profit_data['exit_price']:.4f}\n"
                f"Size: {profit_data['position_size']:.4f}\n\n"
                f"P/L: {profit_data['absolute_profit']:.4f} USDT ({profit_data['leveraged_percentage']:.2f}%)\n"
                f"Raw Price Change: {profit_data['price_diff_percent']:.2f}%\n\n"
                f"#trade #{profit_data['symbol']} #{profit_data['position_type'].lower()} #{exit_type}"
            )
            
            # Send the message
            await self.telegram_client.send_message(self.target_channel_id, message)
            
            # Also log to the profit logger
            profit_logger.info(
                f"{profit_data['symbol']} {profit_data['position_type']} - {exit_description} - " +
                f"P/L: {profit_data['absolute_profit']:.4f} USDT ({profit_data['leveraged_percentage']:.2f}%)"
            )
            
            logger.info(f"Sent profit result message for {profit_data['symbol']}")
            
        except Exception as e:
            logger.error(f"Error sending profit message: {e}")

    async def monitor_order_execution(self, symbol: str, entry_order_id: int, sl_order_id: int, tp_order_id: int, 
                                 entry_price: float, position_size: float, position_type: str, leverage: int):
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
        """
        try:
            # First wait for entry order to be filled
            entry_filled = False
            check_attempts = 0
            actual_position_size = position_size  # Default to provided size
            
            while not entry_filled and check_attempts < 12:  # Check for 2 minutes
                try:
                    order_status = self.client.futures_get_order(symbol=symbol, orderId=entry_order_id)
                    if order_status['status'] == 'FILLED':
                        entry_filled = True
                        
                        # Get actual filled price from the order
                        try:
                            actual_entry_price = float(order_status['avgPrice'])
                            if actual_entry_price > 0:
                                entry_price = actual_entry_price
                                logger.info(f"Updated entry price to actual filled price: {entry_price}")
                        except (KeyError, ValueError) as e:
                            logger.warning(f"Could not get actual entry price: {e}")
                        
                        # Get actual filled quantity from the order
                        try:
                            actual_position_size = float(order_status['executedQty'])
                            if actual_position_size > 0:
                                position_size = actual_position_size
                                logger.info(f"Updated position size to actual filled quantity: {position_size}")
                        except (KeyError, ValueError) as e:
                            logger.warning(f"Could not get actual position size: {e}")
                        
                        logger.info(f"Entry order {entry_order_id} for {symbol} has been filled at {entry_price}")
                    else:
                        await asyncio.sleep(10)  # Check every 10 seconds
                        check_attempts += 1
                except Exception as e:
                    logger.error(f"Error checking entry order status: {e}")
                    await asyncio.sleep(10)
                    check_attempts += 1
            
            if not entry_filled:
                logger.warning(f"Entry order {entry_order_id} for {symbol} was not filled after 2 minutes")
                return
                    
            # Entry is filled, now monitor SL and TP orders
            position_closed = False
            exit_price = 0
            exit_type = "unknown"
            
            # Keep track of whether we've processed the exit already to prevent double processing
            exit_processed = False
            
            while not position_closed:
                try:
                    # Check SL order
                    try:
                        sl_status = self.client.futures_get_order(symbol=symbol, orderId=sl_order_id)
                        if sl_status['status'] == 'FILLED' and not exit_processed:
                            # SL was triggered - position is closed, cancel TP
                            logger.info(f"Stop loss triggered for {symbol}, canceling take profit order")
                            position_closed = True
                            exit_type = "stop_loss"
                            exit_processed = True  # Mark as processed
                            
                            # Get the exit price - use the actual execution price if available
                            if 'avgPrice' in sl_status and float(sl_status['avgPrice']) > 0:
                                exit_price = float(sl_status['avgPrice'])
                            else:
                                # Fallback to the stop price
                                exit_price = float(sl_status['stopPrice'])
                            
                            # Cancel the take profit order
                            try:
                                self.client.futures_cancel_order(symbol=symbol, orderId=tp_order_id)
                                logger.info(f"Successfully canceled TP order {tp_order_id} for {symbol}")
                            except Exception as e:
                                logger.error(f"Error canceling TP order after SL was hit: {e}")
                    except Exception as e:
                        # Order might not exist anymore
                        logger.warning(f"Could not check SL order {sl_order_id}: {e}")
                    
                    # If position already closed by SL, don't check TP
                    if position_closed:
                        break
                        
                    # Check TP order
                    try:
                        tp_status = self.client.futures_get_order(symbol=symbol, orderId=tp_order_id)
                        if tp_status['status'] == 'FILLED' and not exit_processed:
                            # TP was triggered - position is closed, cancel SL
                            logger.info(f"Take profit triggered for {symbol}, canceling stop loss order")
                            position_closed = True
                            exit_type = "take_profit"
                            exit_processed = True  # Mark as processed
                            
                            # Get the exit price - use the actual execution price if available
                            if 'avgPrice' in tp_status and float(tp_status['avgPrice']) > 0:
                                exit_price = float(tp_status['avgPrice'])
                            else:
                                # Fallback to the stop price
                                exit_price = float(tp_status['stopPrice'])
                            
                            # Cancel the stop loss order
                            try:
                                self.client.futures_cancel_order(symbol=symbol, orderId=sl_order_id)
                                logger.info(f"Successfully canceled SL order {sl_order_id} for {symbol}")
                            except Exception as e:
                                logger.error(f"Error canceling SL order after TP was hit: {e}")
                    except Exception as e:
                        # Order might not exist anymore
                        logger.warning(f"Could not check TP order {tp_order_id}: {e}")
                    
                    # Check if the position still exists
                    if not position_closed:
                        position_info = self.client.futures_position_information(symbol=symbol)
                        position = next((p for p in position_info if p['symbol'] == symbol and float(p['positionAmt']) != 0), None)
                        
                        if not position and not exit_processed:
                            # Position was closed by some other means
                            logger.info(f"Position for {symbol} was closed by other means, canceling all orders")
                            position_closed = True
                            exit_type = "manual_or_liquidation"
                            exit_processed = True  # Mark as processed
                            
                            # Try to get the last price as exit price
                            try:
                                exit_price = self.get_last_price(symbol)
                                logger.info(f"Using current price as exit price: {exit_price}")
                            except Exception as e:
                                logger.error(f"Could not get last price: {e}")
                                # If we can't get the current price, use entry price as fallback
                                exit_price = entry_price
                                
                            await self.cancel_all_open_orders(symbol)
                    
                    if not position_closed:
                        await asyncio.sleep(10)  # Check every 10 seconds
                        
                except Exception as e:
                    logger.error(f"Error in order execution monitor: {e}")
                    await asyncio.sleep(10)
                    
            # Position is closed and not yet processed
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
                    
                    # Add exit type to the profit data
                    profit_data['exit_type'] = exit_type
                    
                    # Log the profit information regardless of exit type
                    profit_message = (
                        f"{symbol} {position_type} - {exit_type.upper()} - " +
                        f"Entry: {entry_price:.4f}, Exit: {exit_price:.4f}, " +
                        f"P/L: {profit_data['absolute_profit']:.4f} USDT ({profit_data['leveraged_percentage']:.2f}%)"
                    )
                    from utils.logger import profit_logger
                    profit_logger.info(profit_message)
                    logger.info(f"Profit calculation for {symbol}: {profit_data['percentage_profit']:.2f}%")
                    
                    # Check the config option to determine if we should send a message
                    if not Config.SEND_PROFIT_ONLY_FOR_MANUAL_EXITS or exit_type == "manual_or_liquidation":
                        await self.send_profit_message(profit_data)
                    else:
                        logger.info(f"Not sending profit message for {exit_type} exit as per configuration")
                    
                except Exception as e:
                    logger.error(f"Error processing profit result: {e}")
                    
            # As a final safety check, cancel any remaining orders
            try:
                await self.cancel_all_open_orders(symbol)
            except Exception as e:
                logger.error(f"Error in final order cleanup: {e}")
                
        except Exception as e:
            logger.error(f"Error in order execution monitor for {symbol}: {e}")
    def setup_order_monitor(self, symbol: str, entry_order_id: int, sl_order_id: int, tp_order_id: int,
                            entry_price: float, position_size: float, position_type: str, leverage: int):
        """
        Set up monitoring for order execution to clean up related orders and send profit messages.
        
        Args:
            symbol (str): The trading symbol
            entry_order_id (int): Entry order ID
            sl_order_id (int): Stop loss order ID
            tp_order_id (int): Take profit order ID
            entry_price (float): Entry price
            position_size (float): Position size
            position_type (str): 'LONG' or 'SHORT'
            leverage (int): Leverage used
        """
        # Start the monitor in a separate task to avoid blocking
        asyncio.create_task(self.monitor_order_execution(
            symbol, entry_order_id, sl_order_id, tp_order_id, 
            entry_price, position_size, position_type, leverage
        ))
        logger.info(f"Set up order execution monitor for {symbol}")

    async def execute_signal(self, signal: Dict) -> Dict:
        """
        Execute trades based on a parsed signal.

        Args:
            signal (dict): The parsed signal data

        Returns:
            dict: Trade execution results
        """
        symbol = signal['binance_symbol']
        position_type = signal['position_type']
        entry_price = signal['entry_price']
        stop_loss = signal.get('stop_loss')
        take_profit_levels = signal['take_profit_levels']
        original_message = signal.get('original_message', 'Unknown message')

        results = {
            'symbol': symbol,
            'position': position_type,
            'entry_order': None,
            'stop_loss_order': None,
            'take_profit_orders': [],
            'errors': [],
            'warnings': []
        }

        try:
            # Step 1: Check the maximum supported leverage
            max_leverage = min(self.get_max_leverage(symbol), int(Config.MAX_LEVERAGE))
            
            if max_leverage == 0:
                # Symbol is not supported
                await self.handle_trading_failure(
                    symbol, 
                    "Symbol not supported on Binance Futures", 
                    Exception("Unsupported symbol"), 
                    original_message
                )
                results['errors'].append(f"Symbol {symbol} not supported on Binance Futures")
                return results
                
            # Step 2: Calculate position size using risk management
            try:
                position_size, _ = self.calculate_coin_amount_to_buy(
                    symbol, max_leverage
                )
                results['position_size'] = position_size
            except Exception as e:
                await self.handle_trading_failure(
                    symbol, 
                    "Failed to calculate position size", 
                    e, 
                    original_message
                )
                results['errors'].append(f"Position sizing error: {str(e)}")
                return results

            # Step 3: Create the main entry order
            side = "BUY" if position_type == 'LONG' else "SELL"
            try:
                entry_order = await self._create_entry_order(symbol, side, position_size, entry_price)
                results['entry_order'] = entry_order
                
                if not entry_order or 'orderId' not in entry_order:
                    raise Exception("Failed to create entry order")
                    
            except Exception as e:
                await self.handle_trading_failure(
                    symbol, 
                    "Failed to create entry order", 
                    e, 
                    original_message
                )
                results['errors'].append(f"Entry order error: {str(e)}")
                return results

            # Step 4: Create take profit and stop loss orders
            try:
                tp_result = await self._create_take_profit_order(
                    symbol, side, position_size, max_leverage, entry_price, Config.DEFAULT_TP_PERCENT
                )
                results['take_profit_orders'].append(tp_result)
                
                sl_result = await self._create_stop_loss_order(
                    symbol, side, position_size, max_leverage, entry_price, Config.DEFAULT_SL_PERCENT
                )
                results['stop_loss_order'] = sl_result
                
                # Get the actual prices from the orders for notifications
                sl_price = float(sl_result['stopPrice']) if 'stopPrice' in sl_result else 0
                tp_price = float(tp_result['stopPrice']) if 'stopPrice' in tp_result else 0
                
                # Send entry message with all details
                if Config.ENABLE_ENTRY_NOTIFICATIONS:
                    await self.send_entry_message(
                        symbol=symbol,
                        position_type=position_type,
                        leverage=max_leverage,
                        entry_price=entry_price,
                        sl_price=sl_price,
                        tp_price=tp_price,
                        position_size=position_size
                    )
                
            except Exception as e:
                logger.error(f"Error creating TP/SL orders for {symbol}: {e}")
                results['warnings'].append(f"Created entry order, but failed to set TP/SL: {str(e)}")
                # We still return success since the main order was placed

            # Step 5: Set up order monitoring to clean up orders when SL or TP is triggered
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
                    max_leverage
                )
                results['order_monitoring'] = True

            # Note: We do NOT close existing positions here as per the request
            # Positions will be managed by SL/TP orders and closed only when they hit

            return results

        except Exception as e:
            error_msg = f"Error executing signal for {symbol}: {e}"
            logger.error(error_msg)
            
            # Handle any unexpected errors
            await self.handle_trading_failure(
                symbol, 
                "Unexpected error during trade execution", 
                e, 
                original_message
            )
            
            results['errors'].append(error_msg)
            return results

    def parse(self, message: str):
        try:
            # Split message into lines and remove empty lines
            lines = [line.strip() for line in message.split('\n') if line.strip()]

            # First line should contain trading pair and position type
            first_line = lines[0]

            # Look for trading pair (any word containing /)
            symbol = next((word for word in first_line.split() if '/' in word), None)
            symbol = "".join(re.findall(r"[A-Z0-9]+", symbol))  # Keep numbers and uppercase letters
            if not symbol:
                return None

            # Position type
            position_type = 'LONG' if 'Long' in first_line else 'SHORT' if 'Short' in first_line else None
            if not position_type:
                return None

            # Rest of your parsing logic for entry price, stop loss, take profits...
            # ...

            # Convert symbol format from X/Y to XY for Binance
            binance_symbol = symbol.replace('/', '')

            return {
                'symbol': symbol,
                'binance_symbol': binance_symbol,
                'position_type': position_type,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit_levels': tp_levels,
                'original_message': message
            }
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return None