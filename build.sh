#!/bin/bash
# Installation script for the Bybit Telegram Trading Bot

# Text formatting
BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

echo -e "${BOLD}🤖 Bybit Telegram Trading Bot Setup${NC}"
echo -e "======================================="

# Check Python version
echo -e "\n${BOLD}Checking Python version...${NC}"
python_version=$(python3 --version 2>&1)
if [[ $python_version =~ "Python 3" ]]; then
    echo -e "${GREEN}✅ Python 3 is installed: $python_version${NC}"
else
    echo -e "${RED}❌ Python 3 is required but not found.${NC}"
    echo -e "Please install Python 3.7 or higher and try again."
    exit 1
fi

# Create virtual environment
echo -e "\n${BOLD}Setting up virtual environment...${NC}"
if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠️ Virtual environment already exists.${NC}"
    read -p "Do you want to recreate it? (y/n): " recreate_venv
    if [[ $recreate_venv == "y" || $recreate_venv == "Y" ]]; then
        echo "Removing existing virtual environment..."
        rm -rf venv
        python3 -m venv venv
        echo -e "${GREEN}✅ Virtual environment created.${NC}"
    else
        echo "Using existing virtual environment."
    fi
else
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created.${NC}"
fi

# Activate virtual environment
echo -e "\n${BOLD}Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}✅ Virtual environment activated.${NC}"

# Install dependencies
echo -e "\n${BOLD}Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to install dependencies. Check internet connection and requirements.txt file.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Dependencies installed.${NC}"

# Create necessary directories
echo -e "\n${BOLD}Creating necessary directories...${NC}"
mkdir -p logs
echo -e "${GREEN}✅ Directories created.${NC}"

# Check for .env file and create if needed
echo -e "\n${BOLD}Checking for configuration...${NC}"
if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠️ .env file already exists.${NC}"
else
    echo -e "${YELLOW}⚠️ .env file not found.${NC}"
    if [ -f ".env.sample" ]; then
        read -p "Do you want to create .env from .env.sample? (y/n): " create_env
        if [[ $create_env == "y" || $create_env == "Y" ]]; then
            cp .env.sample .env
            echo -e "${GREEN}✅ .env file created from template.${NC}"
            echo -e "${YELLOW}⚠️ Please edit the .env file with your configuration settings.${NC}"
        else
            echo -e "${YELLOW}⚠️ Please create .env file manually.${NC}"
        fi
    else
        echo -e "${YELLOW}Creating basic .env.sample file...${NC}"
        cat > .env.sample << 'EOL'
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
SOURCE_CHANNEL_ID=YOUR_SOURCE_CHANNEL_ID
TARGET_CHANNEL_ID=YOUR_TARGET_CHANNEL_ID
API_ID=YOUR_TELEGRAM_API_ID
API_HASH=YOUR_TELEGRAM_API_HASH
BINANCE_API_KEY=YOUR_BINANCE_API_KEY
BINANCE_API_SECRET_KEY=YOUR_BINANCE_API_SECRET_KEY

# Risk management settings
DEFAULT_RISK_PERCENT=2.0
MAX_LEVERAGE=20

# Trading settings
ENABLE_AUTO_SL=true
AUTO_SL_PERCENT=5.0
DEFAULT_TP_PERCENT=20.0
DEFAULT_SL_PERCENT=100.0

# Logging settings
LOG_LEVEL=INFO
LOG_FILE=logs/trading_bot.log

QUOTE_ASSET=USDT
WALLET_RATIO=10

# Profit reporting
ENABLE_PROFIT_REPORTING=true

# Position management
CLOSE_POSITIONS_AFTER_TRADE=true
POSITION_MONITOR_TIMEOUT=3600

# Notification settings
ENABLE_ENTRY_NOTIFICATIONS=true
ENABLE_PROFIT_NOTIFICATIONS=true
ENABLE_FAILURE_NOTIFICATIONS=true
SEND_PROFIT_ONLY_FOR_MANUAL_EXITS=true
EOL
        echo -e "${GREEN}✅ .env.sample file created.${NC}"
        
        read -p "Do you want to create .env from the new template? (y/n): " create_env
        if [[ $create_env == "y" || $create_env == "Y" ]]; then
            cp .env.sample .env
            echo -e "${GREEN}✅ .env file created from template.${NC}"
            echo -e "${YELLOW}⚠️ Please edit the .env file with your configuration settings.${NC}"
        else
            echo -e "${YELLOW}⚠️ Please create .env file manually.${NC}"
        fi
    fi
fi

echo -e "\n${GREEN}${BOLD}Installation complete!${NC}"
echo -e "\nTo start the bot, run:"
echo -e "${BOLD}source venv/bin/activate${NC}"
echo -e "${BOLD}python main.py${NC}"
echo -e "\n${YELLOW}⚠️ IMPORTANT:${NC} Ensure you have configured your .env file with correct credentials before starting."
echo -e "Particularly these required settings:"
echo -e "  - BOT_TOKEN: Your Telegram Bot token"
echo -e "  - SOURCE_CHANNEL_ID: Channel ID to monitor for signals"
echo -e "  - TARGET_CHANNEL_ID: Channel ID to send formatted signals"
echo -e "  - API_ID & API_HASH: Your Telegram API credentials"
echo -e "  - BINANCE_API_KEY & BINANCE_API_SECRET_KEY: Your Binance API credentials"