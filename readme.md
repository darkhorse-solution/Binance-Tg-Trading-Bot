# 📊 Bybit Telegram Trading Bot

A robust, class-based Telegram bot for monitoring, parsing, and automatically executing cryptocurrency trading signals from Telegram channels on Bybit Futures.

## Features

- **Telegram Integration**: Monitor source channels for trading signals and forward formatted signals to target channels
- **Signal Parsing**: Parse crypto trading signals with stop-loss and take-profit targets
- **Bybit Trading**: Automatically execute trades with proper risk management
- **Risk Management**: Calculate appropriate position sizes and enforce risk limits
- **Order Management**: Handle entry orders, stop-losses, and multiple take-profit targets
- **Profit Reporting**: Track and report trade profits in real-time

## Project Structure

```
├── main.py                 # Entry point
├── .env                    # Configuration (created via build.sh)
├── requirements.txt        # Dependencies
├── build.sh                # Setup script
├── trading/                # Trading functionality
│   ├── __init__.py
│   ├── bot.py              # Main trading bot class
│   ├── signal.py           # Signal parsing and formatting
│   ├── trader.py           # Bybit trading functionality
│   └── risk.py             # Risk management functionality
├── telegram/               # Telegram functionality
│   └── __init__.py
├── utils/                  # Utility modules
│   ├── __init__.py
│   ├── config.py           # Configuration handling
│   └── logger.py           # Logging functionality
└── logs/                   # Log files
```

## Setup

### Quick Setup

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/Bybit-Tg-Trading-Bot.git
   cd Bybit-Tg-Trading-Bot
   ```

2. Run the setup script
   ```bash
   chmod +x build.sh
   ./build.sh
   ```
   
3. Edit the .env file with your personal credentials
   ```bash
   nano .env
   # or
   vim .env
   ```

4. Run the bot
   ```bash
   source venv/bin/activate
   python main.py
   ```

### Manual Setup

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/Bybit-Tg-Trading-Bot.git
   cd Bybit-Tg-Trading-Bot
   ```

2. Create a virtual environment
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Create necessary directories
   ```bash
   mkdir -p logs
   ```

5. Create and configure your .env file
   ```bash
   cp .env.sample .env   # If .env.sample exists
   # Edit .env with your configuration
   ```

6. Run the bot
   ```bash
   python main.py
   ```

## Configuration

The bot is configured through environment variables in the `.env` file:

### Required Settings

- `BOT_TOKEN`: Your Telegram Bot token from @BotFather
- `SOURCE_CHANNEL_ID`: Channel ID to monitor for signals (with negative sign, e.g., -1001234567890)
- `TARGET_CHANNEL_ID`: Channel ID to send formatted signals (with negative sign)
- `API_ID`: Telegram API ID (from [my.telegram.org/apps](https://my.telegram.org/apps))
- `API_HASH`: Telegram API hash
- `BINANCE_API_KEY`: Binance API key
- `BINANCE_API_SECRET_KEY`: Binance API secret key

### Risk Management Settings

- `DEFAULT_RISK_PERCENT`: Percentage of account to risk per trade (default: 2.0)
- `MAX_LEVERAGE`: Maximum leverage to use (default: 20)

### Trading Settings

- `ENABLE_AUTO_SL`: Enable automatic stop loss if not provided in signal (default: true)
- `AUTO_SL_PERCENT`: Automatic stop loss percentage (default: 5.0)
- `DEFAULT_TP_PERCENT`: Default take profit percentage (default: 20.0)
- `DEFAULT_SL_PERCENT`: Default stop loss percentage (default: 100.0)
- `QUOTE_ASSET`: Quote asset for trading (default: USDT)
- `WALLET_RATIO`: Wallet allocation ratio (default: 10)

### Position Management

- `CLOSE_POSITIONS_AFTER_TRADE`: Whether to close positions after trade (default: true)
- `POSITION_MONITOR_TIMEOUT`: Timeout for position monitoring in seconds (default: 3600)

### Notification Settings

- `ENABLE_ENTRY_NOTIFICATIONS`: Enable notifications for trade entries (default: true)
- `ENABLE_PROFIT_NOTIFICATIONS`: Enable notifications for profits (default: true)
- `ENABLE_FAILURE_NOTIFICATIONS`: Enable notifications for failures (default: true)
- `SEND_PROFIT_ONLY_FOR_MANUAL_EXITS`: Send profit notifications only for manual exits (default: true)

### Other Settings

- `LOG_LEVEL`: Logging level - DEBUG, INFO, WARNING, ERROR, or CRITICAL (default: INFO)
- `LOG_FILE`: Path to log file (default: logs/trading_bot.log)
- `SESSION_STRING`: Telegram session string (generated on first run)

## Getting Telegram API Credentials

1. Go to [my.telegram.org/apps](https://my.telegram.org/apps)
2. Log in with your phone number
3. Create a new application if you don't have one
4. Note down the `api_id` and `api_hash` values

## Getting Channel IDs

To get a Telegram channel ID:

1. Forward a message from the channel to @username_to_id_bot
2. The bot will reply with the channel ID
3. Make sure to include the negative sign in your .env file (e.g., -1001234567890)

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

## Troubleshooting

- **Bot not responding**: Check if your Telegram API credentials and bot token are correct
- **Trades not executing**: Verify your Binance API keys have trading permissions enabled
- **Missing signals**: Ensure the bot has access to the source channel

## Disclaimer

This bot is for educational purposes only. Use at your own risk. Cryptocurrency trading involves significant risk and can result in the loss of your invested capital.

## License

MIT