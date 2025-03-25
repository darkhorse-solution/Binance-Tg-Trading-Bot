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

### Requirements

- Python 3.7 or higher (automatically installed on Ubuntu/Debian systems if not already present)
- python3-venv package for creating virtual environments (automatically installed by the setup script)
- Internet connection for downloading dependencies
- Telegram account with API access
- Bybit exchange account with API access

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
   
   The script will:
   - Check if Python 3 is installed, and attempt to install it on Ubuntu/Debian systems if needed
   - Verify and install the python3-venv package if required
   - Create a virtual environment
   - Install required dependencies
   - Create necessary directories
   - Help you set up the .env configuration file
   
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

2. Install Python and the python3-venv package (Ubuntu/Debian)
   ```bash
   sudo apt-get update
   sudo apt-get install python3 python3-venv
   ```

3. Create a virtual environment
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. Install dependencies
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. Create necessary directories
   ```bash
   mkdir -p logs
   ```

6. Create and configure your .env file
   ```bash
   cp .env.sample .env   # If .env.sample exists
   # Edit .env with your configuration
   ```

7. Run the bot
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

# Trading Settings Section Update (for README.md)

### Trading Settings

- `ENABLE_AUTO_SL`: Enable automatic stop loss if not provided in signal (default: true)
- `AUTO_SL_PERCENT`: Automatic stop loss percentage (default: 5.0)
- `DEFAULT_TP_PERCENT`: Default take profit percentage (default: 20.0)
- `DEFAULT_SL_PERCENT`: Default stop loss percentage (default: 100.0)
- `QUOTE_ASSET`: Quote asset for trading (default: USDT)

### Trading Amount Settings

The bot supports two trading modes:

- `TRADING_MODE`: Determines how trade amounts are calculated (options: "ratio" or "fixed", default: "ratio")
  - `ratio`: Calculate trade amount as a percentage of your wallet balance
  - `fixed`: Use a fixed amount for every trade

Depending on the mode selected, the following settings apply:

- When using `ratio` mode:
  - `WALLET_RATIO`: Percentage of wallet balance to use per trade (default: 10)
  
- When using `fixed` mode:
  - `CONSTANT_AMOUNT`: Fixed amount of USDT to use for each trade (default: 100.0)

Example configurations:

```
# Use 5% of wallet balance per trade
TRADING_MODE=ratio
WALLET_RATIO=5

# OR

# Use 150 USDT for every trade
TRADING_MODE=fixed
CONSTANT_AMOUNT=150.0
```
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
- **Virtual environment errors**: If you encounter issues with the virtual environment:
  ```bash
  sudo apt-get update
  sudo apt-get install python3-venv
  # For specific Python versions (e.g., Python 3.12)
  sudo apt-get install python3.12-venv
  ```
- **pip command not found**: If pip is not available after activating the virtual environment:
  ```bash
  curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
  python get-pip.py
  rm get-pip.py
  ```

## Disclaimer

This bot is for educational purposes only. Use at your own risk. Cryptocurrency trading involves significant risk and can result in the loss of your invested capital.

## License

MIT