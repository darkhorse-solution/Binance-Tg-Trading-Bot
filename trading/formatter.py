def format_trading_signal(signal):
    """
    Legacy format function - disabled in favor of new messaging system.
    This is kept for compatibility with existing code but will not 
    send duplicate messages if entry notifications are enabled.
    
    Args:
        signal (dict): The parsed signal data

    Returns:
        str: Empty string when entry notifications are enabled, or formatted message when disabled
    """
    from utils.config import Config
    
    # If entry notifications are enabled, don't send duplicates
    if Config.ENABLE_ENTRY_NOTIFICATIONS:
        return ""
    
    # Otherwise use the original formatting for backward compatibility
    position_emoji = "🟢" if signal['position_type'] == "LONG" else "🔴"
    position_display = f"{position_emoji} {signal['position_type']}"

    # Calculate total profit percentage
    total_profit_percentage = sum(tp['percentage'] for tp in signal['take_profit_levels'])

    formatted_message = (
        f"📊 BINANCE SIGNAL\n\n"
        f"Pair: {signal['symbol']}\n"
        f"Position: {position_display}\n"
        f"Leverage: {signal['leverage']}x\n"
        f"Entry: {signal['entry_price']}\n\n"
        f"Take Profit Targets:\n"
    )

    for i, tp in enumerate(signal['take_profit_levels'], 1):
        formatted_message += f"TP{i}: {tp['price']} ({tp['percentage']}%)\n"

    formatted_message += f"\nTotal Profit: {total_profit_percentage}%\n"
    formatted_message += f"\n#Binance #{signal['symbol'].replace('/', '')}"

    return formatted_message