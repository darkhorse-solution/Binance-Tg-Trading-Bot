from typing import re

from utils.logger import logger


def parse_trading_signal(message: str):
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
        symbol = "".join(re.findall(r"[A-Z]", symbol))
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

        # Take profit levels - look for numbers and percentages
        tp_levels = []
        for line in lines[3:7]:  # Expect 4 TP levels
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

        if len(tp_levels) != 4:
            return None

        return {
            'symbol': symbol,
            'position_type': position_type,
            'leverage': leverage,
            'entry_price': entry_price,
            'take_profit_levels': tp_levels
        }

    except Exception as e:
        logger.error(f"Error parsing message: {e}")
        return None