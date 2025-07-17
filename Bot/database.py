import sqlite3
from Bot.config import DB_PATH, SUPER_ADMIN_ID
from datetime import datetime, timedelta
from Bot.Logger import get_logger
logger = get_logger()

def init_db():
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        # Admins table
        # Table: admins
        cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
            telegram_id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            name TEXT,
            promoted_by TEXT,
            promoted_at TIMESTAMP,
            is_super_admin INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_admins_username ON admins(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_admins_promoted_by ON admins(promoted_by)")
        # Whitelisted Users table
        # Table: whitelisted_users
        cursor.execute('''CREATE TABLE IF NOT EXISTS whitelisted_users (
            telegram_id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            name TEXT,
            approved_by TEXT,
            approved_at TIMESTAMP,
            expiration_time TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_whitelisted_users_username ON whitelisted_users(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_whitelisted_users_approved_by ON whitelisted_users(approved_by)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_whitelisted_users_expiration_time ON whitelisted_users(expiration_time)")
        # Blacklisted Users table
        # Table: blacklisted_users
        cursor.execute('''CREATE TABLE IF NOT EXISTS blacklisted_users (
            telegram_id TEXT PRIMARY KEY,
            username TEXT,
            name TEXT,
            restriction_type TEXT, -- 'Temporary' or 'Permanent'
            restriction_end TIMESTAMP, -- NULL for permanent
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklisted_users_username ON blacklisted_users(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklisted_users_restriction_type ON blacklisted_users(restriction_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklisted_users_restriction_end ON blacklisted_users(restriction_end)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklisted_users_created_at ON blacklisted_users(created_at)")
        # Pending Users table
        # Table: pending_users
        cursor.execute('''CREATE TABLE IF NOT EXISTS pending_users (
            telegram_id TEXT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            group_message_id INTEGER
        )''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_users_username ON pending_users(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_users_requested_at ON pending_users(requested_at)")
        # Broadcasts table
        # Table: broadcasts
        cursor.execute('''CREATE TABLE IF NOT EXISTS broadcasts (
            request_id TEXT PRIMARY KEY,
            requester_id TEXT,
            message_text TEXT,
            media_type TEXT,
            media_file_id TEXT,
            approval_status TEXT,
            status TEXT,
            approved_by TEXT,
            approved_at TIMESTAMP,
            created_at TIMESTAMP,
            target_count INTEGER,
            group_message_id INTEGER,
            approvers TEXT DEFAULT '[]'
        )''')
        # Add approvers column if it doesn't exist (for migrations)
        try:
            cursor.execute("ALTER TABLE broadcasts ADD COLUMN approvers TEXT DEFAULT '[]'")
        except Exception:
            pass
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_requester_id ON broadcasts(requester_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_status ON broadcasts(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_approved_by ON broadcasts(approved_by)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_created_at ON broadcasts(created_at)")
        # Uploads table
        # Table: uploads
        cursor.execute('''CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT,
            file_id TEXT,
            file_name TEXT,
            file_size INTEGER,
            file_type TEXT,
            message_id INTEGER,
            chat_id INTEGER,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT,
            error_message TEXT
        )''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_telegram_id ON uploads(telegram_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_file_id ON uploads(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_upload_time ON uploads(upload_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status)")
        # Team Cloudverse table
        # Table: team_cloudverse
        cursor.execute('''CREATE TABLE IF NOT EXISTS team_cloudverse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT,
            event_type TEXT,
            event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            event_details TEXT,
            status TEXT,
            handled_by TEXT,
            related_message_id TEXT,
            notes TEXT
        )''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_cloudverse_telegram_id ON team_cloudverse(telegram_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_cloudverse_event_type ON team_cloudverse(event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_cloudverse_event_time ON team_cloudverse(event_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_cloudverse_status ON team_cloudverse(status)")
        # Developer Messages table
        cursor.execute('''CREATE TABLE IF NOT EXISTS dev_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_telegram_id INTEGER NOT NULL,
            sender_role TEXT NOT NULL, -- 'user' or 'developer'
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            reply_to_id INTEGER,
            telegram_message_id INTEGER,
            delivery_status INTEGER DEFAULT 0
        )''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dev_messages_user_telegram_id ON dev_messages(user_telegram_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dev_messages_timestamp ON dev_messages(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dev_messages_delivery_status ON dev_messages(delivery_status)")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def insert_dev_message(user_telegram_id, sender_role, message, reply_to_id=None, telegram_message_id=None, delivery_status=0):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO dev_messages (user_telegram_id, sender_role, message, reply_to_id, telegram_message_id, delivery_status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_telegram_id, sender_role, message, reply_to_id, telegram_message_id, delivery_status))
    conn.commit()
    msg_id = cursor.lastrowid
    conn.close()
    return msg_id

def fetch_dev_messages(user_telegram_id, limit=20):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, sender_role, message, timestamp, reply_to_id, telegram_message_id, delivery_status
        FROM dev_messages
        WHERE user_telegram_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (user_telegram_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return rows

def mark_dev_message_delivered(msg_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE dev_messages SET delivery_status = 1 WHERE id = ?
    ''', (msg_id,))
    conn.commit()
    conn.close()

# Admin CRUD

def is_admin(telegram_id):
    try:
        from .config import SUPER_ADMIN_ID
        if str(telegram_id) == str(SUPER_ADMIN_ID):
            return True
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM admins WHERE telegram_id = ?", (str(telegram_id),))
        result = cursor.fetchone()
        conn.close()
        return bool(result)
    except Exception as e:
        logger.error(f"Failed to check admin status: {e}")
        return False

def is_super_admin(telegram_id):
    try:
        if not SUPER_ADMIN_ID:
            return False
        return str(telegram_id) == str(SUPER_ADMIN_ID)
    except Exception as e:
        logger.error(f"Failed to check super admin status: {e}")
        return False

def get_admins():
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, username, name, promoted_by, promoted_at, is_super_admin, last_updated FROM admins")
        admins = [
            {
                "telegram_id": row[0],
                "username": row[1],
                "name": row[2],
                "promoted_by": row[3],
                "promoted_at": row[4],
                "is_super_admin": row[5],
                "last_updated": row[6],
            } for row in cursor.fetchall()
        ]
        conn.close()
        return admins
    except Exception as e:
        logger.error(f"Failed to get admins: {e}")
        return []

def add_admin(telegram_id, username=None, name=None, promoted_by=None, is_super_admin=0):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO admins (telegram_id, username, name, promoted_by, promoted_at, is_super_admin, last_updated) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP)",
                       (str(telegram_id), username, name, promoted_by, is_super_admin))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to add admin: {e}")
        raise

def remove_admin(telegram_id):
    try:
        if is_super_admin(telegram_id):
            raise ValueError("Cannot remove super admin (developer)")
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE telegram_id = ?", (str(telegram_id),))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to remove admin: {e}")
        raise

# Whitelist CRUD

def is_whitelisted(telegram_id):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT expiration_time FROM whitelisted_users WHERE telegram_id = ?", (str(telegram_id),))
        row = cursor.fetchone()
        conn.close()
        if row:
            expiration_time = row[0]
            if expiration_time is None or datetime.fromisoformat(expiration_time) > datetime.now():
                return True
        return False
    except Exception as e:
        logger.error(f"Failed to check whitelist status: {e}")
        return False

def get_whitelist():
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, username, name, approved_by, approved_at, expiration_time, last_updated FROM whitelisted_users")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"telegram_id": row[0], "username": row[1], "name": row[2], "approved_by": row[3], "approved_at": row[4], "expiration_time": row[5], "last_updated": row[6]}
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Failed to get whitelist: {e}")
        return []

def add_whitelist(telegram_id, username=None, name=None, approved_by=None, expiration_time=None):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO whitelisted_users (telegram_id, username, name, approved_by, approved_at, expiration_time, last_updated) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP)",
                       (str(telegram_id), username, name, approved_by, expiration_time))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to add whitelist: {e}")
        raise

def remove_whitelist(telegram_id):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM whitelisted_users WHERE telegram_id = ?", (str(telegram_id),))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to remove whitelist: {e}")
        raise

# Blacklist CRUD

def add_blacklisted_user(telegram_id, username, name, restriction_type, restriction_end=None):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO blacklisted_users (telegram_id, username, name, restriction_type, restriction_end, updated_at, last_updated) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
                       (str(telegram_id), username, name, restriction_type, restriction_end))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to add blacklisted user: {e}")
        raise

def remove_blacklisted_user(telegram_id):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM blacklisted_users WHERE telegram_id = ?", (str(telegram_id),))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to remove blacklisted user: {e}")
        raise

def edit_blacklisted_user(telegram_id, restriction_type, restriction_end=None):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute('''UPDATE blacklisted_users SET restriction_type = ?, restriction_end = ?, updated_at = CURRENT_TIMESTAMP, last_updated = CURRENT_TIMESTAMP WHERE telegram_id = ?''',
                       (restriction_type, restriction_end, str(telegram_id)))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to edit blacklisted user: {e}")
        raise

def get_blacklisted_users():
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, username, name, restriction_type, restriction_end, created_at, updated_at, last_updated FROM blacklisted_users ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "telegram_id": r[0],
                "username": r[1],
                "name": r[2],
                "restriction_type": r[3],
                "restriction_end": r[4],
                "created_at": r[5],
                "updated_at": r[6],
                "last_updated": r[7],
            } for r in rows
        ]
    except Exception as e:
        logger.error(f"Failed to get blacklisted users: {e}")
        return []

# Broadcast CRUD

def create_broadcast_request(request_id, requester_id, message_text, media_type=None, media_file_id=None, target_count=0, approval_status=None, status='pending', approved_by=None, approved_at=None, group_message_id=None, approvers=None):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        import json
        if approvers is None:
            approvers = []
        approvers_json = json.dumps(approvers)
        cursor.execute("""INSERT INTO broadcasts 
                         (request_id, requester_id, message_text, media_type, media_file_id, approval_status, status, approved_by, approved_at, created_at, target_count, group_message_id, approvers)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (request_id, str(requester_id), message_text, media_type, media_file_id, approval_status, status, approved_by, approved_at, datetime.now().isoformat(), target_count, group_message_id, approvers_json))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to create broadcast request: {e}")
        return False

def get_broadcast_request(request_id):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT request_id, requester_id, message_text, media_type, media_file_id, approval_status, status, approved_by, approved_at, created_at, target_count, group_message_id, approvers FROM broadcasts WHERE request_id = ?", (request_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            import json
            try:
                approvers = json.loads(row[12]) if row[12] else []
            except Exception:
                approvers = []
            return {
                'request_id': row[0],
                'requester_id': row[1],
                'message_text': row[2],
                'media_type': row[3],
                'media_file_id': row[4],
                'approval_status': row[5],
                'status': row[6],
                'approved_by': row[7],
                'approved_at': row[8],
                'created_at': row[9],
                'target_count': row[10],
                'group_message_id': row[11],
                'approvers': approvers
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get broadcast request: {e}")
        return None

def update_broadcast_status(request_id, status):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("UPDATE broadcasts SET status = ? WHERE request_id = ?", (status, request_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to update broadcast status: {e}")
        return False

def store_broadcast_group_message(request_id, message_id):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("UPDATE broadcasts SET group_message_id = ? WHERE request_id = ?", (message_id, request_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to store broadcast group message: {e}")
        return False

def get_broadcast_group_message(request_id):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT group_message_id FROM broadcasts WHERE request_id = ?", (request_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Failed to get broadcast group message: {e}")
        return None

def update_broadcast_approvers(request_id, approvers):
    """Update the approvers list for a broadcast request (as JSON array)."""
    try:
        import json
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        approvers_json = json.dumps(approvers)
        cursor.execute("UPDATE broadcasts SET approvers = ? WHERE request_id = ?", (approvers_json, request_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to update broadcast approvers: {e}")
        return False

def log_team_cloudverse_event(telegram_id, event_type, event_details=None, status=None, handled_by=None, related_message_id=None, notes=None):
    """
    Insert a new event into the team_cloudverse table.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO team_cloudverse (telegram_id, event_type, event_details, status, handled_by, related_message_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (telegram_id, event_type, event_details, status, handled_by, related_message_id, notes))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log team_cloudverse event: {e}")
        raise

def get_team_cloudverse_events(telegram_id=None, event_type=None, status=None):
    """
    Query events from the team_cloudverse table, optionally filtered by user, event type, or status.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        query = "SELECT id, telegram_id, event_type, event_time, event_details, status, handled_by, related_message_id, notes FROM team_cloudverse WHERE 1=1"
        params = []
        if telegram_id:
            query += " AND telegram_id = ?"
            params.append(telegram_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if status:
            query += " AND status = ?"
            params.append(status)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "telegram_id": r[1],
                "event_type": r[2],
                "event_time": r[3],
                "event_details": r[4],
                "status": r[5],
                "handled_by": r[6],
                "related_message_id": r[7],
                "notes": r[8],
            } for r in rows
        ]
    except Exception as e:
        logger.error(f"Failed to get team_cloudverse events: {e}")
        return []

def add_pending_user(telegram_id, username=None, first_name=None, last_name=None):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO pending_users (telegram_id, username, first_name, last_name, requested_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                       (str(telegram_id), username, first_name, last_name))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to add pending user: {e}")
        raise

def get_pending_users():
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, username, first_name, last_name, requested_at FROM pending_users ORDER BY requested_at ASC")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"telegram_id": row[0], "username": row[1], "first_name": row[2], "last_name": row[3], "requested_at": row[4]}
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Failed to get pending users: {e}")
        return []

def remove_pending_user(telegram_id):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pending_users WHERE telegram_id = ?", (str(telegram_id),))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to remove pending user: {e}")
        raise

# User details lookup

def get_user_details_by_id(telegram_id):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        # Search all user tables for details
        cursor.execute("SELECT telegram_id, username, name FROM admins WHERE telegram_id = ?", (str(telegram_id),))
        row = cursor.fetchone()
        if row:
            conn.close()
            return {"telegram_id": row[0], "username": row[1], "name": row[2]}
        cursor.execute("SELECT telegram_id, username, name FROM whitelisted_users WHERE telegram_id = ?", (str(telegram_id),))
        row = cursor.fetchone()
        if row:
            conn.close()
            return {"telegram_id": row[0], "username": row[1], "name": row[2]}
        cursor.execute("SELECT telegram_id, username, name FROM blacklisted_users WHERE telegram_id = ?", (str(telegram_id),))
        row = cursor.fetchone()
        if row:
            conn.close()
            return {"telegram_id": row[0], "username": row[1], "name": row[2]}
        cursor.execute("SELECT telegram_id, username, first_name || ' ' || last_name FROM pending_users WHERE telegram_id = ?", (str(telegram_id),))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"telegram_id": row[0], "username": row[1], "name": row[2]}
        return None
    except Exception as e:
        logger.error(f"Failed to get user details by id: {e}")
        return None

def get_user_id_by_username(username):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        # Search all user tables for username
        cursor.execute("SELECT telegram_id FROM admins WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row[0]
        cursor.execute("SELECT telegram_id FROM whitelisted_users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row[0]
        cursor.execute("SELECT telegram_id FROM blacklisted_users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row[0]
        cursor.execute("SELECT telegram_id FROM pending_users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
        return None
    except Exception as e:
        logger.error(f"Failed to get user id by username: {e}")
        return None

# Whitelist expiration setter

def set_whitelist_expiration(telegram_id, expiration_time):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("UPDATE whitelisted_users SET expiration_time = ?, last_updated = CURRENT_TIMESTAMP WHERE telegram_id = ?", (expiration_time, str(telegram_id)))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to set whitelist expiration: {e}")
        raise

def insert_upload(telegram_id, file_id, file_name, file_size, file_type, message_id, chat_id, status='success', error_message=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO uploads (telegram_id, file_id, file_name, file_size, file_type, message_id, chat_id, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (telegram_id, file_id, file_name, file_size, file_type, message_id, chat_id, status, error_message))
    conn.commit()
    upload_id = cursor.lastrowid
    conn.close()
    return upload_id

def get_upload_by_file_id(file_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT telegram_id, file_id, file_name, file_size, file_type, message_id, chat_id, status, error_message
        FROM uploads WHERE file_id = ?
        ORDER BY upload_time DESC LIMIT 1
    ''', (file_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'telegram_id': row[0],
            'file_id': row[1],
            'file_name': row[2],
            'file_size': row[3],
            'file_type': row[4],
            'message_id': row[5],
            'chat_id': row[6],
            'status': row[7],
            'error_message': row[8],
        }
    return None

def get_all_users_for_analytics():
    """Return a list of all users (telegram_id, username, name) from all user tables."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT telegram_id, username, name FROM admins
            UNION
            SELECT telegram_id, username, name FROM whitelisted_users
            UNION
            SELECT telegram_id, username, name FROM blacklisted_users
            UNION
            SELECT telegram_id, username, first_name || ' ' || last_name as name FROM pending_users
        """)
        users = cursor.fetchall()
        conn.close()
        return users
    except Exception as e:
        logger.error(f"Failed to get all users for analytics: {e}")
        return []

def get_user_upload_stats(user_id):
    """Return (count, min_upload_time, max_upload_time) for a user's uploads."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), MIN(upload_time), MAX(upload_time) FROM uploads WHERE telegram_id = ?", (user_id,))
        stats = cursor.fetchone()
        conn.close()
        return stats if stats else (0, None, None)
    except Exception as e:
        logger.error(f"Failed to get user upload stats: {e}")
        return (0, None, None)

def get_user_monthly_bandwidth(user_id, year_month):
    """Return total file_size for a user in a given YYYY-MM month."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(file_size) FROM uploads WHERE telegram_id = ? AND strftime('%Y-%m', upload_time) = ?", (user_id, year_month))
        total = cursor.fetchone()[0] or 0
        conn.close()
        return total
    except Exception as e:
        logger.error(f"Failed to get user monthly bandwidth: {e}")
        return 0

def get_num_active_users(minutes=10):
    """Return count of unique users who uploaded in the last X minutes."""
    try:
        since = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT telegram_id) FROM uploads WHERE upload_time >= ?", (since,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        logger.error(f"Failed to get num active users: {e}")
        return 0

def get_bandwidth_today():
    """Return total bandwidth used today (in bytes)."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(file_size) FROM uploads WHERE DATE(upload_time) = ?", (today,))
        total = cursor.fetchone()[0] or 0
        conn.close()
        return total
    except Exception as e:
        logger.error(f"Failed to get bandwidth today: {e}")
        return 0

def get_uploads_today():
    """Return total uploads today."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM uploads WHERE DATE(upload_time) = ?", (today,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        logger.error(f"Failed to get uploads today: {e}")
        return 0

def get_total_users():
    """Return count of unique users across all user tables."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT telegram_id) FROM (SELECT telegram_id FROM admins UNION SELECT telegram_id FROM whitelisted_users UNION SELECT telegram_id FROM blacklisted_users UNION SELECT telegram_id FROM pending_users)")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        logger.error(f"Failed to get total users: {e}")
        return 0

def update_pending_user_group_message(telegram_id, message_id):
    """Set group_message_id for a pending user."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("UPDATE pending_users SET group_message_id = ? WHERE telegram_id = ?", (message_id, str(telegram_id)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to update pending user group message: {e}")
        return False

def get_pending_user_group_message(telegram_id):
    """Get group_message_id for a pending user."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("SELECT group_message_id FROM pending_users WHERE telegram_id = ?", (str(telegram_id),))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Failed to get pending user group message: {e}")
        return None

def clear_pending_user_group_message(telegram_id):
    """Clear group_message_id for a pending user."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("UPDATE pending_users SET group_message_id = NULL WHERE telegram_id = ?", (str(telegram_id),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to clear pending user group message: {e}")
        return False