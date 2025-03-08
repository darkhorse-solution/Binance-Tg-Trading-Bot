# 📊 Crypto Trading Signal Bot

A robust, class-based Telegram bot for monitoring, parsing, and automatically executing cryptocurrency trading signals from Telegram channels on Binance Futures.

## Features

- **Telegram Integration**: Monitor source channels for trading signals and forward formatted signals to target channels
- **Signal Parsing**: Parse crypto trading signals with stop-loss and take-profit targets
- **Binance Trading**: Automatically execute trades with proper risk management
- **Risk Management**: Calculate appropriate position sizes and enforce risk limits
- **Order Management**: Handle entry orders, stop-losses, and multiple take-profit targets

## Project Structure

```
├── main.py                 # Entry point
├── .env                    # Configuration (create from .env.sample)
├── requirements.txt        # Dependencies
├── trading/                # Trading functionality
│   ├── __init__.py
│   ├── bot.py              # Main trading bot class
│   ├── signal.py           # Signal parsing and formatting
│   ├── trader.py           # Binance trading functionality
│   └── risk.py             # Risk management functionality
├── telegram/               # Telegram functionality (legacy)
│   └── __init__.py
├── utils/                  # Utility modules
│   ├── __init__.py
│   ├── config.py           # Configuration handling
│   └── logger.py           # Logging functionality
└── logs/                   # Log files
```

## Setup

1. Clone the repository
2. Install dependencies
   ```
   pip install -r requirements.txt
   ```
3. Create `.env` file from template
   ```
   cp .env.sample .env
   ```
4. Fill in your configuration in the `.env` file
5. Run the bot
   ```
   python main.py
   ```

## Configuration

The bot can be configured through environment variables in the `.env` file:

### Required Settings

- `API_ID`: Telegram API ID (from [my.telegram.org/apps](https://my.telegram.org/apps))
- `API_HASH`: Telegram API hash
- `SOURCE_CHANNEL_ID`: Channel ID to monitor for signals (with negative sign)
- `TARGET_CHANNEL_ID`: Channel ID to send formatted signals (with negative sign)
- `BINANCE_API_KEY`: Binance API key
- `BINANCE_API_SECRET_KEY`: Binance API secret key

### Optional Settings

- `SESSION_STRING`: Telegram session string (generated on first run)
- `DEFAULT_RISK_PERCENT`: Percentage of account to risk per trade (default: 2.0)
- `MAX_LEVERAGE`: Maximum leverage to use (default: 20)
- `ENABLE_AUTO_SL`: Enable automatic stop loss if not provided in signal (default: true)
- `AUTO_SL_PERCENT`: Automatic stop loss percentage (default: 5.0)
- `LOG_LEVEL`: Logging level - DEBUG, INFO, WARNING, ERROR, or CRITICAL (default: INFO)
- `LOG_FILE`: Path to log file (default: logs/trading_bot.log)

## Signal Format

The bot expects trading signals in the following format:

```
BTCUSDT Long 10x
Entry price - 50000
SL - 48000
TP1 - 51000 (20%)
TP2 - 52000 (30%)
TP3 - 53000 (30%)
TP4 - 54000 (20%)
```

## Disclaimer

This bot is for educational purposes only. Use at your own risk. Cryptocurrency trading involves significant risk and can result in the loss of your invested capital.

## License

MIT