import re
from utils.logger import logger
from typing import Dict, List, Optional, Any, Tuple

def extract_pair(s):
    """Extract uppercase letters and numbers from a string (for trading pairs)"""
    return "".join(re.findall(r"[A-Z0-9]+", s))

def clean_text(text):
    """Remove formatting characters like bold asterisks"""
    # Remove markdown formatting
    cleaned = re.sub(r'\*+', '', text)
    # Remove other potential formatting
    cleaned = re.sub(r'__|\||\~\~', '', cleaned)
    return cleaned

def extract_number(text):
    """Extract the first number (with decimals) from text"""
    match = re.search(r'(\d+\.?\d*)', text)
    if match:
        return float(match.group(1))
    return None


class SignalParser:
    """
    Class for parsing trading signals from telegram messages,
    supporting multiple formats including Russian language signals.
    """

    def parse(self, message: str) -> Optional[Dict[str, Any]]:
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

        # Try to parse Russian format signal
        try:
            russian_format = self._try_parse_russian_format(clean_message)
            if russian_format:
                logger.info("Successfully parsed as Russian signal format")
                return russian_format
        except Exception as e:
            logger.error(f"Error trying to parse as Russian format: {e}")
        
        # Try to parse the new signal format with explicit targets and stoploss
        try:
            new_format_signal = self._try_parse_new_format(clean_message)
            if new_format_signal:
                logger.info("Successfully parsed as new signal format")
                return new_format_signal
        except Exception as e:
            logger.error(f"Error trying to parse as new format signal: {e}")
        
        # If not, continue with the standard signal parsing
        try:
            standard_format = self._try_parse_standard_format(clean_message)
            if standard_format:
                logger.info("Successfully parsed as standard format")
                return standard_format
        except Exception as e:
            logger.error(f"Error parsing standard message: {e}")
            
        return None
    
    def _try_parse_russian_format(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Try to parse Russian format signals:
        
        Example 1:
        🪙 МОНЕТА: #ADA/USDT  
        📉📈ПОКУПКА: SHORT
        ПЛЕЧО: 20х
        · Вход: 0.686$
        · Фиксируем прибыль на: 0.6774$, 0.6688$, 0.6517$ 
        · Стоп: 0.734$
        
        Example 2:
        🪙МОНЕТА: #LINK/USDT  
        📉📈ПОКУПКА: SHORT LIMIT ORDER! 
         ПЛЕЧО: 18х
        · Вход: 14.57$
        · Фиксируем прибыль на: 14.161$ 
        · Стоп: 15.703$
        
        Args:
            message (str): The message text to parse
            
        Returns:
            dict: Parsed signal data or None if not matching format
        """
        logger.info(f"Trying to parse as Russian format: {message}")
        
        # Split message into lines and remove empty lines
        lines = [line.strip() for line in message.split('\n') if line.strip()]
        
        # Need at least 4 lines for this format
        if len(lines) < 4:
            return None
            
        symbol = None
        position_type = None
        leverage = None
        entry_price = None
        stop_loss = None
        take_profit_levels = []
        is_limit_order = False
        
        # Extract trading pair (look for # followed by pair)
        for line in lines:
            match = re.search(r'#([A-Z0-9]+/[A-Z0-9]+)', line)
            if match:
                symbol = match.group(1)
                break
        
        if not symbol:
            return None
        
        # Extract position type (SHORT or LONG)
        for line in lines:
            if 'ПОКУПКА' in line or 'КУПИТЬ' in line:
                # Check for LIMIT ORDER special case
                if 'LIMIT ORDER' in line.upper():
                    is_limit_order = True
                    logger.info(f"Detected LIMIT ORDER in signal")
                    
                if 'SHORT' in line or 'ШОРТ' in line:
                    position_type = 'SHORT'
                elif 'LONG' in line or 'ЛОНГ' in line:
                    position_type = 'LONG'
                break
        
        if not position_type:
            return None
        
        # Extract leverage (look for number followed by x or х - Cyrillic 'x')
        for line in lines:
            if 'ПЛЕЧО' in line:
                match = re.search(r'(\d+)[xх]', line)
                if match:
                    leverage = int(match.group(1))
                    break
        
        if not leverage:
            return None
        
        # Extract entry price
        for line in lines:
            if 'Вход' in line:
                match = re.search(r'(\d+\.?\d*)\$?', line)
                if match:
                    entry_price = float(match.group(1))
                    break
        
        if not entry_price:
            return None
        
        # Extract stop loss
        for line in lines:
            if 'Стоп' in line:
                match = re.search(r'(\d+\.?\d*)\$?', line)
                if match:
                    stop_loss = float(match.group(1))
                    break
        
        # Extract take profit levels
        for line in lines:
            if 'прибыль' in line or 'Фиксируем' in line:
                # Find all numbers in the line
                profits = re.findall(r'(\d+\.?\d*)\$?', line)
                if profits:
                    # Clean up profits list - make sure they're valid numbers
                    cleaned_profits = []
                    for p in profits:
                        try:
                            cleaned_profits.append(float(p))
                        except:
                            pass
                    
                    if cleaned_profits:
                        profits = cleaned_profits
                        
                        # Special handling for LIMIT ORDER signals - use only 0.5% of TP
                        if is_limit_order:
                            # For limit order signals, use only the first take profit
                            # and allocate 0.5% of position to it
                            take_profit_levels.append({
                                'price': float(profits[0]),
                                'percentage': 0.5  # 0.5% as requested
                            })
                            logger.info(f"LIMIT ORDER signal: Using TP at {profits[0]} with 0.5% allocation")
                        else:
                            # For normal signals, assign percentages evenly between take profits
                            tp_count = len(profits)
                            percentage_per_tp = 100 / tp_count if tp_count > 0 else 100
                            
                            for price in profits:
                                take_profit_levels.append({
                                    'price': float(price),
                                    'percentage': percentage_per_tp
                                })
                    break
        
        # Convert symbol format from X/Y to XY for Binance
        binance_symbol = symbol.replace('/', '')
        
        # Successfully parsed the Russian format
        logger.info(f"Successfully parsed Russian format: {symbol} {position_type} x{leverage}")
        
        return {
            'symbol': symbol,
            'binance_symbol': binance_symbol,
            'position_type': position_type,
            'leverage': leverage,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit_levels': take_profit_levels,
            'original_message': message,
            'is_profit_message': False,
            'is_russian_format': True,
            'use_limit_order': True if is_limit_order else True,  # Always use limit order for Russian signals
            'is_limit_order_signal': is_limit_order  # Flag specifically for limit order signals
        }
    
    def _try_parse_profit_message(self, message: str) -> Optional[Dict[str, Any]]:
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

    def _try_parse_new_format(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Try to parse the new signal format with explicit targets and stoploss.
        Example format:
        ⌛️#NEAR/USDT  ( LONG )
        🍁 Leverage 👉 20X to 25X
        ⛩️ Entry ➡️ 2.019 - 2.024
        💠 Targets :- 2.043 | 2.065 | 2.083 | 2.103 | 2.124 | 2.153
        🔕 Stoploss = 1.90
        
        Args:
            message (str): The message text to parse
            
        Returns:
            dict: Parsed signal data or None if not matching format
        """
        # Split message into lines and remove empty lines
        lines = [line.strip() for line in message.split('\n') if line.strip()]
        
        # Need at least 4 lines for this format
        if len(lines) < 4:
            return None
            
        # First line should contain the trading pair and position type
        first_line = lines[0]
        
        # Look for trading pair in the format XXX/USDT
        pairs = re.findall(r'([A-Z0-9]+)/([A-Z0-9]+)', first_line)
        if not pairs:
            return None
            
        # Extract symbol
        pair = pairs[0]
        symbol = f"{pair[0]}/{pair[1]}"
        logger.info(f"New format - Found symbol: {symbol}")
        
        # Extract position type
        position_type = None
        if 'LONG' in first_line or '(LONG)' in first_line or '( LONG )' in first_line:
            position_type = 'LONG'
        elif 'SHORT' in first_line or '(SHORT)' in first_line or '( SHORT )' in first_line:
            position_type = 'SHORT'
            
        if not position_type:
            return None
        logger.info(f"New format - Found position type: {position_type}")
        
        # Extract leverage from second line
        leverage_line = next((line for line in lines if 'Leverage' in line or 'leverage' in line), None)
        if not leverage_line:
            return None
            
        # Try to find the leverage value (take the lower one if a range is given)
        leverage_match = re.search(r'(\d+)[Xx]', leverage_line)
        if not leverage_match:
            return None
            
        leverage = int(leverage_match.group(1))
        logger.info(f"New format - Found leverage: {leverage}")
        
        # Extract entry price from "Entry" line
        entry_line = next((line for line in lines if 'Entry' in line), None)
        if not entry_line:
            return None
            
        # Try to find entry price range
        entry_prices = re.findall(r'(\d+\.\d+)', entry_line)
        if not entry_prices or len(entry_prices) < 1:
            return None
            
        # If we have a range, store both values; if single value, store it twice
        entry_price_low = float(entry_prices[0])
        entry_price_high = float(entry_prices[1]) if len(entry_prices) >= 2 else entry_price_low
            
        logger.info(f"New format - Found entry price range: {entry_price_low} - {entry_price_high}")
        
        # Extract targets from the "Targets" line
        targets_line = next((line for line in lines if 'Targets' in line or 'targets' in line or 'Target' in line), None)
        if not targets_line:
            return None
            
        # Find all target prices
        target_prices = re.findall(r'(\d+\.\d+)', targets_line)
        if not target_prices or len(target_prices) < 1:
            return None
            
        logger.info(f"New format - Found {len(target_prices)} targets")
        
        # Calculate percentages for each target
        tp_levels = []
        total_targets = len(target_prices)
        
        # Default to equal distribution of percentage
        percentage_per_target = 100 / total_targets
        
        for i, price in enumerate(target_prices):
            tp_levels.append({
                'price': float(price),
                'percentage': percentage_per_target
            })
            
        # Extract stoploss from "Stoploss" line
        sl_line = next((line for line in lines if 'Stoploss' in line or 'stoploss' in line or 'SL' in line), None)
        stop_loss = None
        
        if sl_line:
            sl_match = re.search(r'(\d+\.\d+)', sl_line)
            if sl_match:
                stop_loss = float(sl_match.group(1))
                logger.info(f"New format - Found stop loss: {stop_loss}")
        
        # Convert symbol format for Binance
        binance_symbol = symbol.replace('/', '')
        
        # Successfully parsed new format signal
        return {
            'symbol': symbol,
            'binance_symbol': binance_symbol,
            'position_type': position_type,
            'leverage': leverage,
            'entry_price_low': entry_price_low,
            'entry_price_high': entry_price_high,
            'entry_price': (entry_price_low + entry_price_high) / 2,  # Average for compatibility
            'stop_loss': stop_loss,
            'take_profit_levels': tp_levels,
            'original_message': message,
            'is_profit_message': False,
            'is_entry_range': True,  # Flag for entry price range
            'target_prices': [float(price) for price in target_prices]  # Store original targets
        }

    def _try_parse_standard_format(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Parse the standard signal format.
        
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
                'take_profit_levels': tp_levels,
                'original_message': message,
                'is_profit_message': False
            }

        except Exception as e:
            logger.error(f"Error parsing standard message: {e}")
            return None