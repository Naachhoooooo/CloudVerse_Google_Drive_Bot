"""
CloudVerse Google Drive Bot - Configuration Module

This module handles all configuration settings for the CloudVerse Bot,
including environment variable loading, security settings, and path
configurations. It centralizes all configurable parameters to ensure
consistent behavior across the application.

Configuration Categories:
1. Telegram Bot Settings - Bot token and chat configurations
2. Google Drive API Settings - OAuth scopes and credentials
3. Security Settings - Encryption keys and access control
4. Database Settings - Database paths and connection parameters
5. Logging Settings - Log levels and output configurations
6. File System Paths - Application file and directory locations

Security Features:
- Environment variable validation
- Encryption key management with Fernet
- Secure credential storage paths
- Access control configuration

Environment Variables Required:
- BOT_TOKEN: Telegram bot token from BotFather
- GROUP_CHAT_ID: Admin notification group chat ID
- TeamCloudverse_TOPIC_ID: Topic ID for team notifications
- MessageDev_TOPIC_ID: Topic ID for developer messages
- SUPER_ADMIN_ID: Telegram ID of the super administrator
- ENCRYPTION_KEY: Base64 encoded Fernet encryption key
- API_ID: Telegram API ID for Telethon (optional)
- API_HASH: Telegram API hash for Telethon (optional)
- LOG_LEVEL: Logging level (default: INFO)

Author: CloudVerse Team
License: Open Source
"""

from pathlib import Path
from dotenv import load_dotenv
import os
from cryptography.fernet import Fernet

# ============================================================================
# ENVIRONMENT VARIABLE LOADING
# ============================================================================

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# TELEGRAM BOT CONFIGURATION
# ============================================================================

# Core bot authentication and communication settings
BOT_TOKEN = os.getenv("BOT_TOKEN")                          # Telegram bot token from BotFather
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")                  # Admin notification group chat ID
TeamCloudverse_TOPIC_ID = os.getenv("TeamCloudverse_TOPIC_ID")  # Topic for team notifications
MessageDev_TOPIC_ID = os.getenv("MessageDev_TOPIC_ID")      # Topic for developer messages
SUPER_ADMIN_ID = os.getenv("SUPER_ADMIN_ID")                # Super administrator Telegram ID

# ============================================================================
# SECURITY AND ENCRYPTION CONFIGURATION
# ============================================================================

# Encryption key for securing sensitive data (Google Drive credentials)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY is not set in config. Please set this environment variable.")

# Initialize Fernet cipher for symmetric encryption
CIPHER = Fernet(ENCRYPTION_KEY.encode())

# ============================================================================
# GOOGLE DRIVE API CONFIGURATION
# ============================================================================

# OAuth 2.0 scopes for Google Drive access
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Path to Google OAuth credentials file
CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials" / "credentials.json"

# ============================================================================
# DATABASE AND FILE SYSTEM CONFIGURATION
# ============================================================================

# SQLite database file path
DB_PATH = Path(__file__).parent.parent / "Cloudverse.db"

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # Default to INFO level logging

# ============================================================================
# TELETHON CONFIGURATION (Optional)
# ============================================================================

# Telethon API credentials for advanced Telegram features (if needed)
TELETHON_API_ID = os.getenv("API_ID")       # Telegram API ID
TELETHON_API_HASH = os.getenv("API_HASH")   # Telegram API hash
