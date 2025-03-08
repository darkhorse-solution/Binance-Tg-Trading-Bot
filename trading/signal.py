import re
from utils.logger import logger

def extract_pair(s):
    # Extract only uppercase letters
    return "".join(re.findall(r"[A-Z]+", s))

class SignalParser:
    """
    Class for parsing trading signals from telegram messages.
    """

    def parse(self, message: str):
        """
        Parse a trading signal message from Telegram.

        Args:
            message (str): The message text to parse

        Returns:
            dict: Parsed signal data or None if parsing failed
        """
        try:
            # Split message into lines and remove empty lines
            lines = [line.strip() for line in message.split('\n') if line.strip()]

            # First line should contain trading pair and leverage
            first_line = lines[0]

            # Look for trading pair (any word containing /)
            symbol = next((word for word in first_line.split() if '/' in word), None)
            symbol = extract_pair(symbol)
            if not symbol:
                return None

            # Position type
            position_type = 'LONG' if 'Long' in first_line else 'SHORT' if 'Short' in first_line else None
            if not position_type:
                return None

            # Find leverage (number followed by x)
            leverage = None
            for word in first_line.split():
                if 'x' in word.lower():
                    try:
                        leverage = int(''.join(filter(str.isdigit, word)))
                        break
                    except:
                        continue
            if not leverage:
                return None

            # Entry price - look for number in second line
            try:
                entry_price = float(''.join(c for c in lines[1].split('-')[1] if c.isdigit() or c == '.'))
            except:
                return None

            # Extract stop loss - look for "SL" or "Stop Loss" in the message
            stop_loss = None
            for line in lines:
                if 'SL' in line or 'Stop Loss' in line or 'Stop-Loss' in line:
                    try:
                        # Find first number in line for stop loss price
                        stop_loss = float(''.join(c for c in line.split('-')[1] if c.isdigit() or c == '.'))
                        break
                    except:
                        continue

            # Take profit levels - look for numbers and percentages
            tp_levels = []
            for line in lines[3:7]:  # Expect up to 4 TP levels
                try:
                    # Find first number in line for price
                    numbers = ''.join(c for c in line if c.isdigit() or c == '.')
                    price = float(numbers)

                    # Find percentage
                    percentage = int(''.join(filter(str.isdigit, line.split('(')[1].split('%')[0])))

                    tp_levels.append({
                        'price': price,
                        'percentage': percentage
                    })
                except:
                    continue

            if len(tp_levels) < 1:
                return None

            # Convert symbol format from X/Y to XY for Binance
            binance_symbol = symbol.replace('/', '')

            return {
                'symbol': symbol,
                'binance_symbol': binance_symbol,
                'position_type': position_type,
                'leverage': leverage,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit_levels': tp_levels
            }

        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return None


class SignalFormatter:
    """
    Class for formatting parsed signals into readable messages.
    """

    def format(self, signal):
        """
        Format a parsed trading signal into a readable message for Binance trading.

        Args:
            signal (dict): The parsed signal data

        Returns:
            str: Formatted message
        """
        # Format position type for better visibility
        position_emoji = "🟢" if signal['position_type'] == "LONG" else "🔴"
        position_display = f"{position_emoji} {signal['position_type']}"

        # Calculate total profit percentage
        total_profit_percentage = sum(tp['percentage'] for tp in signal['take_profit_levels'])

        formatted_message = (
            f"📊 BINANCE SIGNAL\n\n"
            f"Pair: {signal['symbol']}\n"
            f"Position: {position_display}\n"
            f"Leverage: {signal['leverage']}x\n"
            f"Entry: {signal['entry_price']}\n"
        )

        # Add stop loss if available
        if signal.get('stop_loss'):
            formatted_message += f"Stop Loss: {signal['stop_loss']}\n"

        formatted_message += "\nTake Profit Targets:\n"

        for i, tp in enumerate(signal['take_profit_levels'], 1):
            formatted_message += f"TP{i}: {tp['price']} ({tp['percentage']}%)\n"

        formatted_message += f"\nTotal Profit: {total_profit_percentage}%\n"
        formatted_message += f"\n#Binance #{signal['binance_symbol']}"

        return formatted_message