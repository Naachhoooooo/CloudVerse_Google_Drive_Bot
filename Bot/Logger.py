# Bot/Logger.py
"""
Centralized backend logging and real-time stats for CloudVerse Bot.
Logs all backend-relevant events (uploads, bandwidth, access/role changes, dev messages, errors, etc.).
No logging for user menu navigation or user-facing notifications.
"""
import logging
import json
from datetime import datetime, timedelta
from threading import Lock
import sqlite3
from Bot.config import DB_PATH, LOG_LEVEL
import threading
import time
import psutil
import os
from Bot.database import get_num_active_users, get_bandwidth_today, get_uploads_today, get_total_users

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}

logger = logging.getLogger("CloudVerseLogger")
logger.setLevel(LOG_LEVEL_MAP.get(LOG_LEVEL.upper(), logging.INFO))
handler = logging.FileHandler("cloudverse.log")
formatter = logging.Formatter('%(asctime)s %(levelname)s %(module)s %(message)s')
handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(handler)

log_lock = Lock()

# --- Uptime Tracking ---
PROCESS_START_TIME = time.time()

# --- Last Upload Tracking ---
LAST_UPLOAD = {'filename': '', 'timestamp': ''}

# --- Queue Length Placeholder ---
def get_queue_length():
    # Replace with actual queue length if you have a job/task queue
    return 0

# --- Current Bandwidth Usage Placeholder ---
def get_current_bandwidth_usage():
    # Replace with actual bandwidth calculation if you track it
    return "N/A"

# --- System Stats ---
def get_cpu_usage():
    return psutil.cpu_percent(interval=0.1)

def get_memory_usage():
    mem = psutil.virtual_memory()
    return mem.percent, mem.used, mem.total

def get_uptime():
    seconds = int(time.time() - PROCESS_START_TIME)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"

def get_db_size():
    try:
        db_path = str(DB_PATH)
        if os.path.exists(db_path):
            size = os.path.getsize(db_path)
            for unit in ['B','KB','MB','GB','TB']:
                if size < 1024.0:
                    return f"{size:.2f} {unit}"
                size /= 1024.0
        return "0 B"
    except Exception:
        return "N/A"

def get_last_upload():
    if LAST_UPLOAD['filename'] and LAST_UPLOAD['timestamp']:
        return f"{LAST_UPLOAD['filename']} at {LAST_UPLOAD['timestamp']}"
    return "N/A"

# --- Real-Time Stats Functions (existing) ---
def get_num_active_users_proxy(minutes=10):
    return get_num_active_users(minutes)

def get_bandwidth_today_proxy():
    return get_bandwidth_today() / (1024 * 1024)  # Convert bytes to MB

def get_uploads_today_proxy():
    return get_uploads_today()

def get_total_users_proxy():
    return get_total_users()

# --- Update last upload on log_upload ---
def log_upload(user_id, file_name, file_size, bandwidth_used):
    with log_lock:
        logger.info(json.dumps({
            "event": "upload",
            "user_id": user_id,
            "file_name": file_name,
            "file_size": file_size,
            "bandwidth_used": bandwidth_used,
            "timestamp": datetime.now().isoformat()
        }))
        LAST_UPLOAD['filename'] = file_name
        LAST_UPLOAD['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def log_bandwidth(user_id, bandwidth_used, context=""):
    with log_lock:
        logger.info(json.dumps({
            "event": "bandwidth",
            "user_id": user_id,
            "bandwidth_used": bandwidth_used,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }))

def log_access_change(user_id, action, by_admin):
    with log_lock:
        logger.info(json.dumps({
            "event": "access_change",
            "user_id": user_id,
            "action": action,
            "by_admin": by_admin,
            "timestamp": datetime.now().isoformat()
        }))

def log_role_change(user_id, old_role, new_role, by_admin):
    with log_lock:
        logger.info(json.dumps({
            "event": "role_change",
            "user_id": user_id,
            "old_role": old_role,
            "new_role": new_role,
            "by_admin": by_admin,
            "timestamp": datetime.now().isoformat()
        }))

def log_developer_message(user_id, message):
    with log_lock:
        logger.info(json.dumps({
            "event": "dev_message",
            "user_id": user_id,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }))

def log_developer_reply(user_id, message):
    with log_lock:
        logger.info(json.dumps({
            "event": "dev_reply",
            "user_id": user_id,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }))

def log_error(error, context=""):
    with log_lock:
        logger.error(json.dumps({
            "event": "error",
            "error": str(error),
            "context": context,
            "timestamp": datetime.now().isoformat()
        }))

def get_logger():
    return logger 