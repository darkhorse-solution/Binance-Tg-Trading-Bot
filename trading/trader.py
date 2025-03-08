# trading/trader.py
import asyncio
from binance.client import Client
from utils.logger import logger
from typing import Dict, List, Optional, Any
import time
import asyncio
from trading.risk import RiskManager


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
            position_size = await self._calculate_position_size(
                symbol, entry_price, stop_loss, leverage
            )
            results['position_size'] = position_size

            # Create main order - could be market or limit depending on entry_price vs current
            side = "BUY" if position_type == 'LONG' else "SELL"
            entry_order = await self._create_entry_order(symbol, side, position_size, entry_price)
            results['entry_order'] = entry_order

            # If entry order successful, place stop loss and take profit orders
            if entry_order and 'orderId' in entry_order:
                # Place stop loss order if provided
                if stop_loss:
                    sl_side = "SELL" if position_type == 'LONG' else "BUY"
                    stop_loss_order = await self._create_stop_loss_order(
                        symbol, sl_side, position_size, stop_loss
                    )
                    results['stop_loss_order'] = stop_loss_order
                else:
                    # Create automatic stop loss if none provided (based on risk management)
                    auto_stop_loss = self._calculate_auto_stop_loss(entry_price, position_type, leverage)
                    sl_side = "SELL" if position_type == 'LONG' else "BUY"
                    stop_loss_order = await self._create_stop_loss_order(
                        symbol, sl_side, position_size, auto_stop_loss
                    )
                    results['stop_loss_order'] = stop_loss_order
                    results['warnings'].append(f"Auto stop-loss created at {auto_stop_loss}")

                # Place take profit orders
                tp_remaining = position_size
                for i, tp in enumerate(take_profit_levels):
                    tp_side = "SELL" if position_type == 'LONG' else "BUY"

                    # Calculate position size for this TP level
                    # For last TP level, use remaining size to ensure we close full position
                    if i == len(take_profit_levels) - 1:
                        tp_size = tp_remaining
                    else:
                        tp_size = position_size * (tp['percentage'] / 100)
                        tp_remaining -= tp_size

                    # Create take profit order
                    tp_order = await self._create_take_profit_order(
                        symbol=symbol,
                        side=tp_side,
                        quantity=tp_size,
                        price=tp['price']
                    )
                    results['take_profit_orders'].append(tp_order)

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
            # Check current price
            ticker = self.client.futures_ticker(symbol=symbol)
            current_price = float(ticker['lastPrice'])

            # Decide if we should use limit or market order
            price_difference_pct = abs(price - current_price) / current_price

            if price_difference_pct <= 0.003:  # Within 0.3% of current price, use market order
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type="MARKET",  # Use correct string constant
                    quantity=quantity
                )
            else:
                # Use a limit order with reasonable time in force
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type="LIMIT",  # Use correct string constant
                    timeInForce="GTC",  # Good Till Cancelled - correct string constant
                    quantity=quantity,
                    price=price
                )

            logger.info(f"Created entry order for {symbol}, {side} at {price}: {order['orderId']}")
            return order

        except Exception as e:
            logger.error(f"Error creating entry order: {e}")
            return {"error": str(e)}

    async def _create_stop_loss_order(self, symbol: str, side: str,
                                      quantity: float, price: float) -> Dict:
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
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="STOP_MARKET",  # Use correct string constant
                stopPrice=price,
                closePosition=True  # Close the entire position
            )

            logger.info(f"Created stop loss order for {symbol} at {price}: {order['orderId']}")
            return order

        except Exception as e:
            logger.error(f"Error creating stop loss order: {e}")
            return {"error": str(e)}

    async def _create_take_profit_order(self, symbol: str, side: str,
                                        quantity: float, price: float) -> Dict:
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
                side=side,
                type="TAKE_PROFIT_MARKET",  # Use correct string constant
                stopPrice=price,
                quantity=quantity
            )

            logger.info(f"Created take profit order for {symbol} at {price}: {order['orderId']}")
            return order

        except Exception as e:
            logger.error(f"Error creating take profit order: {e}")
            return {"error": str(e)}