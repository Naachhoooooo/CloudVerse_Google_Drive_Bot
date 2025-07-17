from pathlib import Path
from dotenv import load_dotenv
import os
from cryptography.fernet import Fernet

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
TeamCloudverse_TOPIC_ID = os.getenv("TeamCloudverse_TOPIC_ID")  # Renamed from AdminControl_TOPIC_ID
MessageDev_TOPIC_ID = os.getenv("MessageDev_TOPIC_ID")
SUPER_ADMIN_ID = os.getenv("SUPER_ADMIN_ID")  # Super admin Telegram ID
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY is not set in config.")

CIPHER = Fernet(ENCRYPTION_KEY.encode())

SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials" / "credentials.json"
DB_PATH = Path(__file__).parent.parent / "Cloudverse.db"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

TELETHON_API_ID = os.getenv("API_ID")
TELETHON_API_HASH = os.getenv("API_HASH")
