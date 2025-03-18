# trading/risk.py
from typing import Dict, Optional, Tuple
from utils.logger import logger


class RiskManager:
    """
    Class for managing trading risk and calculating appropriate position sizes.
    """

    def __init__(self, default_risk_percent: float = 2.0, max_leverage: int = 20):
        """
        Initialize the risk manager.

        Args:
            default_risk_percent (float): Default percentage of account to risk per trade
            max_leverage (int): Maximum leverage to use
        """
        self.default_risk_percent = default_risk_percent / 100.0  # Convert to decimal
        self.max_leverage = max_leverage

    def calculate_position_size(self,
                                account_balance: float,
                                entry_price: float,
                                stop_loss: Optional[float],
                                leverage: int,
                                symbol_info: Dict) -> Tuple[float, str]:
        """
        Calculate the appropriate position size based on account balance and risk parameters.

        Args:
            account_balance (float): Available account balance
            entry_price (float): Entry price for the trade
            stop_loss (float, optional): Stop loss price
            leverage (int): Requested leverage
            symbol_info (dict): Symbol information from exchange

        Returns:
            tuple: (position_size, message) - The calculated position size and any relevant message
        """
        try:
            # Cap leverage to maximum
            effective_leverage = min(leverage, self.max_leverage)
            print(f"Effective leverage: {effective_leverage}")

            # Calculate risk amount (how much we're willing to lose on this trade)
            risk_amount = account_balance * self.default_risk_percent

            # Get min notional and quantity precision from symbol info
            min_notional = float(symbol_info.get('minNotional', 10.0))  # Default to 10 if not found
            precision = int(symbol_info.get('quantityPrecision', 3))  # Default to 3 decimals

            # Calculate position size based on stop loss if provided
            if stop_loss and stop_loss > 0:
                # Calculate risk per unit
                risk_per_unit = abs(entry_price - stop_loss)

                if risk_per_unit <= 0:
                    logger.warning("Stop loss too close to entry; using default sizing")
                    # Fallback: use 10% of available balance with leverage
                    position_value = account_balance * 0.1 * effective_leverage
                    position_size = position_value / entry_price
                else:
                    # Calculate position size based on risk amount and price difference
                    position_size = (risk_amount * effective_leverage) / risk_per_unit
            else:
                # No stop loss provided, use conservative sizing
                # Use a small percentage of account with leverage
                position_value = account_balance * 0.05 * effective_leverage
                position_size = position_value / entry_price

                message = "No stop loss provided; using conservative position sizing"
                logger.info(message)

            # Ensure minimum notional value
            notional_value = position_size * entry_price
            if notional_value < min_notional:
                position_size = min_notional / entry_price
                message = f"Increased position size to meet minimum notional value of {min_notional}"
                logger.info(message)

            # Round to appropriate precision for the symbol
            position_size = round(position_size, precision)

            return position_size, "Position size calculated successfully"

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            # Return a safe minimal position size as fallback
            return 0.01, f"Error in position sizing: {str(e)}"

    def validate_risk_parameters(self,
                                 signal: Dict,
                                 account_balance: float) -> Tuple[bool, str]:
        """
        Validate that the signal's risk parameters are acceptable.

        Args:
            signal (dict): The parsed signal
            account_balance (float): Available account balance

        Returns:
            tuple: (is_valid, message) - Whether the risk is acceptable and any message
        """
        try:
            entry_price = signal.get('entry_price', 0)
            stop_loss = signal.get('stop_loss')
            leverage = signal.get('leverage', 1)

            # Check if leverage is within acceptable range
            if leverage > self.max_leverage:
                return False, f"Leverage {leverage}x exceeds maximum allowed ({self.max_leverage}x)"

            # If no stop loss, flag as higher risk
            if not stop_loss:
                return True, "Warning: No stop loss provided. Trade executed with default protection."

            # Calculate potential loss percentage
            price_move_pct = abs(entry_price - stop_loss) / entry_price * 100
            potential_loss_pct = price_move_pct * leverage

            # If potential loss percentage is too high, reject the trade
            if potential_loss_pct > 80:  # 80% loss is very high
                return False, f"Potential loss of {potential_loss_pct:.2f}% is too high"

            # If potential loss percentage is high but not extreme, warn
            if potential_loss_pct > 50:
                return True, f"Warning: High risk trade with potential {potential_loss_pct:.2f}% loss"

            return True, "Risk parameters acceptable"

        except Exception as e:
            logger.error(f"Error validating risk parameters: {e}")
            return False, f"Error validating risk: {str(e)}"