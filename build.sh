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
    
    # Extract Python version
    python_version_number=$(echo $python_version | grep -oP '(?<=Python 3\.)\d+')
    
    # Check if python3-venv is installed
    echo -e "\n${BOLD}Checking for python3-venv package...${NC}"
    if ! dpkg -l | grep -q "python3.*-venv"; then
        echo -e "${YELLOW}⚠️ python3-venv package is not installed.${NC}"
        
        # Check if user has sudo privileges
        if command -v sudo >/dev/null 2>&1; then
            echo -e "${YELLOW}Installing python3-venv package...${NC}"
            if [[ -n "$python_version_number" ]]; then
                sudo apt-get update
                sudo apt-get install -y python3.$python_version_number-venv
                if [ $? -ne 0 ]; then
                    echo -e "${YELLOW}Specific version package not found. Installing generic python3-venv...${NC}"
                    sudo apt-get install -y python3-venv
                fi
            else
                sudo apt-get update
                sudo apt-get install -y python3-venv
            fi
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}❌ Failed to install python3-venv package.${NC}"
                echo -e "Please install it manually using:"
                echo -e "sudo apt-get update"
                echo -e "sudo apt-get install python3-venv"
                exit 1
            fi
            echo -e "${GREEN}✅ python3-venv package installed.${NC}"
        else
            echo -e "${RED}❌ Sudo privileges required to install python3-venv.${NC}"
            echo -e "Please run:"
            echo -e "sudo apt-get update"
            echo -e "sudo apt-get install python3-venv"
            echo -e "Then run this script again."
            exit 1
        fi
    else
        echo -e "${GREEN}✅ python3-venv is already installed.${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ Python 3 is not found.${NC}"
    echo -e "Attempting to install Python 3 on Ubuntu..."
    
    # Check if we're on Ubuntu/Debian
    if [ -f /etc/lsb-release ] || [ -f /etc/debian_version ]; then
        echo -e "Ubuntu/Debian detected. Installing Python 3..."
        
        # Check if user has sudo privileges
        if command -v sudo >/dev/null 2>&1; then
            # Add deadsnakes PPA for latest Python versions
            echo -e "${YELLOW}Adding deadsnakes PPA for latest Python versions...${NC}"
            sudo apt-get update
            sudo apt-get install -y software-properties-common
            sudo add-apt-repository -y ppa:deadsnakes/ppa
            sudo apt-get update
            
            # Install Python 3.10 or later
            echo -e "${YELLOW}Installing Python 3.10...${NC}"
            sudo apt-get install -y python3.10 python3.10-venv python3.10-dev python3-pip
            
            # Create symbolic link if needed
            if ! command -v python3 >/dev/null 2>&1; then
                echo -e "${YELLOW}Creating python3 symbolic link...${NC}"
                sudo ln -sf /usr/bin/python3.10 /usr/bin/python3
            fi
            
            echo -e "${GREEN}✅ Python 3 has been installed.${NC}"
            
            # Verify the installation
            python_version=$(python3 --version 2>&1)
            if [[ $python_version =~ "Python 3" ]]; then
                echo -e "${GREEN}✅ Python 3 is now installed: $python_version${NC}"
            else
                echo -e "${RED}❌ Failed to install Python 3. Please install manually.${NC}"
                exit 1
            fi
        else
            echo -e "${RED}❌ Sudo privileges required to install Python. Please run:${NC}"
            echo -e "sudo apt-get update"
            echo -e "sudo apt-get install -y software-properties-common"
            echo -e "sudo add-apt-repository -y ppa:deadsnakes/ppa"
            echo -e "sudo apt-get update"
            echo -e "sudo apt-get install -y python3.10 python3.10-venv python3.10-dev python3-pip"
            exit 1
        fi
    else
        echo -e "${RED}❌ Python 3 is required but not found and your OS is not Ubuntu/Debian.${NC}"
        echo -e "Please install Python 3.7 or higher manually and try again."
        exit 1
    fi
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
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Failed to create virtual environment.${NC}"
            echo -e "Please make sure python3-venv is installed."
            exit 1
        fi
        echo -e "${GREEN}✅ Virtual environment created.${NC}"
    else
        echo "Using existing virtual environment."
    fi
else
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to create virtual environment.${NC}"
        echo -e "Please make sure python3-venv is installed."
        exit 1
    fi
    echo -e "${GREEN}✅ Virtual environment created.${NC}"
fi

# Check if virtual environment was actually created
if [ ! -f "venv/bin/activate" ]; then
    echo -e "${RED}❌ Virtual environment activation script not found.${NC}"
    echo -e "The virtual environment was not created correctly."
    exit 1
fi

# Activate virtual environment
echo -e "\n${BOLD}Activating virtual environment...${NC}"
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to activate virtual environment.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Virtual environment activated.${NC}"

# Verify pip is available
if ! command -v pip >/dev/null 2>&1; then
    echo -e "${RED}❌ pip command not found after activating virtual environment.${NC}"
    echo -e "This suggests the virtual environment was not properly created or activated."
    echo -e "Please try recreating the virtual environment or installing pip manually."
    exit 1
fi

# Install dependencies
echo -e "\n${BOLD}Installing dependencies...${NC}"
pip install --upgrade pip
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to upgrade pip. Attempting to continue anyway...${NC}"
fi

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