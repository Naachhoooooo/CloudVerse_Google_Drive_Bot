import sqlite3
from Bot.config import DB_PATH, SUPER_ADMIN_ID, CIPHER
from datetime import datetime, timedelta
import json

def init_db():
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                # Administrators table
                cursor.execute('''CREATE TABLE IF NOT EXISTS administrators (
                    telegram_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE,
                    name TEXT,
                    is_super_admin INTEGER DEFAULT 0,
                    promoted_by TEXT,
                    promoted_at TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_administrators_username ON administrators(username)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_administrators_is_super_admin ON administrators(is_super_admin)")
                # Whitelisted Users table
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
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_whitelisted_users_expiration_time ON whitelisted_users(expiration_time)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_whitelisted_users_approved_by ON whitelisted_users(approved_by)")
                # Blacklisted Users table
                cursor.execute('''CREATE TABLE IF NOT EXISTS blacklisted_users (
                    telegram_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE,
                    name TEXT,
                    restriction_type TEXT, -- 'temporary','permanent'
                    restriction_period TIMESTAMP,
                    restricted_at TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklisted_users_username ON blacklisted_users(username)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklisted_users_restriction_type ON blacklisted_users(restriction_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklisted_users_restriction_period ON blacklisted_users(restriction_period)")
                # User Credentials table
                cursor.execute('''CREATE TABLE IF NOT EXISTS user_credentials (
                    telegram_id TEXT,
                    name TEXT,
                    email_address_1 TEXT,
                    email_address_2 TEXT,
                    email_address_3 TEXT,
                    credential_1 TEXT,
                    credential_2 TEXT,
                    credential_3 TEXT,
                    primary_email_address TEXT,
                    default_folder_id TEXT DEFAULT 'root',
                    parallel_uploads INTEGER DEFAULT 1,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(telegram_id, email_address_1)
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
                    requester_id TEXT,
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
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_requester_id ON broadcasts(requester_id)")
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
                    file_id TEXT,
                    file_name TEXT,
                    file_type TEXT,
                    file_size INTEGER,
                    status TEXT,
                    error_message TEXT,
                    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_telegram_id ON uploads(telegram_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_username ON uploads(username)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_file_id ON uploads(file_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_upload_time ON uploads(upload_time)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status)")
                # CloudVerse History table
                cursor.execute('''CREATE TABLE IF NOT EXISTS cloudverse_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id TEXT,
                    username TEXT,
                    event_type TEXT,
                    status TEXT,
                    handled_by TEXT,
                    related_message_id TEXT,
                    event_details TEXT,
                    notes TEXT,
                    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloudverse_history_telegram_id ON cloudverse_history(telegram_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloudverse_history_username ON cloudverse_history(username)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloudverse_history_event_type ON cloudverse_history(event_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloudverse_history_event_time ON cloudverse_history(event_time)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloudverse_history_status ON cloudverse_history(status)")
                # Developer Messages table
                cursor.execute('''CREATE TABLE IF NOT EXISTS dev_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_telegram_id INTEGER NOT NULL,
                    user_role TEXT,
                    username TEXT,
                    user_name TEXT,
                    sender_role TEXT NOT NULL, -- 'user' or 'developer'
                    message TEXT NOT NULL,
                    telegram_message_id INTEGER,
                    reply_to_id INTEGER,
                    delivery_status INTEGER DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_dev_messages_user_telegram_id ON dev_messages(user_telegram_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_dev_messages_delivery_status ON dev_messages(delivery_status)")
    except Exception as e:
        raise

#Admin

def add_admin(telegram_id, username=None, name=None, promoted_by=None, is_super_admin=0):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO administrators (telegram_id, username, name, is_super_admin, promoted_by, promoted_at, last_updated) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                       (str(telegram_id), username, name, is_super_admin, promoted_by))
    except Exception as e:
        raise

def get_admins():
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM administrators")
                admins = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        return admins
    except Exception as e:
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
    try:
        if str(telegram_id) == str(SUPER_ADMIN_ID):
            return True
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM administrators WHERE telegram_id = ?", (str(telegram_id),))
                result = cursor.fetchone()
        return bool(result)
    except Exception as e:
        raise

def is_super_admin(telegram_id):
    try:
        if not SUPER_ADMIN_ID:
            return False
        return str(telegram_id) == str(SUPER_ADMIN_ID)
    except Exception as e:
        raise

def remove_admin(telegram_id):
    try:
        if is_super_admin(telegram_id):
            raise ValueError("Cannot remove super admin (developer)")
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM administrators WHERE telegram_id = ?", (str(telegram_id),))
    except Exception as e:
        raise

#Whitelisted

def add_whitelist(telegram_id, username=None, name=None, approved_by=None, approved_at=None, expiration_time=None):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO whitelisted_users (telegram_id, username, name, approved_by, approved_at, expiration_time, last_updated) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                       (str(telegram_id), username, name, approved_by, approved_at, expiration_time))
    except Exception as e:
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

def remove_whitelist(telegram_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM whitelisted_users WHERE telegram_id = ?", (str(telegram_id),))
    except Exception as e:
        raise

#Blacklisted

def add_blacklisted_user(telegram_id, username, name, restriction_type, restriction_period=None, restricted_at=None):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute('''INSERT OR REPLACE INTO blacklisted_users (telegram_id, username, name, restriction_type, restriction_period, restricted_at, last_updated) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                       (str(telegram_id), username, name, restriction_type, restriction_period, restricted_at))
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

def remove_blacklisted_user(telegram_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM blacklisted_users WHERE telegram_id = ?", (str(telegram_id),))
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
                    cursor.execute("SELECT default_folder_id FROM user_credentials WHERE telegram_id = ? AND email_address_1 = ?", (str(telegram_id), account_email))
                else:
                    cursor.execute("SELECT default_folder_id FROM user_credentials WHERE telegram_id = ?", (str(telegram_id),))
                row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        return 'root'
    except Exception as e:
        raise

#Broadcast Functions

def create_broadcast_request(request_id, requester_id, message_text, media_type=None, media_file_id=None, target_count=0, approval_status=None, status='pending', approved_by=None, approved_at=None, group_message_id=None, approvers=None):
    try:
        import json
        if approvers is None:
            approvers = []
        approvers_json = json.dumps(approvers)
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""INSERT INTO broadcasts
                         (request_id, requester_id, message_text, media_type, media_file_id, approval_status, status, approved_by, approved_at, last_updated, target_count, group_message_id)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (request_id, str(requester_id), message_text, media_type, media_file_id, approval_status, status, approved_by, approved_at, datetime.now().isoformat(), target_count, group_message_id))
    except Exception as e:
        raise

def get_broadcast_request(request_id):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT request_id, requester_id, message_text, media_type, media_file_id, approval_status, status, approved_by, approved_at, last_updated, target_count, group_message_id FROM broadcasts WHERE request_id = ?", (request_id,))
                row = cursor.fetchone()
        if row:
            import json
            try:
                approvers = json.loads(row[11]) if row[11] else []
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
                'last_updated': row[9],
                'target_count': row[10],
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

def insert_upload(telegram_id, username, chat_id, message_id, file_id, file_name, file_type, file_size, status='success', error_message=None):
    with sqlite3.connect(DB_PATH) as conn:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO uploads (telegram_id, username, chat_id, message_id, file_id, file_name, file_type, file_size, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (telegram_id, username, chat_id, message_id, file_id, file_name, file_type, file_size, status, error_message))
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

def log_cloudverse_history_event(telegram_id, event_type, status=None, handled_by=None, related_message_id=None, event_details=None, notes=None, username=None):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO cloudverse_history (telegram_id, username, event_type, status, handled_by, related_message_id, event_details, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (telegram_id, username, event_type, status, handled_by, related_message_id, event_details, notes))
    except Exception as e:
        raise

def get_cloudverse_history_events(telegram_id=None, event_type=None, status=None):
    try:
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            with conn:
                cursor = conn.cursor()
                query = "SELECT id, telegram_id, username, event_type, status, handled_by, related_message_id, event_details, notes, event_time FROM cloudverse_history WHERE 1=1"
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
        return [
            {
                "id": r[0],
                "telegram_id": r[1],
                "username": r[2],
                "event_type": r[3],
                "status": r[4],
                "handled_by": r[5],
                "related_message_id": r[6],
                "event_details": r[7],
                "notes": r[8],
                "event_time": r[9],
            } for r in rows
        ]
    except Exception as e:
        raise

#Devloper Messages Functions

def insert_dev_message(user_telegram_id, user_role, username, user_name, sender_role, message, telegram_message_id=None, reply_to_id=None, delivery_status=0):
    with sqlite3.connect(DB_PATH) as conn:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO dev_messages (user_telegram_id, user_role, username, user_name, sender_role, message, telegram_message_id, reply_to_id, delivery_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_telegram_id, user_role, username, user_name, sender_role, message, telegram_message_id, reply_to_id, delivery_status))
            msg_id = cursor.lastrowid
    return msg_id

def fetch_dev_messages(user_telegram_id, limit=20):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_telegram_id, user_role, username, user_name, sender_role, message, telegram_message_id, reply_to_id, delivery_status, timestamp
            FROM dev_messages
            WHERE user_telegram_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (user_telegram_id, limit))
        rows = cursor.fetchall()
    return [
        {
            'id': row[0],
            'user_telegram_id': row[1],
            'user_role': row[2],
            'username': row[3],
            'user_name': row[4],
            'sender_role': row[5],
            'message': row[6],
            'telegram_message_id': row[7],
            'reply_to_id': row[8],
            'delivery_status': row[9],
            'timestamp': row[10],
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

def set_drive_credentials(telegram_id, name, primary_email_address, email_address_1, email_address_2, email_address_3, credential_1, credential_2, credential_3, default_folder_id='root', parallel_uploads=1):
    with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO user_credentials (telegram_id, name, primary_email_address, email_address_1, email_address_2, email_address_3, credential_1, credential_2, credential_3, default_folder_id, parallel_uploads, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (telegram_id, name, primary_email_address, email_address_1, email_address_2, email_address_3, credential_1, credential_2, credential_3, default_folder_id, parallel_uploads))

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