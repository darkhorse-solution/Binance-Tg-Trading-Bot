#!/bin/bash
# Installation script for the Trading Bot

# Text formatting
BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

echo -e "${BOLD}🤖 Trading Bot Setup${NC}"
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
        echo -e "${RED}❌ .env.sample file not found.${NC}"
        echo -e "Please create .env file manually."
    fi
fi

echo -e "\n${GREEN}${BOLD}Installation complete!${NC}"
echo -e "\nTo start the bot, run:"
echo -e "${BOLD}source venv/bin/activate${NC}"
echo -e "${BOLD}python main.py${NC}"
echo -e "\nEnsure you have configured your .env file with correct credentials before starting."