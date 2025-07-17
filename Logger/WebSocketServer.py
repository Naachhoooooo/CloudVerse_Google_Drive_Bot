import asyncio
import websockets
import json
import os
import time
import threading
import psutil
import sqlite3
from datetime import datetime, timedelta
import logging
import sys
import signal
import pathlib
import importlib.util
import socket

# Add the Bot directory to the path for imports
bot_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Bot')
sys.path.append(bot_dir)
# NOTE: Run this script as a module from the project root, e.g.,
# python3 -m Logger.WebSocketServer
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from Bot.Logger import get_logger
logger = get_logger()

# Add the Logger directory to the path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from WebConfig import config
except ImportError:
    # Fallback configuration if import fails
    class Config:
        WEBSOCKET = {'HOST': 'localhost', 'PORT': 8765}
        PATHS = {'DATABASE': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Cloudverse.db')}
        
        @classmethod
        def get_websocket_url(cls):
            return f"ws://{cls.WEBSOCKET['HOST']}:{cls.WEBSOCKET['PORT']}"
        
        @classmethod
        def print_config(cls):
            print("Using fallback configuration")
            print(f"WebSocket: {cls.get_websocket_url()}")
            print(f"Database: {cls.PATHS['DATABASE']}")
    
    config = Config()

# Global variables for real-time data
metrics = {
    'cpu': 0.0,
    'bandwidth': 0.0,
    'memory': 0.0,
    'uptime': 0,
    'users': 0,
    'uploads_today': 0,
    'total_storage_used': 0.0
}

logs = []
users = []
clients = set()
process_start_time = time.time()

# Database path from config
DB_PATH = config.PATHS['DATABASE']

def get_system_metrics():
    """Get real system metrics"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        uptime = int(time.time() - process_start_time)
        
        return {
            'cpu': round(cpu_percent, 1),
            'memory': round(memory_percent, 1),
            'uptime': uptime
        }
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return {'cpu': 0.0, 'memory': 0.0, 'uptime': 0}

def get_user_data():
    """Get real user data from new schema: admins and whitelisted_users"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        users_list = []
        # Fetch admins
        cursor.execute("SELECT telegram_id, username, name FROM admins")
        for row in cursor.fetchall():
            telegram_id, username, name = row
            users_list.append({
                'name': name if name else (username or f"User {telegram_id}"),
                'username': username or '',
                'telegram_id': str(telegram_id),
                'parallel_uploads': 1,  # Default, adjust if needed
                'is_admin': True,
                'status': 'Online'
            })
        # Fetch whitelisted users
        cursor.execute("SELECT telegram_id, username, name FROM whitelisted_users")
        for row in cursor.fetchall():
            telegram_id, username, name = row
            # Avoid duplicate admins
            if not any(u['telegram_id'] == str(telegram_id) for u in users_list):
                users_list.append({
                    'name': name if name else (username or f"User {telegram_id}"),
                    'username': username or '',
                    'telegram_id': str(telegram_id),
                    'parallel_uploads': 1,  # Default, adjust if needed
                    'is_admin': False,
                    'status': 'Online'
                })
        conn.close()
        return users_list
    except Exception as e:
        logger.error(f"Error getting user data: {e}")
        return []

def get_recent_logs():
    """Get recent logs from bot.log"""
    try:
        log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bot.log')
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                return lines[-20:]  # Last 20 lines
        return []
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return []

def get_upload_stats():
    """Get upload statistics from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get uploads today
        today = datetime.now().date().isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM uploads 
            WHERE DATE(upload_time) = ?
        """, (today,))
        uploads_today = cursor.fetchone()[0] or 0
        
        # Get total storage used (placeholder - implement based on your storage tracking)
        total_storage_used = 0.0
        
        conn.close()
        return {
            'uploads_today': uploads_today,
            'total_storage_used': total_storage_used
        }
    except Exception as e:
        logger.error(f"Error getting upload stats: {e}")
        return {'uploads_today': 0, 'total_storage_used': 0.0}

def calculate_bandwidth():
    """Calculate bandwidth usage (placeholder - implement based on your needs)"""
    # This is a placeholder - implement based on your actual bandwidth tracking
    return 0.0

def get_all_uploads():
    """Fetch all uploads from the uploads table and return as a list of dicts."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, telegram_id, file_id, file_name, file_size, file_type, upload_time, status, error_message FROM uploads ORDER BY upload_time DESC")
        uploads = [
            {
                'id': row[0],
                'telegram_id': row[1],
                'file_id': row[2],
                'file_name': row[3],
                'file_size': row[4],
                'file_type': row[5],
                'upload_time': row[6],
                'status': row[7],
                'error_message': row[8],
            } for row in cursor.fetchall()
        ]
        conn.close()
        return uploads
    except Exception as e:
        logger.error(f"Error fetching uploads: {e}")
        return []

async def send_periodic_updates():
    """Send periodic updates to all connected clients"""
    while True:
        try:
            if clients:
                # Update real metrics
                system_metrics = get_system_metrics()
                metrics.update(system_metrics)
                metrics['bandwidth'] = calculate_bandwidth()
                metrics['users'] = len(get_user_data())
                
                # Get additional stats
                upload_stats = get_upload_stats()
                metrics.update(upload_stats)
                
                # Send metrics
                msg = json.dumps({'type': 'dashboard', 'metrics': metrics})
                await asyncio.gather(*[c.send(msg) for c in clients], return_exceptions=True)
                
                # Send recent logs
                recent_logs = get_recent_logs()
                for log in recent_logs[-5:]:  # Send last 5 logs
                    if log.strip():
                        msg = json.dumps({'type': 'logs', 'log': log.strip()})
                        await asyncio.gather(*[c.send(msg) for c in clients], return_exceptions=True)
                
                # Send users
                users_data = get_user_data()
                msg = json.dumps({'type': 'users', 'users': users_data})
                await asyncio.gather(*[c.send(msg) for c in clients], return_exceptions=True)
                
                # Send uploads
                uploads_list = get_all_uploads()
                msg = json.dumps({'type': 'uploads', 'uploads': uploads_list})
                await asyncio.gather(*[c.send(msg) for c in clients], return_exceptions=True)
                
        except Exception as e:
            logger.error(f"Error in periodic updates: {e}")
        
        await asyncio.sleep(2)

# For websockets >= 12.0, handler should only take websocket
async def handler(websocket):
    clients.add(websocket)
    logger.info(f"Client connected. Total clients: {len(clients)}")
    try:
        # Send initial data
        system_metrics = get_system_metrics()
        metrics.update(system_metrics)
        metrics['bandwidth'] = calculate_bandwidth()
        metrics['users'] = len(get_user_data())
        upload_stats = get_upload_stats()
        metrics.update(upload_stats)
        await websocket.send(json.dumps({'type': 'dashboard', 'metrics': metrics}))
        await websocket.send(json.dumps({'type': 'users', 'users': get_user_data()}))
        recent_logs = get_recent_logs()
        for log in recent_logs[-10:]:
            if log.strip():
                await websocket.send(json.dumps({'type': 'logs', 'log': log.strip()}))
        await websocket.send(json.dumps({'type': 'uploads', 'uploads': get_all_uploads()}))
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get('action') == 'restart_bot':
                    logger.info('Restart bot requested')
                    await websocket.send(json.dumps({'type': 'status', 'message': 'Restarting entire system...'}))
                    os.kill(os.getppid(), signal.SIGUSR1)
                elif data.get('action') == 'shutdown_bot':
                    logger.info('Shutdown bot requested')
                    await websocket.send(json.dumps({'type': 'status', 'message': 'Shutting down entire system...'}))
                    os.kill(os.getppid(), signal.SIGTERM)
                elif data.get('action') == 'limit_bandwidth':
                    user_id = data.get('user_id')
                    logger.info(f'Limit bandwidth for user {user_id}')
                    await websocket.send(json.dumps({'type': 'status', 'message': f'Bandwidth limit set for user {user_id}'}))
                elif data.get('action') == 'tag_user':
                    user_id = data.get('user_id')
                    logger.info(f'Tag user {user_id}')
                    await websocket.send(json.dumps({'type': 'status', 'message': f'User {user_id} tagged'}))
                elif data.get('action') == 'get_user_details':
                    user_id = data.get('user_id')
                    user_details = get_user_details(user_id)
                    await websocket.send(json.dumps({'type': 'user_details', 'user': user_details}))
                elif data.get('action') == 'get_uploads':
                    uploads_list = get_all_uploads()
                    await websocket.send(json.dumps({'type': 'uploads', 'uploads': uploads_list}))
                elif data.get('action') == 'ban_user':
                    user_id = data.get('user_id')
                    duration = data.get('duration')
                    # Prevent banning admins
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("SELECT telegram_id FROM admins WHERE telegram_id = ?", (user_id,))
                    if cursor.fetchone():
                        await websocket.send(json.dumps({'type': 'status', 'message': 'Cannot ban an admin.'}))
                        conn.close()
                        continue
                    # Fetch from whitelist
                    cursor.execute("SELECT telegram_id, username, name, last_updated FROM whitelisted_users WHERE telegram_id = ?", (user_id,))
                    user = cursor.fetchone()
                    if not user:
                        await websocket.send(json.dumps({'type': 'status', 'message': 'User not found in whitelist.'}))
                        conn.close()
                        continue
                    # Calculate restriction fields
                    now = datetime.now()
                    if duration == 'permanent':
                        restriction_type = 'Permanent'
                        restriction_countdown = None
                    else:
                        restriction_type = 'Temporary'
                        restriction_countdown = (now + timedelta(hours=int(duration))).isoformat()
                    # Insert into blacklist
                    cursor.execute("""
                        INSERT OR REPLACE INTO blacklisted_users (telegram_id, username, name, restriction_type, restriction_countdown, restricted_at, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user[0], user[1], user[2], restriction_type, restriction_countdown, now.isoformat(), now.isoformat()
                    ))
                    # Remove from whitelist
                    cursor.execute("DELETE FROM whitelisted_users WHERE telegram_id = ?", (user_id,))
                    conn.commit()
                    conn.close()
                    # TODO: Send ban message to user via bot integration
                    logger.info(f"User {user_id} banned: {restriction_type} {restriction_countdown or ''}")
                    await websocket.send(json.dumps({'type': 'status', 'message': f'User {user_id} banned: {restriction_type}'}))
                    # Optionally, trigger user data refresh for all clients
                    users_data = get_user_data()
                    msg = json.dumps({'type': 'users', 'users': users_data})
                    await asyncio.gather(*[c.send(msg) for c in clients], return_exceptions=True)
                elif data.get('action') == 'mark_for_ban':
                    user_id = data.get('user_id')
                    # Prevent marking admins
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("SELECT telegram_id, username, name FROM admins WHERE telegram_id = ?", (user_id,))
                    admin_row = cursor.fetchone()
                    if admin_row:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Cannot mark an admin for ban.'
                        }))
                        continue
                    # Fetch user info from whitelist
                    cursor.execute("SELECT telegram_id, username, name FROM whitelisted_users WHERE telegram_id = ?", (user_id,))
                    user_row = cursor.fetchone()
                    if not user_row:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'User not found in whitelist.'
                        }))
                        continue
                    # Forward message to TeamCloudverse group (placeholder: implement bot API call)
                    # Save message/thread ID for future updates (store in DB or in-memory as needed)
                    # Example: send_group_ban_message(user_row)
                    logger.info(f"Marked user {user_id} for ban. Forwarded to TeamCloudverse group.")
                    await websocket.send(json.dumps({
                        'type': 'mark_for_ban_success',
                        'user_id': user_id
                    }))
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
    finally:
        clients.remove(websocket)
        logger.info(f"Client disconnected. Total clients: {len(clients)}")

def get_user_details(user_id):
    """Get detailed user information"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT telegram_id, username, first_name, last_name, parallel_uploads, 
                   is_admin, is_whitelisted, created_at, last_activity
            FROM users 
            WHERE telegram_id = ?
        """, (user_id,))
        
        user_data = cursor.fetchone()
        if user_data:
            telegram_id, username, first_name, last_name, parallel_uploads, is_admin, is_whitelisted, created_at, last_activity = user_data
            return {
                'telegram_id': str(telegram_id),
                'username': username or '',
                'name': f"{first_name} {last_name}".strip() if first_name or last_name else username or f"User {telegram_id}",
                'parallel_uploads': parallel_uploads or 1,
                'is_admin': bool(is_admin),
                'is_whitelisted': bool(is_whitelisted),
                'created_at': created_at,
                'last_activity': last_activity
            }
        
        conn.close()
        return None
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        return None

# --- Real-time upload progress bridge ---
progress_clients = set()
async def progress_ws_handler(websocket):
    progress_clients.add(websocket)
    try:
        async for message in websocket:
            # Forward progress update to all dashboard clients
            for c in clients:
                await c.send(message)
    finally:
        progress_clients.remove(websocket)

def start_progress_ws_server():
    # Start a local WebSocket server for the bot to send progress updates
    return websockets.serve(progress_ws_handler, 'localhost', 8770)

# --- Real-time log tailing ---
async def tail_log_file(log_path, callback):
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                await callback(line.rstrip())
            else:
                await asyncio.sleep(0.2)

async def log_tail_broadcast():
    log_path = os.path.join(pathlib.Path(__file__).parent.parent, 'bot.log')
    async def push_log(line):
        msg = json.dumps({'type': 'logs', 'log': line})
        await asyncio.gather(*[c.send(msg) for c in clients], return_exceptions=True)
    await tail_log_file(log_path, push_log)

def check_port_in_use(port):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

async def main():
    """Main WebSocket server function"""
    try:
        # Check if port is already in use
        port = config.WEBSOCKET['PORT']
        if check_port_in_use(port):
            logger.error(f"Port {port} is already in use. Killing existing process.")
            # Find and kill the process using the port
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    for conn in proc.connections(kind='inet'):
                        if conn.laddr.port == port:
                            logger.info(f"Killing process {proc.pid} ({proc.name()}) using port {port}")
                            proc.kill()
                            logger.info(f"Process {proc.pid} killed successfully.")
                except Exception as e:
                    logger.error(f"Error killing process on port {port}: {e}")
            # Wait a moment for port to be released
            time.sleep(2)
        server = await websockets.serve(
            handler, 
            config.WEBSOCKET['HOST'], 
            config.WEBSOCKET['PORT']
        )
        logger.info(f"WebSocket server started on {config.get_websocket_url()}")
        logger.info('Waiting for connections...')
        # Start progress WebSocket server
        await start_progress_ws_server()
        # Start log tailing
        asyncio.create_task(log_tail_broadcast())
        # Start periodic updates
        await send_periodic_updates()
        
    except Exception as e:
        logger.error(f"Error starting WebSocket server: {e}")
        logger.error("Unrecoverable error. Killing WebSocket server process.")
        os.kill(os.getpid(), signal.SIGTERM)

# Only start the WebSocket server if this is the main process
if __name__ == '__main__':
    config.print_config()
    asyncio.run(main()) 