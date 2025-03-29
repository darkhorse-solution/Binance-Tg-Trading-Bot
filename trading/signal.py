import re
from utils.logger import logger

def extract_pair(s):
    # Extract uppercase letters AND numbers
    return "".join(re.findall(r"[A-Z0-9]+", s))

def clean_text(text):
    """Remove formatting characters like bold asterisks"""
    # Remove markdown formatting
    cleaned = re.sub(r'\*+', '', text)
    # Remove other potential formatting
    cleaned = re.sub(r'__|\||\~\~', '', cleaned)
    return cleaned

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
        # Clean the message to remove formatting
        clean_message = clean_text(message)
        logger.info(f"Cleaned message: {clean_message}")
        
        # First, try to identify if this is a profit target message format
        try:
            profit_message = self._try_parse_profit_message(clean_message)
            if profit_message:
                logger.info("Successfully parsed as profit message format")
                return profit_message
        except Exception as e:
            logger.error(f"Error trying to parse as profit message: {e}")
        
        # If not, continue with the standard signal parsing
        try:
            # Split message into lines and remove empty lines
            lines = [line.strip() for line in clean_message.split('\n') if line.strip()]

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
                'take_profit_levels': tp_levels,
                'original_message': message,
                'is_profit_message': False
            }

        except Exception as e:
            logger.error(f"Error parsing standard message: {e}")
            return None

    def _try_parse_profit_message(self, message: str):
        """
        Try to parse a profit target message format like:
        #PLUME/USDT (Short📉, x20)
        ✅ Price - 0.1724
        🔝 Profit - 60%

        Args:
            message (str): The message text to parse

        Returns:
            dict: Parsed profit message data or None if not matching format
        """
        logger.info(f"Trying to parse as profit message: {message}")
        
        # Split message into lines and remove empty lines
        lines = [line.strip() for line in message.split('\n') if line.strip()]
        
        # Need at least 3 lines for this format
        if len(lines) < 3:
            logger.info("Not enough lines for profit message format")
            return None
        
        # First line should contain symbol, position direction and leverage
        first_line = lines[0]
        
        # Look for any crypto pair in the format XXX/YYY
        # This is a very generic approach that should work regardless of formatting
        pairs = re.findall(r'([A-Z0-9]+)/([A-Z0-9]+)', first_line)
        if not pairs:
            logger.info(f"No trading pair found in line: {first_line}")
            return None
            
        # Use the first pair found
        pair = pairs[0]
        symbol = f"{pair[0]}/{pair[1]}"
        logger.info(f"Found symbol: {symbol}")
        
        # Extract position type - be very flexible
        position_type = None
        if re.search(r'short|📉', first_line.lower()):
            position_type = 'SHORT'
        elif re.search(r'long|📈', first_line.lower()):
            position_type = 'LONG'
        
        if not position_type:
            logger.info(f"No position type found in: {first_line}")
            return None
        logger.info(f"Found position type: {position_type}")
        
        # Extract leverage - look for digits next to 'x'
        leverage_match = re.search(r'x\s*(\d+)', first_line)
        if not leverage_match:
            logger.info(f"No leverage match in: {first_line}")
            # Try a more generic approach - look for any number followed by x
            leverage_match = re.search(r'(\d+)\s*x', first_line)
            if not leverage_match:
                return None
        
        leverage = int(leverage_match.group(1))
        logger.info(f"Found leverage: {leverage}")
        
        # Look for price in any line - be very flexible
        price = None
        for line in lines:
            # Try specific pattern first
            price_match = re.search(r'price\s*[-:]\s*(\d+\.?\d*)', line.lower())
            if price_match:
                price = float(price_match.group(1))
                break
                
            # If not found, try to find any decimal number in a line with "price"
            if 'price' in line.lower():
                number_match = re.search(r'(\d+\.\d+)', line)
                if number_match:
                    price = float(number_match.group(1))
                    break
        
        if not price:
            logger.info("No price found in any line")
            return None
        logger.info(f"Found price: {price}")
        
        # Look for profit target in any line - be very flexible
        profit_target = None
        for line in lines:
            # Try specific pattern first
            profit_match = re.search(r'profit\s*[-:]\s*(\d+)[%]?', line.lower())
            if profit_match:
                profit_target = int(profit_match.group(1))
                break
                
            # If not found, try to find any percentage in a line with "profit"
            if 'profit' in line.lower():
                percent_match = re.search(r'(\d+)\s*%', line)
                if percent_match:
                    profit_target = int(percent_match.group(1))
                    break
        
        if not profit_target:
            logger.info("No profit target found in any line")
            return None
        logger.info(f"Found profit target: {profit_target}%")
        
        # Convert symbol format
        binance_symbol = symbol.replace('/', '')
        
        # Successfully parsed profit message
        logger.info(f"Successfully parsed profit message: {symbol} {position_type} x{leverage}")
        return {
            'symbol': symbol,
            'binance_symbol': binance_symbol,
            'position_type': position_type,
            'leverage': leverage,
            'entry_price': price,
            'profit_target': profit_target,
            'original_message': message,
            'is_profit_message': True
        }


class SignalFormatter:
    """
    Class for formatting parsed signals into readable messages.
    """
    def format(self, signal):
        """
        Format a signal for forwarding.
        
        Args:
            signal (dict): The parsed signal data

        Returns:
            str: Formatted message
        """
        from utils.config import Config
        
        # If this is a profit message, format it differently
        if signal.get('is_profit_message', False):
            return self.format_profit_message(signal)
        
        # If entry notifications are enabled, don't send duplicates
        if Config.ENABLE_ENTRY_NOTIFICATIONS:
            return ""
        
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
        
    def format_profit_message(self, signal):
        """
        Format a profit message signal for forwarding.
        
        Args:
            signal (dict): The parsed profit message data
            
        Returns:
            str: Formatted message
        """
        # Get correct emoji for position type
        position_emoji = "🟢" if signal['position_type'] == "LONG" else "🔴"
        
        # Format the message nicely
        formatted_message = (
            f"📊 PROFIT TARGET\n\n"
            f"Pair: {signal['symbol']}\n"
            f"Position: {position_emoji} {signal['position_type']}\n"
            f"Leverage: {signal['leverage']}x\n"
            f"Entry Price: {signal['entry_price']}\n"
            f"Target Profit: {signal['profit_target']}%\n\n"
            f"#Binance #{signal['binance_symbol']}"
        )
        
        return formatted_message