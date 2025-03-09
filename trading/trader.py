import math
from binance.client import Client
from utils.logger import logger
from typing import Dict, List, Optional, Any
from trading.risk import RiskManager
from utils.config import Config

class BinanceTrader:
    """
    Class for interacting with Binance API to execute trades.
    """

    def __init__(self, api_key: str, api_secret: str,
                default_risk_percent: float = 2.0, max_leverage: int = 20,
                target_channel_id: int = None):
        """
        Initialize the Binance trader with API credentials.
        """
        self.client = Client(api_key, api_secret)
        self.risk_manager = RiskManager(default_risk_percent, max_leverage)
        self._symbol_info_cache = {}
        self._leverage_cache = {}  # Cache for max leverage values
        self._prefetch_common_symbols()
        self.telegram_client = None
        self.target_channel_id = target_channel_id
        self.default_max_leverage = max_leverage

    def set_telegram_client(self, client):
        """Set the Telegram client for sending notifications."""
        self.telegram_client = client

    def _prefetch_common_symbols(self):
        """Prefetch information for common trading pairs to avoid API rate limits."""
        try:
            exchange_info = self.client.get_exchange_info()

            # Focus on futures symbols for leveraged trading
            for symbol_info in exchange_info['symbols']:  # Limit to top 20 to avoid rate limits
                symbol = symbol_info['symbol']
                self._symbol_info_cache[symbol] = symbol_info

            logger.info(f"Prefetched {len(self._symbol_info_cache)} common symbols")            
        except Exception as e:
            logger.warning(f"Failed to prefetch symbols: {e}")

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
        from utils.logger import trading_failures_logger
        
        error_msg = f"Symbol: {symbol}, Error: {str(error)}, Message: {message}"
        trading_failures_logger.error(error_msg)
        trading_failures_logger.info(f"Original signal: {original_signal}")
        
        # Send message to channel if client is available
        if self.telegram_client and self.target_channel_id:
            notification = (
                f"❌ TRADE EXECUTION FAILED\n\n"
                f"Symbol: {symbol}\n"
                f"Reason: {message}\n"
                f"Error: {str(error)}\n\n"
                f"This trading signal could not be processed automatically."
            )
            
            try:
                await self.telegram_client.send_message(self.target_channel_id, notification)
                logger.info(f"Sent trading failure notification for {symbol}")
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")

    async def execute_signal(self, signal: Dict) -> Dict:
        """
        Execute trades based on a parsed signal.
        """
        symbol = signal['binance_symbol']
        position_type = signal['position_type']
        entry_price = signal['entry_price']
        requested_leverage = signal['leverage']
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
            max_leverage = self.get_max_leverage(symbol)
            
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
                
            # Step 2: Apply the minimum of requested leverage and max supported leverage
            effective_leverage = min(requested_leverage, max_leverage)
            
            if effective_leverage < requested_leverage:
                message = f"Requested leverage {requested_leverage}x exceeds maximum supported leverage {max_leverage}x for {symbol}. Using {effective_leverage}x instead."
                logger.warning(message)
                results['warnings'].append(message)
            
            # Step 3: Set leverage for the symbol
            try:
                self.client.futures_change_leverage(symbol=symbol, leverage=effective_leverage)
                logger.info(f"Set leverage for {symbol} to {effective_leverage}x")
            except Exception as e:
                await self.handle_trading_failure(
                    symbol, 
                    "Failed to set leverage", 
                    e, 
                    original_message
                )
                results['errors'].append(f"Failed to set leverage for {symbol}: {str(e)}")
                return results

            # Step 4: Calculate position size using risk management
            try:
                position_size, _ = self.calculate_coin_amount_to_buy(
                    symbol, effective_leverage
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

            # Step 5: Create the main entry order
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

            # Step 6: Create take profit and stop loss orders
            try:
                tp_result = await self._create_take_profit_order(
                    symbol, side, position_size, requested_leverage, entry_price, 100
                )
                results['take_profit_orders'].append(tp_result)
                
                sl_result = await self._create_stop_loss_order(
                    symbol, side, position_size, requested_leverage, entry_price, 150
                )
                results['stop_loss_order'] = sl_result
                
            except Exception as e:
                logger.error(f"Error creating TP/SL orders for {symbol}: {e}")
                results['warnings'].append(f"Created entry order, but failed to set TP/SL: {str(e)}")
                # We still return success since the main order was placed

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

    def _calculate_auto_stop_loss(self, entry_price: float, position_type: str, leverage: int) -> float:
        """
        Calculate an automatic stop loss price if none is provided.

        Args:
            entry_price (float): Entry price
            position_type (str): 'LONG' or 'SHORT'
            leverage (int): Leverage being used

        Returns:
            float: Stop loss price
        """
        # Determine maximum allowed loss based on leverage
        # Higher leverage = tighter stop loss
        max_loss_pct = min(5.0, 20.0 / leverage)  # Between 1% and 5%

        if position_type == 'LONG':
            return entry_price * (1 - max_loss_pct / 100)
        else:  # SHORT
            return entry_price * (1 + max_loss_pct / 100)

    async def _calculate_position_size(self, symbol: str, entry_price: float,
                                       stop_loss: Optional[float] = None,
                                       leverage: int = 1) -> float:
        """
        Calculate appropriate position size based on account balance and risk.

        Args:
            symbol (str): Trading symbol
            entry_price (float): Entry price
            stop_loss (float, optional): Stop loss price
            leverage (int): Leverage to use

        Returns:
            float: Position size
        """
        try:
            # Get account balance
            account = self.client.futures_account_balance()
            usdt_balance = next((item['balance'] for item in account if item['asset'] == 'USDT'), 0)
            usdt_balance = float(usdt_balance)

            # Get symbol information for precision requirements
            symbol_info = self.get_symbol_info(symbol) or {}

            # Use risk manager to calculate position size
            position_size, message = self.risk_manager.calculate_position_size(
                account_balance=usdt_balance,
                entry_price=entry_price,
                stop_loss=stop_loss,
                leverage=leverage,
                symbol_info=symbol_info
            )

            logger.info(f"Position size for {symbol}: {position_size} - {message}")
            return position_size

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            # Return a safe minimal position size
            return 0.01  # Minimum to avoid errors

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
            logger.error(f'get_precise_quantity {get_precise_quantity}')
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
            price (float): Stop price

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
                type="STOP_MARKET",  # Use correct string constant
                stopPrice=sl_price,
                quantity=quantity,
                closePosition=True  # Close the entire position
            )

            logger.info(f"Created stop loss order for {symbol} at {sl_price}: {order['orderId']}")
            return order

        except Exception as e:
            logger.error(f"Error creating stop loss order: {e}")
            return {"error": str(e)}

    async def _create_take_profit_order(self, symbol: str, side: str,
                                        quantity: float, leverage, entry_price, tp_percent) -> Dict:
        
        price_precision = self.get_price_precision(symbol)
        if side == 'BUY':
            tp_price = entry_price * (leverage + tp_percent / 100) / leverage
        else:
            tp_price = entry_price * (leverage - tp_percent / 100) / leverage

        tp_price = round(tp_price, price_precision)
        """
        Create a take profit order.

        Args:
            symbol (str): Trading symbol
            side (str): SIDE_BUY or SIDE_SELL (opposite of entry order)
            quantity (float): Order quantity
            price (float): Take profit price

        Returns:
            dict: Order response
        """
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side='SELL' if side == 'BUY' else 'BUY',
                type="TAKE_PROFIT_MARKET",  # Use correct string constant
                stopPrice=tp_price,
                quantity=quantity
            )

            logger.info(f"Created take profit order for {symbol} at {tp_price}: {order['orderId']}")
            return order

        except Exception as e:
            logger.error(f"Error creating take profit order: {e}")
            return {"error": str(e)}