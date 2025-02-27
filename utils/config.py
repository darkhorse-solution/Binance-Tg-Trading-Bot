import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    SOURCE_CHANNEL_ID = os.getenv("SOURCE_CHANNEL_ID")
    TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID")
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    SESSION_STRING = os.getenv("SESSION_STRING", "")