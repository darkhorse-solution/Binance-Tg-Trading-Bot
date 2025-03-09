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
                 default_risk_percent: float = 2.0, max_leverage: int = 20):
        """
        Initialize the Binance trader with API credentials.

        Args:
            api_key (str): Binance API key
            api_secret (str): Binance API secret
            default_risk_percent (float): Default percentage of account to risk per trade
            max_leverage (int): Maximum leverage to use
        """
        self.client = Client(api_key, api_secret)

        # Initialize risk manager
        self.risk_manager = RiskManager(default_risk_percent, max_leverage)

        # Cache for symbol information to avoid repeated API calls
        self._symbol_info_cache = {}

        # Initialize the cache with common symbols at startup
        self._prefetch_common_symbols()

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
        leverage = signal['leverage']
        stop_loss = signal.get('stop_loss')
        take_profit_levels = signal['take_profit_levels']

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
            # Get account balance for risk validation
            account = self.client.futures_account_balance()
            usdt_balance = float(next((item['balance'] for item in account if item['asset'] == 'USDT'), 0))
            logger.info(f"{usdt_balance}")

            # Validate risk parameters
            is_valid, message = self.risk_manager.validate_risk_parameters(signal, usdt_balance)

            if not is_valid:
                results['errors'].append(f"Risk validation failed: {message}")
                logger.warning(f"Signal rejected due to risk parameters: {message}")
                return results

            if "Warning" in message:
                results['warnings'].append(message)
                logger.warning(message)

            # Set leverage for the symbol
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

            # Calculate position size using risk management
            position_size, _ = self.calculate_coin_amount_to_buy(
                symbol, leverage
            )
            results['position_size'] = position_size

            # Create main order - could be market or limit depending on entry_price vs current
            side = "BUY" if position_type == 'LONG' else "SELL"
            entry_order = await self._create_entry_order(symbol, side, position_size, entry_price)
            results['entry_order'] = entry_order

            # If entry order successful, place stop loss and take profit orders
            if entry_order and 'orderId' in entry_order:
                await self._create_take_profit_order(symbol, side, position_size, leverage, entry_price, 100)
                await self._create_stop_loss_order(symbol, side, position_size, leverage, entry_price, 150)
                # Place stop loss order if provided
                # if stop_loss:
                #     sl_side = "SELL" if position_type == 'LONG' else "BUY"
                #     stop_loss_order = await self._create_stop_loss_order(
                #         symbol, sl_side, position_size, stop_loss
                #     )
                #     results['stop_loss_order'] = stop_loss_order
                # else:
                #     # Create automatic stop loss if none provided (based on risk management)
                #     auto_stop_loss = self._calculate_auto_stop_loss(entry_price, position_type, leverage)
                #     sl_side = "SELL" if position_type == 'LONG' else "BUY"
                #     stop_loss_order = await self._create_stop_loss_order(
                #         symbol, sl_side, position_size, auto_stop_loss
                #     )
                #     results['stop_loss_order'] = stop_loss_order
                #     results['warnings'].append(f"Auto stop-loss created at {auto_stop_loss}")

                # # Place take profit orders
                # tp_remaining = position_size
                # for i, tp in enumerate(take_profit_levels):
                #     tp_side = "SELL" if position_type == 'LONG' else "BUY"

                #     # Calculate position size for this TP level
                #     # For last TP level, use remaining size to ensure we close full position
                #     if i == len(take_profit_levels) - 1:
                #         tp_size = tp_remaining
                #     else:
                #         tp_size = position_size * (tp['percentage'] / 100)
                #         tp_remaining -= tp_size

                #     # Create take profit order
                #     tp_order = await self._create_take_profit_order(
                #         symbol=symbol,
                #         side=tp_side,
                #         quantity=tp_size,
                #         price=tp['price']
                #     )
                #     results['take_profit_orders'].append(tp_order)

            return results

        except Exception as e:
            error_msg = f"Error executing signal for {symbol}: {e}"
            logger.error(error_msg)
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