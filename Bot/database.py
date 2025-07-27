"""
CloudVerse Google Drive Bot - Database Management Module

This module handles all database operations for the CloudVerse Google Drive Bot,
providing a comprehensive data layer for user management, access control, and
bot functionality. It uses SQLite as the primary database with optimized
schemas and indexing for performance.

Key Features:
- User access control and permission management
- Google Drive credentials storage with encryption
- Session and authentication data management
- Comprehensive logging and error handling
- Database migration and initialization
- Performance optimization with proper indexing

Database Schema:
- administrators: Admin and super admin user management
- whitelisted_users: Users with bot access (with optional expiration)
- blacklisted_users: Restricted users (temporary or permanent)
- pending_users: Users awaiting access approval
- cloudverse_users: General user information and profiles
- user_credentials: Encrypted Google Drive authentication data
- user_sessions: Active user sessions and state management

Security Features:
- Encrypted credential storage using CIPHER
- SQL injection prevention with parameterized queries
- Transaction management for data consistency
- Comprehensive audit logging for security monitoring

Author: CloudVerse Team
License: Open Source
"""

import sqlite3
from Bot.config import DB_PATH, SUPER_ADMIN_ID, CIPHER
from datetime import datetime, timedelta
import json
from .Logger import database_logger as logger

# ============================================================================
# DATABASE INITIALIZATION AND SCHEMA MANAGEMENT
# ============================================================================

def init_db():
    """
    Initialize the SQLite database with all required tables and indexes.
    
    This function creates the complete database schema for the CloudVerse Bot,
    including all tables, indexes, and constraints needed for proper operation.
    It's designed to be idempotent - safe to run multiple times without issues.
    
    Database Tables Created:
        1. administrators: Admin and super admin management
        2. whitelisted_users: Users with bot access permissions
        3. blacklisted_users: Restricted/banned users
        4. pending_users: Users awaiting access approval
        5. cloudverse_users: General user profiles and information
        6. user_credentials: Encrypted Google Drive authentication data
        7. user_sessions: Active user sessions and state
        
    Performance Optimizations:
        - Strategic indexing on frequently queried columns
        - Proper data types for efficient storage
        - Foreign key relationships where appropriate
        
    Error Handling:
        - Comprehensive logging of initialization process
        - Transaction rollback on failures
        - Detailed error reporting for troubleshooting
        
    Raises:
        sqlite3.Error: On database connection or schema creation failures
        Exception: On unexpected errors during initialization
    """
    logger.info("Starting database initialization")
    try:
        logger.debug(f"Connecting to database at: {DB_PATH}")
        
        # Use connection context manager for automatic transaction handling
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:  # This ensures transaction is committed or rolled back
                cursor = conn.cursor()
                
                # ================================================================
                # ADMINISTRATORS TABLE - Admin and Super Admin Management
                # ================================================================
                logger.debug("Creating administrators table")
                cursor.execute('''CREATE TABLE IF NOT EXISTS administrators (
                    telegram_id TEXT PRIMARY KEY,      -- Telegram user ID (unique identifier)
                    username TEXT UNIQUE,              -- Telegram username (for easy identification)
                    name TEXT,                         -- Full name of the administrator
                    is_super_admin INTEGER DEFAULT 0,  -- 1 for super admin, 0 for regular admin
                    promoted_by TEXT,                  -- ID of admin who promoted this user
                    promoted_at TIMESTAMP,             -- When the promotion occurred
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- Last modification time
                )''')
                
                # Create indexes for efficient querying
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_administrators_username ON administrators(username)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_administrators_is_super_admin ON administrators(is_super_admin)")
                
                # ================================================================
                # WHITELISTED USERS TABLE - Users with Bot Access
                # ================================================================
                logger.debug("Creating whitelisted_users table")
                cursor.execute('''CREATE TABLE IF NOT EXISTS whitelisted_users (
                    telegram_id TEXT PRIMARY KEY,      -- Telegram user ID
                    username TEXT UNIQUE,              -- Telegram username
                    name TEXT,                         -- Full name of the user
                    approved_by TEXT,                  -- ID of admin who approved access
                    approved_at TIMESTAMP,             -- When access was granted
                    expiration_time TIMESTAMP,         -- When access expires (NULL for permanent)
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- Last modification time
                )''')
                
                # Create indexes for efficient access control checks
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_whitelisted_users_username ON whitelisted_users(username)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_whitelisted_users_expiration_time ON whitelisted_users(expiration_time)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_whitelisted_users_approved_by ON whitelisted_users(approved_by)")
                
                # ================================================================
                # BLACKLISTED USERS TABLE - Restricted/Banned Users
                # ================================================================
                logger.debug("Creating blacklisted_users table")
                cursor.execute('''CREATE TABLE IF NOT EXISTS blacklisted_users (
                    telegram_id TEXT PRIMARY KEY,      -- Telegram user ID
                    username TEXT UNIQUE,              -- Telegram username
                    name TEXT,                         -- Full name of the user
                    restriction_type TEXT,             -- 'temporary' or 'permanent'
                    restriction_period TIMESTAMP,      -- When restriction expires (for temporary)
                    restricted_at TIMESTAMP,           -- When restriction was applied
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- Last modification time
                )''')
                
                # Create indexes for restriction management
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklisted_users_username ON blacklisted_users(username)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklisted_users_restriction_type ON blacklisted_users(restriction_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklisted_users_restriction_period ON blacklisted_users(restriction_period)")
                # User Credentials table
                cursor.execute('''CREATE TABLE IF NOT EXISTS user_credentials (
                    telegram_id TEXT,
                    username TEXT,
                    name TEXT,
                    email_address_1 TEXT,
                    email_address_2 TEXT,
                    email_address_3 TEXT,
                    credential_1 TEXT,
                    credential_2 TEXT,
                    credential_3 TEXT,
                    primary_email_address TEXT,
                    default_upload_location TEXT DEFAULT 'root',
                    parallel_uploads INTEGER DEFAULT 1,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_credentials_telegram_id ON user_credentials(telegram_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_credentials_email_address_1 ON user_credentials(email_address_1)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_credentials_primary_email_address ON user_credentials(primary_email_address)")
                # Pending Users table
                cursor.execute('''CREATE TABLE IF NOT EXISTS pending_users (
                    telegram_id TEXT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    group_message_id INTEGER,
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_users_username ON pending_users(username)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_users_requested_at ON pending_users(requested_at)")
                # Broadcasts table
                cursor.execute('''CREATE TABLE IF NOT EXISTS broadcasts (
                    request_id TEXT PRIMARY KEY,
                    requester_telegram_id TEXT,
                    requester_username TEXT,
                    group_message_id INTEGER,
                    message_text TEXT,
                    media_type TEXT,
                    media_file_id TEXT,
                    approval_status TEXT,
                    status TEXT,
                    approved_by TEXT, -- can be JSON list or single value
                    approved_at TIMESTAMP,
                    target_count INTEGER,
                    last_updated TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_requester_telegram_id ON broadcasts(requester_telegram_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_requester_username ON broadcasts(requester_username)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_status ON broadcasts(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_approved_by ON broadcasts(approved_by)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_last_updated ON broadcasts(last_updated)")
                # Uploads table
                cursor.execute('''CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id TEXT,
                    username TEXT,
                    chat_id INTEGER,
                    message_id INTEGER,
                    file_name TEXT,
                    file_type TEXT,
                    file_size INTEGER,
                    status TEXT,
                    error_message TEXT,
                    upload_method TEXT,
                    average_speed REAL,
                    upload_source TEXT,
                    upload_duration REAL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_telegram_id ON uploads(telegram_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_username ON uploads(username)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_uploaded_at ON uploads(uploaded_at)")
                # CloudVerse History table
                cursor.execute('''CREATE TABLE IF NOT EXISTS cloudverse_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id TEXT,
                    username TEXT,
                    user_role TEXT,
                    action_taken TEXT,
                    status TEXT,
                    handled_by TEXT,
                    related_message_id TEXT,
                    event_details TEXT,
                    notes TEXT,
                    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloudverse_history_telegram_id ON cloudverse_history(telegram_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloudverse_history_username ON cloudverse_history(username)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloudverse_history_action_taken ON cloudverse_history(action_taken)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloudverse_history_user_role ON cloudverse_history(user_role)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloudverse_history_event_time ON cloudverse_history(event_time)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloudverse_history_status ON cloudverse_history(status)")
                # Developer Messages table
                cursor.execute('''CREATE TABLE IF NOT EXISTS dev_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_telegram_id INTEGER NOT NULL,
                    username TEXT,
                    user_name TEXT,
                    sender_role TEXT NOT NULL, -- 'user' or 'developer'
                    message TEXT NOT NULL,
                    telegram_message_id INTEGER,
                    reply_to_id INTEGER,
                    delivery_status INTEGER DEFAULT 0,
                    delivered_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_dev_messages_user_telegram_id ON dev_messages(user_telegram_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_dev_messages_delivery_status ON dev_messages(delivery_status)")
                # User Quota table
                cursor.execute('''CREATE TABLE IF NOT EXISTS user_quota (
                    telegram_id TEXT PRIMARY KEY,
                    username TEXT,
                    daily_upload_limit INTEGER DEFAULT 5,
                    current_date TEXT,
                    daily_uploads_used INTEGER DEFAULT 0,
                    last_reset_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_quota_telegram_id ON user_quota(telegram_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_quota_current_date ON user_quota(current_date)")
                
                logger.info("Database initialization completed successfully")
                logger.debug("All tables and indexes created/verified")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}", exc_info=True)
        raise

#Admin

def add_admin(telegram_id, username=None, name=None, promoted_by=None, is_super_admin=0):
    """Add a new administrator to the system"""
    logger.info(f"Adding admin: telegram_id={telegram_id}, username={username}, is_super_admin={is_super_admin}")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO administrators (telegram_id, username, name, is_super_admin, promoted_by, promoted_at, last_updated) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                       (str(telegram_id), username, name, is_super_admin, promoted_by))
                
                # Log admin action
                admin_type = "super_admin" if is_super_admin else "admin"
                action_details = f"Added {admin_type}: {username or telegram_id}"
                log_cloudverse_history_event(
                    telegram_id=str(telegram_id),
                    username=username,
                    user_role=admin_type,
                    action_taken="admin_promotion",
                    status="success",
                    handled_by=promoted_by,
                    event_details=action_details
                )
                logger.info(f"Successfully added admin: {username or telegram_id}")
    except Exception as e:
        logger.error(f"Failed to add admin {telegram_id}: {str(e)}", exc_info=True)
        raise

def get_admins():
    """Retrieve all administrators from the database"""
    logger.debug("Retrieving all administrators")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM administrators")
                admins = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        logger.debug(f"Retrieved {len(admins)} administrators")
        return admins
    except Exception as e:
        logger.error(f"Failed to retrieve administrators: {str(e)}", exc_info=True)
        raise

def get_super_admins():
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM administrators WHERE is_super_admin = 1")
                super_admins = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        return super_admins
    except Exception as e:
        raise

def is_admin(telegram_id):
    """Check if user is an administrator"""
    logger.debug(f"Checking admin status for user {telegram_id}")
    try:
        if str(telegram_id) == str(SUPER_ADMIN_ID):
            logger.debug(f"User {telegram_id} is super admin")
            return True
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM administrators WHERE telegram_id = ?", (str(telegram_id),))
                result = cursor.fetchone()
        is_admin_result = bool(result)
        logger.debug(f"Admin check for user {telegram_id}: {is_admin_result}")
        return is_admin_result
    except Exception as e:
        logger.error(f"Failed to check admin status for user {telegram_id}: {str(e)}", exc_info=True)
        raise

def is_super_admin(telegram_id):
    try:
        if not SUPER_ADMIN_ID:
            return False
        return str(telegram_id) == str(SUPER_ADMIN_ID)
    except Exception as e:
        raise

def remove_admin(telegram_id, removed_by=None):
    try:
        if is_super_admin(telegram_id):
            raise ValueError("Cannot remove super admin (developer)")
        
        # Get admin info before deletion for logging
        admin_info = None
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, name, is_super_admin FROM administrators WHERE telegram_id = ?", (str(telegram_id),))
            admin_info = cursor.fetchone()
        
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM administrators WHERE telegram_id = ?", (str(telegram_id),))
                
                # Log admin action
                if admin_info:
                    username, name, was_super_admin = admin_info
                    admin_type = "super_admin" if was_super_admin else "admin"
                    action_details = f"Removed {admin_type}: {username or name or telegram_id}"
                    log_cloudverse_history_event(
                        telegram_id=str(telegram_id),
                        username=username,
                        user_role=admin_type,
                        action_taken="admin_demotion",
                        status="success",
                        handled_by=removed_by,
                        event_details=action_details
                    )
    except Exception as e:
        raise

#Whitelisted

def add_whitelist(telegram_id, username=None, name=None, approved_by=None, approved_at=None, expiration_time=None):
    """Add user to whitelist with optional expiration"""
    logger.info(f"Adding user to whitelist: {telegram_id}, username: {username}, approved_by: {approved_by}")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO whitelisted_users (telegram_id, username, name, approved_by, approved_at, expiration_time, last_updated) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                       (str(telegram_id), username, name, approved_by, approved_at, expiration_time))
                
                # Log admin action
                action_details = f"Added to whitelist: {username or name or telegram_id}"
                if expiration_time:
                    action_details += f" (expires: {expiration_time})"
                    logger.info(f"User {telegram_id} whitelisted with expiration: {expiration_time}")
                else:
                    logger.info(f"User {telegram_id} whitelisted permanently")
                    
                log_cloudverse_history_event(
                    telegram_id=str(telegram_id),
                    username=username,
                    user_role="whitelisted",
                    action_taken="whitelist_add",
                    status="success",
                    handled_by=approved_by,
                    event_details=action_details
                )
                logger.info(f"Successfully added user {telegram_id} to whitelist")
    except Exception as e:
        logger.error(f"Failed to add user {telegram_id} to whitelist: {str(e)}", exc_info=True)
        raise

def get_whitelist():
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM whitelisted_users")
                rows = cursor.fetchall()
        result = [dict(zip([column[0] for column in cursor.description], row)) for row in rows]
        return result
    except Exception as e:
        raise

def get_whitelisted_users():
    try:
        import sqlite3
        from Bot.config import DB_PATH
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT telegram_id, username, name FROM whitelisted_users")
                rows = cursor.fetchall()
                return [
                    {'telegram_id': row[0], 'username': row[1], 'name': row[2]}
                    for row in rows
                ]
    except Exception as e:
        return []

def get_whitelisted_users_except_admins():
    try:
        whitelisted_users = get_whitelisted_users()
        admin_users = get_admins()
        admin_ids = {admin['telegram_id'] for admin in admin_users}
        return [user for user in whitelisted_users if user['telegram_id'] not in admin_ids]
    except Exception as e:
        # Optionally log error
        return []

def is_whitelisted(telegram_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT expiration_time FROM whitelisted_users WHERE telegram_id = ?", (str(telegram_id),))
                row = cursor.fetchone()
        if row:
            expiration_time = row[0]
            if expiration_time is None or datetime.fromisoformat(expiration_time) > datetime.now():
                return True
        return False
    except Exception as e:
        raise

def set_whitelist_expiration(telegram_id, expiration_time):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE whitelisted_users SET expiration_time = ?, last_updated = CURRENT_TIMESTAMP WHERE telegram_id = ?", (expiration_time, str(telegram_id)))
    except Exception as e:
        raise

def get_whitelist_expiring_soon(minutes=30):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                now = datetime.now()
                soon = now + timedelta(minutes=minutes)
                cursor.execute("SELECT telegram_id, username, name, expiration_time FROM whitelisted_users WHERE expiration_time IS NOT NULL")
                users = []
                for row in cursor.fetchall():
                    exp_time = row[3]
                    if exp_time:
                        try:
                            exp_dt = datetime.fromisoformat(exp_time)
                            if now < exp_dt <= soon:
                                users.append({
                                    'telegram_id': row[0],
                                    'username': row[1],
                                    'name': row[2],
                                    'expiration_time': exp_time
                                })
                        except Exception:
                            continue
                return users
    except Exception as e:
        raise

def remove_whitelist(telegram_id, removed_by=None):
    try:
        # Get user info before deletion for logging
        user_info = None
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, name FROM whitelisted_users WHERE telegram_id = ?", (str(telegram_id),))
            user_info = cursor.fetchone()
        
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM whitelisted_users WHERE telegram_id = ?", (str(telegram_id),))
                
                # Log admin action
                if user_info:
                    username, name = user_info
                    action_details = f"Removed from whitelist: {username or name or telegram_id}"
                    log_cloudverse_history_event(
                        telegram_id=str(telegram_id),
                        username=username,
                        user_role="whitelisted",
                        action_taken="whitelist_remove",
                        status="success",
                        handled_by=removed_by,
                        event_details=action_details
                    )
    except Exception as e:
        raise

#Blacklisted

def add_blacklisted_user(telegram_id, username, name, restriction_type, restriction_period=None, restricted_at=None, restricted_by=None):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute('''INSERT OR REPLACE INTO blacklisted_users (telegram_id, username, name, restriction_type, restriction_period, restricted_at, last_updated) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                       (str(telegram_id), username, name, restriction_type, restriction_period, restricted_at))
                
                # Log admin action
                action_details = f"Added to blacklist: {username or name or telegram_id} ({restriction_type})"
                if restriction_period:
                    action_details += f" until {restriction_period}"
                log_cloudverse_history_event(
                    telegram_id=str(telegram_id),
                    username=username,
                    user_role="blacklisted",
                    action_taken="blacklist_add",
                    status="success",
                    handled_by=restricted_by,
                    event_details=action_details
                )
    except Exception as e:
        raise

def get_blacklisted_users():
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM blacklisted_users ORDER BY last_updated DESC")
                rows = cursor.fetchall()
        result = [dict(zip([column[0] for column in cursor.description], row)) for row in rows]
        return result
    except Exception as e:
        raise

def edit_blacklisted_user(telegram_id, restriction_type, restriction_end=None):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute('''UPDATE blacklisted_users SET restriction_type = ?, restriction_period = ?, last_updated = CURRENT_TIMESTAMP WHERE telegram_id = ?''',
                       (restriction_type, restriction_end, str(telegram_id)))
    except Exception as e:
        raise

def remove_blacklisted_user(telegram_id, removed_by=None):
    try:
        # Get user info before deletion for logging
        user_info = None
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, name, restriction_type FROM blacklisted_users WHERE telegram_id = ?", (str(telegram_id),))
            user_info = cursor.fetchone()
        
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM blacklisted_users WHERE telegram_id = ?", (str(telegram_id),))
                
                # Log admin action
                if user_info:
                    username, name, restriction_type = user_info
                    action_details = f"Removed from blacklist: {username or name or telegram_id} (was {restriction_type})"
                    log_cloudverse_history_event(
                        telegram_id=str(telegram_id),
                        username=username,
                        user_role="blacklisted",
                        action_taken="blacklist_remove",
                        status="success",
                        handled_by=removed_by,
                        event_details=action_details
                    )
    except Exception as e:
        raise

#Lifting Bans and Expiry Functions

def unban_expired_temporary_blacklist():
    unbanned_users = []
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                now = datetime.now()
                cursor.execute("SELECT telegram_id, restriction_period FROM blacklisted_users WHERE restriction_type = 'Temporary' AND restriction_period IS NOT NULL")
                for row in cursor.fetchall():
                    telegram_id, restriction_period = row
                    if restriction_period:
                        try:
                            end_dt = datetime.fromisoformat(restriction_period)
                            if end_dt < now:
                                cursor.execute("DELETE FROM blacklisted_users WHERE telegram_id = ?", (str(telegram_id),))
                                # logger.info(f"Automatically unbanned user {telegram_id} after temporary ban expired.")
                                unbanned_users.append(telegram_id)
                        except Exception:
                            pass
    except Exception as e:
        raise
    return unbanned_users

def mark_expired_users():
    newly_expired = []
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                now = datetime.now()
                cursor.execute("SELECT telegram_id, username, name, expiration_time FROM whitelisted_users WHERE expiration_time IS NOT NULL")
                for row in cursor.fetchall():
                    telegram_id, username, name, expiration_time = row
                    if expiration_time:
                        try:
                            exp_dt = datetime.fromisoformat(expiration_time)
                            if exp_dt < now:
                                # Split name into first and last name if possible
                                first_name, last_name = (name.split(' ', 1) + [""])[:2] if name else ("", "")
                                newly_expired.append({
                                    'telegram_id': telegram_id,
                                    'username': username,
                                    'first_name': first_name,
                                    'last_name': last_name
                                })
                                cursor.execute("UPDATE whitelisted_users SET role = 'expired', last_updated = CURRENT_TIMESTAMP WHERE telegram_id = ?", (str(telegram_id),))
                        except Exception:
                            pass
    except Exception as e:
        raise
    return newly_expired

#User Details Functions

def get_user_details_by_id(telegram_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                # Search all user tables for details
                cursor.execute("SELECT telegram_id, username, name FROM administrators WHERE telegram_id = ?", (str(telegram_id),))
                row = cursor.fetchone()
                if row:
                    return {"telegram_id": row[0], "username": row[1], "name": row[2]}
                cursor.execute("SELECT telegram_id, username, name FROM whitelisted_users WHERE telegram_id = ?", (str(telegram_id),))
                row = cursor.fetchone()
        if row:
            return {"telegram_id": row[0], "username": row[1], "name": row[2]}
        cursor.execute("SELECT telegram_id, username, first_name || ' ' || last_name FROM pending_users WHERE telegram_id = ?", (str(telegram_id),))
        row = cursor.fetchone()
        if row:
            return {"telegram_id": row[0], "username": row[1], "name": row[2]}
        return None
    except Exception as e:
        raise

def get_user_id_by_username(username):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                # Search all user tables for username
                cursor.execute("SELECT telegram_id FROM administrators WHERE username = ?", (username,))
                row = cursor.fetchone()
                if row:
                    return row[0]
                cursor.execute("SELECT telegram_id FROM whitelisted_users WHERE username = ?", (username,))
                row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("SELECT telegram_id FROM pending_users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
    except Exception as e:
        raise

def get_user_accounts_and_primary(telegram_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                for table in ["user_credentials"]:
                    cursor.execute(f"SELECT email_address_1, primary_email_address FROM {table} WHERE telegram_id = ?", (str(telegram_id),))
                    row = cursor.fetchone()
                    if row:
                        accounts = [email for email in row[:1] if email]
                        primary = row[1]
                        return (accounts, primary, table)
        return ([], None, None)
    except Exception as e:
        raise

def set_primary_account(telegram_id, email, table_name):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE {table_name} SET primary_email_address = ?, last_updated = CURRENT_TIMESTAMP WHERE telegram_id = ? AND email_address_1 = ?", (email, str(telegram_id), email))
                cursor.execute(f"UPDATE {table_name} SET primary_email_address = NULL, last_updated = CURRENT_TIMESTAMP WHERE telegram_id = ? AND email_address_1 != ?", (str(telegram_id), email))
    except Exception as e:
        raise

def get_user_default_folder_id(telegram_id, account_email=None):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                if account_email:
                    cursor.execute("SELECT default_upload_location FROM user_credentials WHERE telegram_id = ? AND email_address_1 = ?", (str(telegram_id), account_email))
                else:
                    cursor.execute("SELECT default_upload_location FROM user_credentials WHERE telegram_id = ?", (str(telegram_id),))
                row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        return 'root'
    except Exception as e:
        raise

def get_user_credentials(telegram_id):
    """Get user credentials and settings from database."""
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""SELECT default_upload_location, parallel_uploads, primary_email_address, 
                                 email_address_1, email_address_2, email_address_3 
                                 FROM user_credentials WHERE telegram_id = ?""", (str(telegram_id),))
                row = cursor.fetchone()
        if row:
            return {
                'default_folder_id': row[0] or 'root',
                'parallel_uploads': row[1] or 1,
                'primary_email_address': row[2],
                'email_address_1': row[3],
                'email_address_2': row[4],
                'email_address_3': row[5]
            }
        return None
    except Exception as e:
        raise

#Broadcast Functions

def create_broadcast_request(request_id, requester_telegram_id, requester_username, message_text, media_type=None, media_file_id=None, target_count=0, approval_status=None, status='pending', approved_by=None, approved_at=None, group_message_id=None, approvers=None):
    try:
        import json
        if approvers is None:
            approvers = []
        approvers_json = json.dumps(approvers)
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""INSERT INTO broadcasts
                         (request_id, requester_telegram_id, requester_username, message_text, media_type, media_file_id, approval_status, status, approved_by, approved_at, last_updated, target_count, group_message_id)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (request_id, str(requester_telegram_id), requester_username, message_text, media_type, media_file_id, approval_status, status, approved_by, approved_at, datetime.now().isoformat(), target_count, group_message_id))
    except Exception as e:
        raise

def get_broadcast_request(request_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT request_id, requester_telegram_id, requester_username, message_text, media_type, media_file_id, approval_status, status, approved_by, approved_at, last_updated, target_count, group_message_id FROM broadcasts WHERE request_id = ?", (request_id,))
                row = cursor.fetchone()
        if row:
            import json
            try:
                approvers = json.loads(row[12]) if row[12] else []
            except Exception:
                approvers = []
            return {
                'request_id': row[0],
                'requester_telegram_id': row[1],
                'requester_username': row[2],
                'message_text': row[3],
                'media_type': row[4],
                'media_file_id': row[5],
                'approval_status': row[6],
                'status': row[7],
                'approved_by': row[8],
                'approved_at': row[9],
                'last_updated': row[10],
                'target_count': row[11],
                'group_message_id': row[12],
                'approvers': approvers
            }
        return None
    except Exception as e:
        raise

def update_broadcast_status(request_id, status):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE broadcasts SET status = ? WHERE request_id = ?", (status, request_id))
    except Exception as e:
        raise

def store_broadcast_group_message(request_id, message_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE broadcasts SET group_message_id = ? WHERE request_id = ?", (message_id, request_id))
    except Exception as e:
        raise

def get_broadcast_group_message(request_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT group_message_id FROM broadcasts WHERE request_id = ?", (request_id,))
                row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        raise

def update_broadcast_approvers(request_id, approvers):
    try:
        import json
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                approvers_json = json.dumps(approvers)
                cursor.execute("UPDATE broadcasts SET approved_by = ?, last_updated = CURRENT_TIMESTAMP WHERE request_id = ?", (approvers_json, request_id))
    except Exception as e:
        raise

#Uploads Functions

def insert_upload(telegram_id, username, chat_id, message_id, file_name, file_type, file_size, status='success', error_message=None, upload_method=None, average_speed=None, upload_source=None, upload_duration=None, uploaded_at=None):
    with sqlite3.connect(DB_PATH) as conn:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO uploads (telegram_id, username, chat_id, message_id, file_name, file_type, file_size, status, error_message, upload_method, average_speed, upload_source, upload_duration, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (telegram_id, username, chat_id, message_id, file_name, file_type, file_size, status, error_message, upload_method, average_speed, upload_source, upload_duration, uploaded_at))
            upload_id = cursor.lastrowid
    return upload_id

def get_upload_by_file_id(file_id):
    with sqlite3.connect(DB_PATH) as conn:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT telegram_id, username, chat_id, message_id, file_id, file_name, file_type, file_size, status, error_message, upload_time
                FROM uploads WHERE file_id = ?
                ORDER BY upload_time DESC LIMIT 1
            ''', (file_id,))
            row = cursor.fetchone()
    if row:
        return {
            'telegram_id': row[0],
            'username': row[1],
            'chat_id': row[2],
            'message_id': row[3],
            'file_id': row[4],
            'file_name': row[5],
            'file_type': row[6],
            'file_size': row[7],
            'status': row[8],
            'error_message': row[9],
            'upload_time': row[10],
        }
    return None

def get_user_upload_stats(user_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*), MIN(upload_time), MAX(upload_time) FROM uploads WHERE telegram_id = ?", (user_id,))
                stats = cursor.fetchone()
        return stats if stats else (0, None, None)
    except Exception as e:
        raise

def get_user_monthly_bandwidth(user_id, year_month):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(file_size) FROM uploads WHERE telegram_id = ? AND strftime('%Y-%m', upload_time) = ?", (user_id, year_month))
                total = cursor.fetchone()[0] or 0
        return total
    except Exception as e:
        raise

def get_bandwidth_today():
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(file_size) FROM uploads WHERE DATE(upload_time) = ?", (today,))
                total = cursor.fetchone()[0] or 0
        return total
    except Exception as e:
        raise

def get_uploads_today():
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM uploads WHERE DATE(upload_time) = ?", (today,))
                count = cursor.fetchone()[0]
        return count
    except Exception as e:
        raise

def get_user_top_file_types(user_id, limit=5):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT file_type, COUNT(*) as cnt
                    FROM uploads
                    WHERE telegram_id = ?
                    GROUP BY file_type
                    ORDER BY cnt DESC
                    LIMIT ?
                """, (user_id, limit))
                result = cursor.fetchall()
        return result
    except Exception as e:
        raise

def get_user_upload_activity_by_hour(user_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT strftime('%H', upload_time) as hour, COUNT(*)
                    FROM uploads
                    WHERE telegram_id = ?
                    GROUP BY hour
                    ORDER BY hour
                """, (user_id,))
                result = cursor.fetchall()
        return result
    except Exception as e:
        raise

def get_user_total_bandwidth(user_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(file_size) FROM uploads WHERE telegram_id = ?", (user_id,))
                total = cursor.fetchone()[0] or 0
        return total
    except Exception as e:
        raise

def get_user_uploads_per_day(user_id, days=30):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT DATE(upload_time), COUNT(*)
                    FROM uploads
                    WHERE telegram_id = ? AND upload_time >= DATE('now', ?)
                    GROUP BY DATE(upload_time)
                    ORDER BY DATE(upload_time)
                    """,
                    (user_id, f'-{days} days')
                )
                result = cursor.fetchall()
        return result
    except Exception as e:
        raise

#Team Cloudverse Functions

def log_cloudverse_history_event(telegram_id, action_taken, status=None, handled_by=None, related_message_id=None, event_details=None, notes=None, username=None, user_role=None):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO cloudverse_history (telegram_id, username, user_role, action_taken, status, handled_by, related_message_id, event_details, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (telegram_id, username, user_role, action_taken, status, handled_by, related_message_id, event_details, notes))
    except Exception as e:
        raise

def get_cloudverse_history_events(telegram_id=None, action_taken=None, status=None, user_role=None):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                query = "SELECT id, telegram_id, username, user_role, action_taken, status, handled_by, related_message_id, event_details, notes, event_time FROM cloudverse_history WHERE 1=1"
                params = []
                if telegram_id:
                    query += " AND telegram_id = ?"
                    params.append(telegram_id)
                if action_taken:
                    query += " AND action_taken = ?"
                    params.append(action_taken)
                if status:
                    query += " AND status = ?"
                    params.append(status)
                if user_role:
                    query += " AND user_role = ?"
                    params.append(user_role)
                cursor.execute(query, params)
                rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "telegram_id": r[1],
                "username": r[2],
                "user_role": r[3],
                "action_taken": r[4],
                "status": r[5],
                "handled_by": r[6],
                "related_message_id": r[7],
                "event_details": r[8],
                "notes": r[9],
                "event_time": r[10],
            } for r in rows
        ]
    except Exception as e:
        raise

#Devloper Messages Functions

def insert_dev_message(user_telegram_id, username, user_name, sender_role, message, telegram_message_id=None, reply_to_id=None, delivery_status=0):
    with sqlite3.connect(DB_PATH) as conn:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO dev_messages (user_telegram_id, username, user_name, sender_role, message, telegram_message_id, reply_to_id, delivery_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_telegram_id, username, user_name, sender_role, message, telegram_message_id, reply_to_id, delivery_status))
            msg_id = cursor.lastrowid
    return msg_id

def fetch_dev_messages(user_telegram_id, limit=20):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_telegram_id, username, user_name, sender_role, message, telegram_message_id, reply_to_id, delivery_status, delivered_at
            FROM dev_messages
            WHERE user_telegram_id = ?
            ORDER BY delivered_at DESC
            LIMIT ?
        ''', (user_telegram_id, limit))
        rows = cursor.fetchall()
    return [
        {
            'id': row[0],
            'user_telegram_id': row[1],
            'username': row[2],
            'user_name': row[3],
            'sender_role': row[4],
            'message': row[5],
            'telegram_message_id': row[6],
            'reply_to_id': row[7],
            'delivery_status': row[8],
            'delivered_at': row[9],
        } for row in rows
    ]

def mark_dev_message_delivered(msg_id):
    with sqlite3.connect(DB_PATH) as conn:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE dev_messages SET delivery_status = 1 WHERE id = ?
            ''', (msg_id,))

def fetch_dev_message_notified(user_telegram_id):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT 1 FROM dev_messages WHERE user_telegram_id = ? AND sender_role = 'system' AND message = ? LIMIT 1''', (user_telegram_id, 'notified'))
            result = cursor.fetchone()
        return bool(result)
    except Exception as e:
        raise

def remove_pending_user(telegram_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM pending_users WHERE telegram_id = ?", (str(telegram_id),))
    except Exception as e:
        raise

#Analytics/Utility Functions

def get_all_users_for_analytics():
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT telegram_id, username, name FROM administrators
                    UNION
                    SELECT telegram_id, username, name FROM whitelisted_users
                    UNION
                    SELECT telegram_id, username, name FROM pending_users
                """)
                users = cursor.fetchall()
                return users
    except Exception as e:
        raise

def get_total_users():
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(DISTINCT telegram_id) FROM (SELECT telegram_id FROM administrators UNION SELECT telegram_id FROM whitelisted_users UNION SELECT telegram_id FROM pending_users)")
                count = cursor.fetchone()[0]
        return count
    except Exception as e:
        raise

def get_analytics_data():
    try:
        import sqlite3
        from .config import DB_PATH
        from datetime import datetime, timedelta
        data = {}
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            # Whitelisted users
            cursor.execute("SELECT COUNT(*) FROM whitelisted_users")
            data['whitelisted_count'] = cursor.fetchone()[0]
            # Pending users
            cursor.execute("SELECT COUNT(*) FROM pending_users")
            data['pending_count'] = cursor.fetchone()[0]
            # Admin users
            cursor.execute("SELECT COUNT(*) FROM administrators")
            data['admin_count'] = cursor.fetchone()[0]
            # Total uploads
            cursor.execute("SELECT COUNT(*) FROM uploads")
            data['total_uploads'] = cursor.fetchone()[0]
            # Recent uploads (last 7 days)
            cursor.execute("SELECT COUNT(*) FROM uploads WHERE upload_time >= DATE('now', '-7 days')")
            data['recent_uploads'] = cursor.fetchone()[0]
            # Total broadcasts
            cursor.execute("SELECT COUNT(*) FROM broadcasts")
            data['total_broadcasts'] = cursor.fetchone()[0]
            # Approved broadcasts
            cursor.execute("SELECT COUNT(*) FROM broadcasts WHERE approval_status = 'approved'")
            data['approved_broadcasts'] = cursor.fetchone()[0]
            # Daily uploads (last 30 days)
            cursor.execute("SELECT DATE(upload_time), COUNT(*) FROM uploads WHERE upload_time >= DATE('now', '-30 days') GROUP BY DATE(upload_time)")
            data['daily_uploads'] = cursor.fetchall()
            # Bandwidth usage (last 30 days)
            cursor.execute("SELECT DATE(upload_time), SUM(file_size) FROM uploads WHERE upload_time >= DATE('now', '-30 days') GROUP BY DATE(upload_time)")
            data['bandwidth_usage'] = [(row[0], row[1] or 0) for row in cursor.fetchall()]
            # File type distribution (last 30 days)
            cursor.execute("SELECT file_type, COUNT(*) FROM uploads WHERE upload_time >= DATE('now', '-30 days') GROUP BY file_type")
            data['file_types'] = cursor.fetchall()
            # Activity by hour (last 30 days)
            cursor.execute("SELECT strftime('%H', upload_time), COUNT(*) FROM uploads WHERE upload_time >= DATE('now', '-30 days') GROUP BY strftime('%H', upload_time)")
            data['activity_by_hour'] = [(int(row[0]), row[1]) for row in cursor.fetchall()]
            # User growth (last 30 days)
            cursor.execute("SELECT DATE(created_at), COUNT(*) FROM administrators WHERE created_at >= DATE('now', '-30 days') GROUP BY DATE(created_at)")
            data['user_growth'] = cursor.fetchall()
            # Storage usage (current)
            cursor.execute("SELECT SUM(storage_quota) FROM administrators")
            data['storage_usage'] = cursor.fetchone()[0] or 0
        return data
    except Exception as e:
        print(f"Error in get_analytics_data: {e}")
        return {}

# Credential Management Functions

def set_drive_credentials(telegram_id, username, name, primary_email_address, email_address_1, email_address_2, email_address_3, credential_1, credential_2, credential_3, default_upload_location='root', parallel_uploads=1):
    with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO user_credentials (telegram_id, username, name, primary_email_address, email_address_1, email_address_2, email_address_3, credential_1, credential_2, credential_3, default_upload_location, parallel_uploads, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (telegram_id, username, name, primary_email_address, email_address_1, email_address_2, email_address_3, credential_1, credential_2, credential_3, default_upload_location, parallel_uploads))

def get_drive_credentials(telegram_id, account_email=None):
    if not account_email:
        return None
    with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email_address_1, email_address_2, email_address_3, credential_1, credential_2, credential_3 FROM user_credentials WHERE telegram_id = ?", (str(telegram_id),))
        row = cursor.fetchone()
    if not row:
        return None
    email_1, email_2, email_3, cred_1, cred_2, cred_3 = row
    cred_blob = None
    if account_email == email_1:
        cred_blob = cred_1
    elif account_email == email_2:
        cred_blob = cred_2
    elif account_email == email_3:
        cred_blob = cred_3
    if not cred_blob:
        return None
    try:
        decrypted = CIPHER.decrypt(cred_blob.encode()).decode()
        creds_dict = json.loads(decrypted)
        return creds_dict
    except Exception:
        return None

def remove_drive_credentials(telegram_id, account_email):
    with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email_address_1, email_address_2, email_address_3 FROM user_credentials WHERE telegram_id = ?", (str(telegram_id),))
        row = cursor.fetchone()
    if not row:
        return False
    email_1, email_2, email_3 = row
    field, email_field = None, None
    if account_email == email_1:
        field, email_field = 'credential_1', 'email_address_1'
    elif account_email == email_2:
        field, email_field = 'credential_2', 'email_address_2'
    elif account_email == email_3:
        field, email_field = 'credential_3', 'email_address_3'
    else:
        return False
    with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE user_credentials SET {field} = NULL, {email_field} = NULL, last_updated = CURRENT_TIMESTAMP WHERE telegram_id = ?", (str(telegram_id),))
        conn.commit()
    return True

def get_known_user_username(user_id):
    """
    Retrieve the username for a given user_id from the cloudverse_users table.
    Returns the username as a string, or None if not found.
    """
    import sqlite3
    from .config import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM administrators WHERE telegram_id = ?", (str(user_id),))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    return None

# Quota Management Functions

def get_user_quota_info(telegram_id, username=None):
    """Get user's current quota information"""
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Get or create user quota record
            cursor.execute("SELECT * FROM user_quota WHERE telegram_id = ?", (str(telegram_id),))
            quota_record = cursor.fetchone()
            
            if not quota_record:
                # Get username if not provided
                if not username:
                    # Try to get username from whitelisted_users table
                    cursor.execute("SELECT username FROM whitelisted_users WHERE telegram_id = ?", (str(telegram_id),))
                    user_record = cursor.fetchone()
                    username = user_record[0] if user_record else None
                
                # Create new quota record for user
                cursor.execute("""
                    INSERT INTO user_quota (telegram_id, username, daily_upload_limit, current_date, daily_uploads_used, last_reset_time)
                    VALUES (?, ?, 5, ?, 0, CURRENT_TIMESTAMP)
                """, (str(telegram_id), username, current_date))
                conn.commit()
                return {
                    'daily_limit': 5,
                    'daily_used': 0,
                    'current_date': current_date,
                    'last_reset_time': datetime.now().isoformat()
                }
            
            # Check if we need to reset daily quota (new day)
            stored_date = quota_record[3]  # current_date column
            if stored_date != current_date:
                # Reset daily quota for new day
                cursor.execute("""
                    UPDATE user_quota 
                    SET current_date = ?, daily_uploads_used = 0, last_reset_time = CURRENT_TIMESTAMP, last_updated = CURRENT_TIMESTAMP
                    WHERE telegram_id = ?
                """, (current_date, str(telegram_id)))
                conn.commit()
                return {
                    'daily_limit': quota_record[2],  # daily_upload_limit
                    'daily_used': 0,
                    'current_date': current_date,
                    'last_reset_time': datetime.now().isoformat()
                }
            
            return {
                'daily_limit': quota_record[2],  # daily_upload_limit
                'daily_used': quota_record[4],   # daily_uploads_used
                'current_date': quota_record[3], # current_date
                'last_reset_time': quota_record[5] # last_reset_time
            }
    except Exception as e:
        print(f"Error in get_user_quota_info: {e}")
        return {
            'daily_limit': 5,
            'daily_used': 0,
            'current_date': datetime.now().strftime("%Y-%m-%d"),
            'last_reset_time': datetime.now().isoformat()
        }

def increment_user_quota(telegram_id):
    """Increment user's daily upload count"""
    try:
        # Don't increment quota for admins (both super admins and regular admins)
        if is_admin(telegram_id):
            return True
        
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Get current quota info
            quota_info = get_user_quota_info(telegram_id)
            
            # Increment the daily uploads used
            cursor.execute("""
                UPDATE user_quota 
                SET daily_uploads_used = daily_uploads_used + 1, last_updated = CURRENT_TIMESTAMP
                WHERE telegram_id = ? AND current_date = ?
            """, (str(telegram_id), current_date))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error in increment_user_quota: {e}")
        return False

def check_user_quota_limit(telegram_id):
    """Check if user has exceeded their daily quota limit"""
    try:
        # Admins have unlimited quota
        if is_admin(telegram_id):
            return True
        
        quota_info = get_user_quota_info(telegram_id)
        # If daily_limit is 0, it means unlimited
        if quota_info['daily_limit'] == 0:
            return True
        
        return quota_info['daily_used'] < quota_info['daily_limit']
    except Exception as e:
        print(f"Error in check_user_quota_limit: {e}")
        return False

def set_user_quota_limit(telegram_id, daily_limit):
    """Set custom daily quota limit for a user"""
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Get username from whitelisted_users table
            cursor.execute("SELECT username FROM whitelisted_users WHERE telegram_id = ?", (str(telegram_id),))
            user_record = cursor.fetchone()
            username = user_record[0] if user_record else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO user_quota 
                (telegram_id, username, daily_upload_limit, current_date, daily_uploads_used, last_reset_time, last_updated)
                VALUES (?, ?, ?, ?, COALESCE((SELECT daily_uploads_used FROM user_quota WHERE telegram_id = ?), 0), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (str(telegram_id), username, daily_limit, current_date, str(telegram_id)))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error in set_user_quota_limit: {e}")
        return False

# ============================================================================
# PENDING USERS MANAGEMENT - Functions for handling access requests
# ============================================================================

def add_pending_user(telegram_id, username=None, first_name=None, last_name=None, group_message_id=None):
    """
    Add a user to the pending approval list.
    
    This function adds users who have requested access to the bot but haven't
    been approved yet. It's used when users first interact with the bot and
    need admin approval for access.
    
    Args:
        telegram_id (str): User's Telegram ID
        username (str): User's Telegram username (optional)
        first_name (str): User's first name (optional)
        last_name (str): User's last name (optional)
        group_message_id (int): Message ID in admin group for approval (optional)
        
    Returns:
        bool: True if user was added successfully, False otherwise
        
    Database Impact:
        - Inserts new record into pending_users table
        - Uses INSERT OR IGNORE to prevent duplicates
        - Logs the pending request for admin review
    """
    logger.info(f"Adding pending user: telegram_id={telegram_id}, username={username}")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO pending_users 
                    (telegram_id, username, first_name, last_name, group_message_id, requested_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (str(telegram_id), username, first_name, last_name, group_message_id))
                
                # Log the pending request
                log_cloudverse_history_event(
                    telegram_id=str(telegram_id),
                    username=username,
                    user_role="pending",
                    action_taken="access_request",
                    status="pending",
                    event_details=f"User requested access: {username or telegram_id}"
                )
                logger.info(f"Successfully added pending user: {username or telegram_id}")
                return True
    except Exception as e:
        logger.error(f"Failed to add pending user {telegram_id}: {str(e)}", exc_info=True)
        return False

def get_pending_users():
    """
    Retrieve all users awaiting access approval.
    
    This function returns a list of all users who have requested access
    but haven't been approved or rejected yet. Used by admins to review
    and process access requests.
    
    Returns:
        list: List of dictionaries containing pending user information
        
    Dictionary Structure:
        - telegram_id: User's Telegram ID
        - username: User's Telegram username
        - first_name: User's first name
        - last_name: User's last name
        - group_message_id: Associated admin group message ID
        - requested_at: When the request was made
    """
    logger.debug("Retrieving all pending users")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT telegram_id, username, first_name, last_name, group_message_id, requested_at
                FROM pending_users
                ORDER BY requested_at ASC
            """)
            rows = cursor.fetchall()
            
            pending_users = []
            for row in rows:
                pending_users.append({
                    'telegram_id': row[0],
                    'username': row[1],
                    'first_name': row[2],
                    'last_name': row[3],
                    'group_message_id': row[4],
                    'requested_at': row[5]
                })
            
            logger.debug(f"Retrieved {len(pending_users)} pending users")
            return pending_users
    except Exception as e:
        logger.error(f"Failed to retrieve pending users: {str(e)}", exc_info=True)
        return []

def remove_pending_user(telegram_id, processed_by=None):
    """
    Remove a user from the pending approval list.
    
    This function removes users from the pending list after they've been
    processed (either approved or rejected). It's called after admin
    makes a decision on the access request.
    
    Args:
        telegram_id (str): User's Telegram ID to remove
        processed_by (str): Admin who processed the request (optional)
        
    Returns:
        bool: True if user was removed successfully, False otherwise
        
    Database Impact:
        - Deletes record from pending_users table
        - Logs the processing action for audit trail
    """
    logger.info(f"Removing pending user: {telegram_id}, processed_by: {processed_by}")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                
                # Get user info before deletion for logging
                cursor.execute("SELECT username FROM pending_users WHERE telegram_id = ?", (str(telegram_id),))
                user_record = cursor.fetchone()
                username = user_record[0] if user_record else None
                
                # Remove from pending list
                cursor.execute("DELETE FROM pending_users WHERE telegram_id = ?", (str(telegram_id),))
                
                # Log the processing action
                log_cloudverse_history_event(
                    telegram_id=str(telegram_id),
                    username=username,
                    user_role="pending",
                    action_taken="request_processed",
                    status="completed",
                    handled_by=processed_by,
                    event_details=f"Pending request processed for: {username or telegram_id}"
                )
                logger.info(f"Successfully removed pending user: {username or telegram_id}")
                return True
    except Exception as e:
        logger.error(f"Failed to remove pending user {telegram_id}: {str(e)}", exc_info=True)
        return False

def update_pending_user_group_message(telegram_id, group_message_id):
    """
    Update the group message ID for a pending user request.
    
    This function updates the message ID in the admin group that corresponds
    to a user's access request. Used for tracking which message relates to
    which user request.
    
    Args:
        telegram_id (str): User's Telegram ID
        group_message_id (int): Message ID in the admin group
        
    Returns:
        bool: True if updated successfully, False otherwise
    """
    logger.debug(f"Updating group message ID for pending user {telegram_id}: {group_message_id}")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE pending_users 
                    SET group_message_id = ?
                    WHERE telegram_id = ?
                """, (group_message_id, str(telegram_id)))
                logger.debug(f"Updated group message ID for user {telegram_id}")
                return True
    except Exception as e:
        logger.error(f"Failed to update group message ID for user {telegram_id}: {str(e)}", exc_info=True)
        return False

def get_pending_user_group_message(telegram_id):
    """
    Get the group message ID for a pending user request.
    
    Args:
        telegram_id (str): User's Telegram ID
        
    Returns:
        int: Group message ID if found, None otherwise
    """
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT group_message_id FROM pending_users WHERE telegram_id = ?", (str(telegram_id),))
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"Failed to get group message ID for user {telegram_id}: {str(e)}", exc_info=True)
        return None

def clear_pending_user_group_message(telegram_id):
    """
    Clear the group message ID for a pending user request.
    
    Args:
        telegram_id (str): User's Telegram ID
        
    Returns:
        bool: True if cleared successfully, False otherwise
    """
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE pending_users 
                    SET group_message_id = NULL
                    WHERE telegram_id = ?
                """, (str(telegram_id),))
                return True
    except Exception as e:
        logger.error(f"Failed to clear group message ID for user {telegram_id}: {str(e)}", exc_info=True)
        return False

# ============================================================================
# UPLOAD MANAGEMENT - Functions for tracking file uploads and operations
# ============================================================================

def insert_upload(telegram_id, file_id=None, file_name=None, file_size=None, file_type=None, 
                 message_id=None, chat_id=None, status='pending', error_message=None, 
                 upload_method=None, average_speed=None, upload_source=None, upload_duration=None):
    """
    Record a file upload attempt in the database.
    
    This function tracks all file upload operations, including successful uploads,
    failed attempts, and upload statistics. It's essential for monitoring system
    usage, performance, and troubleshooting upload issues.
    
    Args:
        telegram_id (str): User's Telegram ID
        file_id (str): Telegram file ID (optional)
        file_name (str): Name of the uploaded file (optional)
        file_size (int): File size in bytes (optional)
        file_type (str): MIME type of the file (optional)
        message_id (int): Telegram message ID (optional)
        chat_id (int): Telegram chat ID (optional)
        status (str): Upload status ('pending', 'success', 'failed', 'cancelled')
        error_message (str): Error description if upload failed (optional)
        upload_method (str): Method used for upload ('direct', 'url', 'batch') (optional)
        average_speed (float): Upload speed in bytes/second (optional)
        upload_source (str): Source of the upload ('telegram', 'url', 'api') (optional)
        upload_duration (float): Time taken for upload in seconds (optional)
        
    Returns:
        int: Upload record ID if successful, None otherwise
        
    Database Impact:
        - Inserts new record into uploads table
        - Auto-generates unique ID for tracking
        - Records timestamp for analytics
    """
    logger.info(f"Recording upload: user={telegram_id}, file={file_name}, status={status}")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                
                # Get username for the record
                username = None
                cursor.execute("SELECT username FROM whitelisted_users WHERE telegram_id = ?", (str(telegram_id),))
                user_record = cursor.fetchone()
                if user_record:
                    username = user_record[0]
                else:
                    # Try administrators table
                    cursor.execute("SELECT username FROM administrators WHERE telegram_id = ?", (str(telegram_id),))
                    admin_record = cursor.fetchone()
                    if admin_record:
                        username = admin_record[0]
                
                cursor.execute("""
                    INSERT INTO uploads 
                    (telegram_id, username, chat_id, message_id, file_name, file_type, file_size, 
                     status, error_message, upload_method, average_speed, upload_source, 
                     upload_duration, uploaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (str(telegram_id), username, chat_id, message_id, file_name, file_type, 
                      file_size, status, error_message, upload_method, average_speed, 
                      upload_source, upload_duration))
                
                upload_id = cursor.lastrowid
                logger.info(f"Successfully recorded upload with ID: {upload_id}")
                return upload_id
    except Exception as e:
        logger.error(f"Failed to record upload for user {telegram_id}: {str(e)}", exc_info=True)
        return None

def get_upload_by_file_id(file_id):
    """
    Retrieve upload record by Telegram file ID.
    
    This function finds upload records based on the Telegram file ID,
    useful for tracking specific file operations and their status.
    
    Args:
        file_id (str): Telegram file ID to search for
        
    Returns:
        dict: Upload record dictionary if found, None otherwise
        
    Dictionary Structure:
        - id: Upload record ID
        - telegram_id: User's Telegram ID
        - username: User's username
        - file_name: Name of the file
        - file_size: Size in bytes
        - status: Upload status
        - uploaded_at: Upload timestamp
        - (and other upload fields)
    """
    logger.debug(f"Retrieving upload record for file_id: {file_id}")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, telegram_id, username, chat_id, message_id, file_name, file_type, 
                       file_size, status, error_message, upload_method, average_speed, 
                       upload_source, upload_duration, uploaded_at
                FROM uploads 
                WHERE message_id = ? OR file_name LIKE ?
                ORDER BY uploaded_at DESC
                LIMIT 1
            """, (file_id, f"%{file_id}%"))
            
            row = cursor.fetchone()
            if row:
                upload_record = {
                    'id': row[0],
                    'telegram_id': row[1],
                    'username': row[2],
                    'chat_id': row[3],
                    'message_id': row[4],
                    'file_name': row[5],
                    'file_type': row[6],
                    'file_size': row[7],
                    'status': row[8],
                    'error_message': row[9],
                    'upload_method': row[10],
                    'average_speed': row[11],
                    'upload_source': row[12],
                    'upload_duration': row[13],
                    'uploaded_at': row[14]
                }
                logger.debug(f"Found upload record: {upload_record['id']}")
                return upload_record
            else:
                logger.debug(f"No upload record found for file_id: {file_id}")
                return None
    except Exception as e:
        logger.error(f"Failed to retrieve upload record for file_id {file_id}: {str(e)}", exc_info=True)
        return None

def get_user_upload_stats(telegram_id, days=30):
    """
    Get comprehensive upload statistics for a specific user.
    
    This function provides detailed analytics about a user's upload activity,
    including total uploads, success rate, bandwidth usage, and performance metrics.
    
    Args:
        telegram_id (str): User's Telegram ID
        days (int): Number of days to analyze (default: 30)
        
    Returns:
        dict: Dictionary containing upload statistics
        
    Statistics Included:
        - total_uploads: Total number of upload attempts
        - successful_uploads: Number of successful uploads
        - failed_uploads: Number of failed uploads
        - success_rate: Percentage of successful uploads
        - total_bandwidth: Total bytes uploaded
        - average_file_size: Average file size in bytes
        - most_common_file_type: Most frequently uploaded file type
        - upload_activity_by_day: Daily upload counts
        - average_upload_speed: Average upload speed
    """
    logger.debug(f"Getting upload stats for user {telegram_id} (last {days} days)")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            
            # Calculate date range
            date_filter = f"uploaded_at >= DATE('now', '-{days} days')"
            
            stats = {}
            
            # Total uploads
            cursor.execute(f"""
                SELECT COUNT(*) FROM uploads 
                WHERE telegram_id = ? AND {date_filter}
            """, (str(telegram_id),))
            stats['total_uploads'] = cursor.fetchone()[0]
            
            # Successful uploads
            cursor.execute(f"""
                SELECT COUNT(*) FROM uploads 
                WHERE telegram_id = ? AND status = 'success' AND {date_filter}
            """, (str(telegram_id),))
            stats['successful_uploads'] = cursor.fetchone()[0]
            
            # Failed uploads
            cursor.execute(f"""
                SELECT COUNT(*) FROM uploads 
                WHERE telegram_id = ? AND status = 'failed' AND {date_filter}
            """, (str(telegram_id),))
            stats['failed_uploads'] = cursor.fetchone()[0]
            
            # Success rate
            if stats['total_uploads'] > 0:
                stats['success_rate'] = (stats['successful_uploads'] / stats['total_uploads']) * 100
            else:
                stats['success_rate'] = 0
            
            # Total bandwidth (successful uploads only)
            cursor.execute(f"""
                SELECT COALESCE(SUM(file_size), 0) FROM uploads 
                WHERE telegram_id = ? AND status = 'success' AND {date_filter}
            """, (str(telegram_id),))
            stats['total_bandwidth'] = cursor.fetchone()[0]
            
            # Average file size
            cursor.execute(f"""
                SELECT COALESCE(AVG(file_size), 0) FROM uploads 
                WHERE telegram_id = ? AND status = 'success' AND file_size IS NOT NULL AND {date_filter}
            """, (str(telegram_id),))
            stats['average_file_size'] = cursor.fetchone()[0]
            
            # Most common file type
            cursor.execute(f"""
                SELECT file_type, COUNT(*) as count FROM uploads 
                WHERE telegram_id = ? AND file_type IS NOT NULL AND {date_filter}
                GROUP BY file_type 
                ORDER BY count DESC 
                LIMIT 1
            """, (str(telegram_id),))
            file_type_result = cursor.fetchone()
            stats['most_common_file_type'] = file_type_result[0] if file_type_result else None
            
            # Upload activity by day
            cursor.execute(f"""
                SELECT DATE(uploaded_at) as upload_date, COUNT(*) as count 
                FROM uploads 
                WHERE telegram_id = ? AND {date_filter}
                GROUP BY DATE(uploaded_at) 
                ORDER BY upload_date DESC
            """, (str(telegram_id),))
            stats['upload_activity_by_day'] = cursor.fetchall()
            
            # Average upload speed
            cursor.execute(f"""
                SELECT COALESCE(AVG(average_speed), 0) FROM uploads 
                WHERE telegram_id = ? AND average_speed IS NOT NULL AND {date_filter}
            """, (str(telegram_id),))
            stats['average_upload_speed'] = cursor.fetchone()[0]
            
            logger.debug(f"Retrieved upload stats for user {telegram_id}: {stats['total_uploads']} uploads")
            return stats
    except Exception as e:
        logger.error(f"Failed to get upload stats for user {telegram_id}: {str(e)}", exc_info=True)
        return {
            'total_uploads': 0,
            'successful_uploads': 0,
            'failed_uploads': 0,
            'success_rate': 0,
            'total_bandwidth': 0,
            'average_file_size': 0,
            'most_common_file_type': None,
            'upload_activity_by_day': [],
            'average_upload_speed': 0
        }

def update_upload_status(upload_id, status, error_message=None, average_speed=None, upload_duration=None):
    """
    Update the status and metrics of an existing upload record.
    
    This function is used to update upload records as they progress through
    different stages (pending -> in_progress -> success/failed).
    
    Args:
        upload_id (int): Upload record ID
        status (str): New status ('pending', 'in_progress', 'success', 'failed', 'cancelled')
        error_message (str): Error description if status is 'failed' (optional)
        average_speed (float): Upload speed in bytes/second (optional)
        upload_duration (float): Total upload time in seconds (optional)
        
    Returns:
        bool: True if updated successfully, False otherwise
    """
    logger.debug(f"Updating upload {upload_id} status to: {status}")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE uploads 
                    SET status = ?, error_message = ?, average_speed = ?, upload_duration = ?
                    WHERE id = ?
                """, (status, error_message, average_speed, upload_duration, upload_id))
                
                logger.debug(f"Successfully updated upload {upload_id}")
                return True
    except Exception as e:
        logger.error(f"Failed to update upload {upload_id}: {str(e)}", exc_info=True)
        return False

# ============================================================================
# HISTORY AND AUDIT LOGGING - Functions for tracking system events
# ============================================================================

def log_cloudverse_history_event(telegram_id, username=None, user_role=None, action_taken=None, 
                                status=None, handled_by=None, related_message_id=None, 
                                event_details=None, notes=None):
    """
    Log system events to the CloudVerse history table for audit trail.
    
    This function records all significant system events, user actions, and
    administrative operations for security auditing, troubleshooting, and
    compliance purposes. It's essential for maintaining a complete audit trail.
    
    Args:
        telegram_id (str): User's Telegram ID
        username (str): User's username (optional)
        user_role (str): User's role ('admin', 'super_admin', 'whitelist', 'blacklist', 'pending')
        action_taken (str): Description of the action performed
        status (str): Status of the action ('success', 'failed', 'pending', 'cancelled')
        handled_by (str): ID of admin who handled the action (optional)
        related_message_id (str): Related Telegram message ID (optional)
        event_details (str): Detailed description of the event (optional)
        notes (str): Additional notes or comments (optional)
        
    Returns:
        int: History record ID if successful, None otherwise
        
    Common Action Types:
        - admin_promotion, admin_removal
        - whitelist_addition, whitelist_removal
        - blacklist_addition, blacklist_removal
        - access_request, request_processed
        - file_upload, file_download
        - login, logout
        - permission_change, quota_change
        
    Database Impact:
        - Inserts new record into cloudverse_history table
        - Auto-generates unique ID and timestamp
        - Provides complete audit trail for compliance
    """
    logger.debug(f"Logging history event: user={telegram_id}, action={action_taken}, status={status}")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO cloudverse_history 
                    (telegram_id, username, user_role, action_taken, status, handled_by, 
                     related_message_id, event_details, notes, event_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (str(telegram_id), username, user_role, action_taken, status, 
                      handled_by, related_message_id, event_details, notes))
                
                history_id = cursor.lastrowid
                logger.debug(f"Successfully logged history event with ID: {history_id}")
                return history_id
    except Exception as e:
        logger.error(f"Failed to log history event for user {telegram_id}: {str(e)}", exc_info=True)
        return None

def get_user_history(telegram_id, limit=50):
    """
    Retrieve history events for a specific user.
    
    Args:
        telegram_id (str): User's Telegram ID
        limit (int): Maximum number of records to return (default: 50)
        
    Returns:
        list: List of history event dictionaries
    """
    logger.debug(f"Retrieving history for user {telegram_id} (limit: {limit})")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, telegram_id, username, user_role, action_taken, status, 
                       handled_by, related_message_id, event_details, notes, event_time
                FROM cloudverse_history 
                WHERE telegram_id = ?
                ORDER BY event_time DESC
                LIMIT ?
            """, (str(telegram_id), limit))
            
            rows = cursor.fetchall()
            history_events = []
            for row in rows:
                history_events.append({
                    'id': row[0],
                    'telegram_id': row[1],
                    'username': row[2],
                    'user_role': row[3],
                    'action_taken': row[4],
                    'status': row[5],
                    'handled_by': row[6],
                    'related_message_id': row[7],
                    'event_details': row[8],
                    'notes': row[9],
                    'event_time': row[10]
                })
            
            logger.debug(f"Retrieved {len(history_events)} history events for user {telegram_id}")
            return history_events
    except Exception as e:
        logger.error(f"Failed to retrieve history for user {telegram_id}: {str(e)}", exc_info=True)
        return []

# ============================================================================
# USER PROFILE AND CREDENTIALS - Functions for user account management
# ============================================================================

def get_user_credentials(telegram_id):
    """
    Get user's Google Drive credentials information (without sensitive data).
    
    This function retrieves user credential information for display purposes,
    excluding the actual encrypted credential data for security.
    
    Args:
        telegram_id (str): User's Telegram ID
        
    Returns:
        dict: Dictionary containing credential information
        
    Dictionary Structure:
        - telegram_id: User's Telegram ID
        - username: User's username
        - name: User's full name
        - email_addresses: List of configured email addresses
        - primary_email_address: Primary email address
        - default_upload_location: Default upload folder
        - parallel_uploads: Number of parallel uploads allowed
        - last_updated: Last update timestamp
    """
    logger.debug(f"Getting credentials info for user {telegram_id}")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT telegram_id, username, name, email_address_1, email_address_2, 
                       email_address_3, primary_email_address, default_upload_location, 
                       parallel_uploads, last_updated
                FROM user_credentials 
                WHERE telegram_id = ?
            """, (str(telegram_id),))
            
            row = cursor.fetchone()
            if row:
                # Filter out None email addresses
                email_addresses = [email for email in [row[3], row[4], row[5]] if email]
                
                credentials_info = {
                    'telegram_id': row[0],
                    'username': row[1],
                    'name': row[2],
                    'email_addresses': email_addresses,
                    'primary_email_address': row[6],
                    'default_upload_location': row[7],
                    'parallel_uploads': row[8],
                    'last_updated': row[9]
                }
                logger.debug(f"Retrieved credentials info for user {telegram_id}")
                return credentials_info
            else:
                logger.debug(f"No credentials found for user {telegram_id}")
                return None
    except Exception as e:
        logger.error(f"Failed to get credentials info for user {telegram_id}: {str(e)}", exc_info=True)
        return None

def get_user_default_folder_id(telegram_id):
    """
    Get user's default upload folder ID.
    
    Args:
        telegram_id (str): User's Telegram ID
        
    Returns:
        str: Default folder ID ('root' if not set or user not found)
    """
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT default_upload_location FROM user_credentials WHERE telegram_id = ?", 
                         (str(telegram_id),))
            result = cursor.fetchone()
            return result[0] if result and result[0] else 'root'
    except Exception as e:
        logger.error(f"Failed to get default folder for user {telegram_id}: {str(e)}", exc_info=True)
        return 'root'

def get_user_monthly_bandwidth(telegram_id):
    """
    Get user's bandwidth usage for the current month.
    
    Args:
        telegram_id (str): User's Telegram ID
        
    Returns:
        int: Total bytes uploaded this month
    """
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(file_size), 0) 
                FROM uploads 
                WHERE telegram_id = ? 
                AND status = 'success' 
                AND uploaded_at >= DATE('now', 'start of month')
            """, (str(telegram_id),))
            result = cursor.fetchone()
            return result[0] if result else 0
    except Exception as e:
        logger.error(f"Failed to get monthly bandwidth for user {telegram_id}: {str(e)}", exc_info=True)
        return 0

def get_user_total_bandwidth(telegram_id):
    """
    Get user's total bandwidth usage (all time).
    
    Args:
        telegram_id (str): User's Telegram ID
        
    Returns:
        int: Total bytes uploaded (all time)
    """
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(file_size), 0) 
                FROM uploads 
                WHERE telegram_id = ? AND status = 'success'
            """, (str(telegram_id),))
            result = cursor.fetchone()
            return result[0] if result else 0
    except Exception as e:
        logger.error(f"Failed to get total bandwidth for user {telegram_id}: {str(e)}", exc_info=True)
        return 0

# ============================================================================
# ACCESS MANAGEMENT - Functions for managing user access and expiration
# ============================================================================

def mark_expired_users():
    """
    Mark users with expired whitelist access and move them to appropriate status.
    
    This function checks for users whose whitelist access has expired and
    handles them according to the system policy. It's typically called
    periodically by a background task.
    
    Returns:
        list: List of users who were marked as expired
    """
    logger.info("Checking for expired whitelist users")
    expired_users = []
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                
                # Find expired users
                cursor.execute("""
                    SELECT telegram_id, username, name, expiration_time
                    FROM whitelisted_users 
                    WHERE expiration_time IS NOT NULL 
                    AND expiration_time <= CURRENT_TIMESTAMP
                """)
                
                expired_records = cursor.fetchall()
                
                for record in expired_records:
                    telegram_id, username, name, expiration_time = record
                    
                    # Log the expiration event
                    log_cloudverse_history_event(
                        telegram_id=telegram_id,
                        username=username,
                        user_role="whitelist",
                        action_taken="access_expired",
                        status="expired",
                        event_details=f"Whitelist access expired at {expiration_time}"
                    )
                    
                    # Remove from whitelist
                    cursor.execute("DELETE FROM whitelisted_users WHERE telegram_id = ?", (telegram_id,))
                    
                    expired_users.append({
                        'telegram_id': telegram_id,
                        'username': username,
                        'name': name,
                        'expiration_time': expiration_time
                    })
                
                logger.info(f"Marked {len(expired_users)} users as expired")
                return expired_users
    except Exception as e:
        logger.error(f"Failed to mark expired users: {str(e)}", exc_info=True)
        return []

# ============================================================================
# ANALYTICS AND REPORTING - Functions for system analytics and reporting
# ============================================================================

def get_all_users_for_analytics():
    """
    Get all users from various tables for analytics reporting.
    
    This function combines users from administrators, whitelisted_users, and
    other relevant tables to provide a comprehensive user list for analytics.
    
    Returns:
        list: List of user dictionaries with analytics information
    """
    logger.debug("Retrieving all users for analytics")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            
            all_users = []
            
            # Get administrators
            cursor.execute("""
                SELECT telegram_id, username, name, 'admin' as user_type, 
                       is_super_admin, promoted_at as joined_at
                FROM administrators
            """)
            admin_rows = cursor.fetchall()
            
            for row in admin_rows:
                user_type = 'super_admin' if row[4] else 'admin'
                all_users.append({
                    'telegram_id': row[0],
                    'username': row[1],
                    'name': row[2],
                    'user_type': user_type,
                    'joined_at': row[5],
                    'is_super_admin': bool(row[4])
                })
            
            # Get whitelisted users
            cursor.execute("""
                SELECT telegram_id, username, name, 'whitelist' as user_type,
                       approved_at as joined_at, expiration_time
                FROM whitelisted_users
            """)
            whitelist_rows = cursor.fetchall()
            
            for row in whitelist_rows:
                all_users.append({
                    'telegram_id': row[0],
                    'username': row[1],
                    'name': row[2],
                    'user_type': row[3],
                    'joined_at': row[4],
                    'expiration_time': row[5],
                    'is_super_admin': False
                })
            
            # Get blacklisted users
            cursor.execute("""
                SELECT telegram_id, username, name, 'blacklist' as user_type,
                       restricted_at as joined_at, restriction_type
                FROM blacklisted_users
            """)
            blacklist_rows = cursor.fetchall()
            
            for row in blacklist_rows:
                all_users.append({
                    'telegram_id': row[0],
                    'username': row[1],
                    'name': row[2],
                    'user_type': row[3],
                    'joined_at': row[4],
                    'restriction_type': row[5],
                    'is_super_admin': False
                })
            
            logger.debug(f"Retrieved {len(all_users)} users for analytics")
            return all_users
    except Exception as e:
        logger.error(f"Failed to get all users for analytics: {str(e)}", exc_info=True)
        return []

def get_all_users_for_analytics_paginated(page=1, page_size=20):
    """
    Get paginated list of all users for analytics.
    
    Args:
        page (int): Page number (1-based)
        page_size (int): Number of users per page
        
    Returns:
        dict: Dictionary containing users list and pagination info
    """
    logger.debug(f"Getting paginated users for analytics: page={page}, size={page_size}")
    try:
        all_users = get_all_users_for_analytics()
        
        # Calculate pagination
        total_users = len(all_users)
        total_pages = (total_users + page_size - 1) // page_size
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        paginated_users = all_users[start_index:end_index]
        
        return {
            'users': paginated_users,
            'current_page': page,
            'total_pages': total_pages,
            'total_users': total_users,
            'page_size': page_size
        }
    except Exception as e:
        logger.error(f"Failed to get paginated users: {str(e)}", exc_info=True)
        return {
            'users': [],
            'current_page': 1,
            'total_pages': 1,
            'total_users': 0,
            'page_size': page_size
        }

def get_admins_paginated(page=1, page_size=10):
    """
    Get paginated list of administrators.
    
    Args:
        page (int): Page number (1-based)
        page_size (int): Number of admins per page
        
    Returns:
        dict: Dictionary containing admins list and pagination info
    """
    logger.debug(f"Getting paginated admins: page={page}, size={page_size}")
    try:
        all_admins = get_admins()
        
        # Calculate pagination
        total_admins = len(all_admins)
        total_pages = (total_admins + page_size - 1) // page_size
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        paginated_admins = all_admins[start_index:end_index]
        
        return {
            'admins': paginated_admins,
            'current_page': page,
            'total_pages': total_pages,
            'total_admins': total_admins,
            'page_size': page_size
        }
    except Exception as e:
        logger.error(f"Failed to get paginated admins: {str(e)}", exc_info=True)
        return {
            'admins': [],
            'current_page': 1,
            'total_pages': 1,
            'total_admins': 0,
            'page_size': page_size
        }

def get_user_top_file_types(telegram_id, limit=5):
    """
    Get user's most frequently uploaded file types.
    
    Args:
        telegram_id (str): User's Telegram ID
        limit (int): Number of top file types to return
        
    Returns:
        list: List of tuples (file_type, count)
    """
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT file_type, COUNT(*) as count
                FROM uploads 
                WHERE telegram_id = ? AND file_type IS NOT NULL AND status = 'success'
                GROUP BY file_type 
                ORDER BY count DESC 
                LIMIT ?
            """, (str(telegram_id), limit))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to get top file types for user {telegram_id}: {str(e)}", exc_info=True)
        return []

def get_user_upload_activity_by_hour(telegram_id, days=30):
    """
    Get user's upload activity distribution by hour of day.
    
    Args:
        telegram_id (str): User's Telegram ID
        days (int): Number of days to analyze
        
    Returns:
        list: List of tuples (hour, count)
    """
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT strftime('%H', uploaded_at) as hour, COUNT(*) as count
                FROM uploads 
                WHERE telegram_id = ? 
                AND uploaded_at >= DATE('now', '-{} days')
                GROUP BY strftime('%H', uploaded_at)
                ORDER BY hour
            """.format(days), (str(telegram_id),))
            
            # Convert hour strings to integers
            results = [(int(row[0]), row[1]) for row in cursor.fetchall()]
            return results
    except Exception as e:
        logger.error(f"Failed to get upload activity by hour for user {telegram_id}: {str(e)}", exc_info=True)
        return []

def get_user_details_by_id(telegram_id):
    """
    Get comprehensive user details by Telegram ID.
    
    This function searches across all user tables to find complete information
    about a user, including their role, status, and activity.
    
    Args:
        telegram_id (str): User's Telegram ID
        
    Returns:
        dict: Dictionary containing comprehensive user information
    """
    logger.debug(f"Getting user details for {telegram_id}")
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            
            user_details = {
                'telegram_id': telegram_id,
                'found': False,
                'user_type': None,
                'username': None,
                'name': None,
                'status': None,
                'joined_at': None,
                'last_activity': None
            }
            
            # Check administrators table
            cursor.execute("""
                SELECT username, name, is_super_admin, promoted_at, last_updated
                FROM administrators WHERE telegram_id = ?
            """, (str(telegram_id),))
            admin_row = cursor.fetchone()
            
            if admin_row:
                user_details.update({
                    'found': True,
                    'user_type': 'super_admin' if admin_row[2] else 'admin',
                    'username': admin_row[0],
                    'name': admin_row[1],
                    'status': 'active',
                    'joined_at': admin_row[3],
                    'last_activity': admin_row[4]
                })
                return user_details
            
            # Check whitelisted_users table
            cursor.execute("""
                SELECT username, name, approved_at, expiration_time, last_updated
                FROM whitelisted_users WHERE telegram_id = ?
            """, (str(telegram_id),))
            whitelist_row = cursor.fetchone()
            
            if whitelist_row:
                status = 'active'
                if whitelist_row[3]:  # has expiration_time
                    # Check if expired
                    cursor.execute("SELECT CURRENT_TIMESTAMP > ? as is_expired", (whitelist_row[3],))
                    is_expired = cursor.fetchone()[0]
                    status = 'expired' if is_expired else 'active'
                
                user_details.update({
                    'found': True,
                    'user_type': 'whitelist',
                    'username': whitelist_row[0],
                    'name': whitelist_row[1],
                    'status': status,
                    'joined_at': whitelist_row[2],
                    'expiration_time': whitelist_row[3],
                    'last_activity': whitelist_row[4]
                })
                return user_details
            
            # Check blacklisted_users table
            cursor.execute("""
                SELECT username, name, restriction_type, restricted_at, restriction_period
                FROM blacklisted_users WHERE telegram_id = ?
            """, (str(telegram_id),))
            blacklist_row = cursor.fetchone()
            
            if blacklist_row:
                user_details.update({
                    'found': True,
                    'user_type': 'blacklist',
                    'username': blacklist_row[0],
                    'name': blacklist_row[1],
                    'status': 'restricted',
                    'restriction_type': blacklist_row[2],
                    'joined_at': blacklist_row[3],
                    'restriction_period': blacklist_row[4]
                })
                return user_details
            
            # Check pending_users table
            cursor.execute("""
                SELECT username, first_name, last_name, requested_at
                FROM pending_users WHERE telegram_id = ?
            """, (str(telegram_id),))
            pending_row = cursor.fetchone()
            
            if pending_row:
                full_name = f"{pending_row[1] or ''} {pending_row[2] or ''}".strip()
                user_details.update({
                    'found': True,
                    'user_type': 'pending',
                    'username': pending_row[0],
                    'name': full_name,
                    'status': 'pending',
                    'joined_at': pending_row[3]
                })
                return user_details
            
            logger.debug(f"User {telegram_id} not found in any table")
            return user_details
            
    except Exception as e:
        logger.error(f"Failed to get user details for {telegram_id}: {str(e)}", exc_info=True)
        return {
            'telegram_id': telegram_id,
            'found': False,
            'error': str(e)
        }

def get_user_uploads_per_day(telegram_id, days=30):
    """
    Get user's daily upload counts for the specified period.
    
    Args:
        telegram_id (str): User's Telegram ID
        days (int): Number of days to analyze
        
    Returns:
        list: List of tuples (date, count)
    """
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DATE(uploaded_at) as upload_date, COUNT(*) as count
                FROM uploads 
                WHERE telegram_id = ? 
                AND uploaded_at >= DATE('now', '-{} days')
                GROUP BY DATE(uploaded_at)
                ORDER BY upload_date DESC
            """.format(days), (str(telegram_id),))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to get uploads per day for user {telegram_id}: {str(e)}", exc_info=True)
        return []