import re
from utils.logger import logger
from utils.config import Config


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
        # If this is a profit message, format it differently
        if signal.get('is_profit_message', False):
            return self.format_profit_message(signal)
            
        # If this is a Russian format signal, format it accordingly
        if signal.get('is_russian_format', False):
            return self.format_russian_signal(signal)
        
        # If entry notifications are enabled, don't send duplicates
        if Config.ENABLE_ENTRY_NOTIFICATIONS:
            return ""
        
        # Format position type for better visibility
        position_emoji = "🟢" if signal['position_type'] == "LONG" else "🔴"
        position_display = f"{position_emoji} {signal['position_type']}"

        # Calculate total profit percentage
        total_profit_percentage = sum(tp['percentage'] for tp in signal['take_profit_levels'])

        # Handle entry price range if present
        if signal.get('is_entry_range', False):
            entry_price_display = f"{signal['entry_price_low']} - {signal['entry_price_high']}"
        else:
            entry_price_display = f"{signal['entry_price']}"

        formatted_message = (
            f"📊 BINANCE SIGNAL\n\n"
            f"Pair: {signal['symbol']}\n"
            f"Position: {position_display}\n"
            f"Leverage: {signal['leverage']}x\n"
            f"Entry: {entry_price_display}\n"
        )

        # Add stop loss if available
        if signal.get('stop_loss'):
            formatted_message += f"Stop Loss: {signal['stop_loss']}\n"

        formatted_message += "\nTake Profit Targets:\n"

        for i, tp in enumerate(signal['take_profit_levels'], 1):
            formatted_message += f"TP{i}: {tp['price']} ({tp['percentage']:.1f}%)\n"

        formatted_message += f"\nTotal Profit: {total_profit_percentage:.1f}%\n"
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
        
    def format_russian_signal(self, signal):
        """
        Format a Russian format signal for forwarding.
        
        Args:
            signal (dict): The parsed Russian format signal
            
        Returns:
            str: Formatted message
        """
        # Get correct emoji for position type
        position_emoji = "🟢" if signal['position_type'] == "LONG" else "🔴"
        position_display = f"{position_emoji} {signal['position_type']}"
        
        # Calculate total profit percentage
        total_profit_percentage = sum(tp['percentage'] for tp in signal['take_profit_levels'])
        
        # Format according to TP mode
        tp_mode = Config.RUSSIAN_TP_MODE.lower()
        if tp_mode == "average" and len(signal['take_profit_levels']) > 0:
            # For average mode, calculate the average TP price
            avg_tp_price = sum(tp['price'] for tp in signal['take_profit_levels']) / len(signal['take_profit_levels'])
            tp_description = f"Take Profit (Average): {avg_tp_price:.6f}\n"
        else:
            # For other modes, list all TPs
            tp_description = "Take Profit Targets:\n"
            for i, tp in enumerate(signal['take_profit_levels'], 1):
                tp_description += f"TP{i}: {tp['price']:.6f}"
                if tp.get('percentage'):
                    tp_description += f" ({tp['percentage']:.1f}%)"
                tp_description += "\n"
        
        # Build the full message
        formatted_message = (
            f"📊 TRADE SIGNAL (RU)\n\n"
            f"Pair: {signal['symbol']}\n"
            f"Position: {position_display}\n"
            f"Leverage: {signal['leverage']}x\n"
            f"Entry Price: {signal['entry_price']:.6f}\n"
        )
        
        # Add order type information
        if signal.get('use_limit_order', False):
            formatted_message += f"Order Type: LIMIT\n"
        
        # Add stop loss if available
        if signal.get('stop_loss'):
            formatted_message += f"Stop Loss: {signal['stop_loss']:.6f}\n"
            
        # Add take profit information
        formatted_message += f"\n{tp_description}"
        
        # Add total profit potential
        formatted_message += f"Total Profit: {total_profit_percentage:.1f}%\n"
        
        # Add hashtags
        formatted_message += f"\n#Binance #{signal['binance_symbol']} #RussianSignal"
        
        return formatted_message