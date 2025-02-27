def format_trading_signal(signal):
    """
    Format a parsed trading signal into a readable message.

    Args:
        signal (dict): The parsed signal data

    Returns:
        str: Formatted message
    """
    formatted_message = (
        f"🎯 New Trading Signal\n\n"
        f"Symbol: {signal['symbol']}\n"
        f"Position: {signal['position_type']}\n"
        f"Leverage: {signal['leverage']}x\n"
        f"Entry Price: {signal['entry_price']}\n\n"
        f"Take Profit Levels:\n"
    )

    for i, tp in enumerate(signal['take_profit_levels'], 1):
        formatted_message += f"TP{i}: {tp['price']} ({tp['percentage']}%)\n"

    return formatted_message