from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .database import (
    is_admin, get_admins, get_whitelist, is_super_admin
)
import sqlite3
from .config import GROUP_CHAT_ID, TeamCloudverse_TOPIC_ID, DB_PATH
import uuid
from datetime import datetime
from .Utilities import paginate_list
from .Logger import get_total_users, get_queue_length
from .Logger import get_logger
logger = get_logger()
import os
import asyncio
TERMS_MD_PATH = os.path.join(os.path.dirname(__file__), 'TermsAndCondition.md')

# Track active live log update tasks per user
live_log_tasks = {}

import psutil
import time
import threading

# In-memory sets for online and uploading users
ONLINE_USERS = set()
UPLOADING_USERS = set()

def get_online_users():
    # Return the number of users considered online in the last 10 minutes
    return len(ONLINE_USERS)

def get_currently_uploading():
    # Return the number of users currently uploading
    return len(UPLOADING_USERS)

def mark_user_online(telegram_id):
    ONLINE_USERS.add(telegram_id)

def mark_user_offline(telegram_id):
    ONLINE_USERS.discard(telegram_id)

def mark_user_uploading(telegram_id):
    UPLOADING_USERS.add(telegram_id)

def mark_user_not_uploading(telegram_id):
    UPLOADING_USERS.discard(telegram_id)

from .Logger import get_bandwidth_today, get_current_bandwidth_usage

# Remove get_all_users and any references to 'users' and 'known_users' tables

def get_server_stats():
    # Server details
    bandwidth_today = get_bandwidth_today()  # in MB or GB
    live_bandwidth = get_current_bandwidth_usage()  # in Mbps or as available
    load = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory().percent
    uptime = time.time() - psutil.boot_time()
    return {
        "live_bandwidth": live_bandwidth,
        "bandwidth_today": bandwidth_today,
        "load": load,
        "cpu": cpu,
        "mem": mem,
        "uptime": uptime
    }

def get_bot_stats():
    # Bot details
    total_users = get_total_users()
    online_users = get_online_users()
    queue_length = get_queue_length()
    currently_uploading = get_currently_uploading()
    return {
        "total_users": total_users,
        "online_users": online_users,
        "queue_length": queue_length,
        "currently_uploading": currently_uploading
    }

async def handle_admin_control(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        q = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
        m = update.message if hasattr(update, 'message') and update.message else None
        if q and q.from_user:
            telegram_id = q.from_user.id
        elif m and m.from_user:
            telegram_id = m.from_user.id
        else:
            return
        if not is_admin(telegram_id):
            msg = "You don't have permission to access Admin Controls."
            if q:
                await q.edit_message_text(msg)
            elif m:
                await m.reply_text(msg)
            return
        buttons = [
            [InlineKeyboardButton("👑 Admin", callback_data="admin_list")],
            [InlineKeyboardButton("👥 Users", callback_data="users_list")],
            [InlineKeyboardButton("📊 Analytics", callback_data="analytics_report")],
            [InlineKeyboardButton("🖥 Performance", callback_data="performance_panel")],
            [InlineKeyboardButton("🗝️ Authenticate Session", callback_data="authenticate_session")],
            [InlineKeyboardButton("📝 Edit Terms & Condition", callback_data="edit_terms_condition")],
            [InlineKeyboardButton("✳️ Back", callback_data="back")]
        ]
        text = "👑 Admin Control Panel\n\nSelect an option:"
        markup = InlineKeyboardMarkup(buttons)
        if q:
            await q.edit_message_text(text, reply_markup=markup)
        elif m:
            await m.reply_text(text, reply_markup=markup)
        ctx.user_data["state"] = "ADMIN_CONTROL"
    except Exception as e:
        logger.error(f"Error in handle_admin_control for user: {locals().get('telegram_id', 'unknown')}: {e}")
        if 'q' in locals() and q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text("Failed to load admin control panel. Please try again later.")
        elif 'm' in locals() and m:
            await m.reply_text("Failed to load admin control panel. Please try again later.")

async def handle_admin_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays a paginated list of admin users.
    """
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.edit_message_text("You don't have permission to access Admin Controls.")
        return
    page = ctx.user_data.get("admin_page", 0)
    admins = get_admins()
    page_admins, total_pages, start_idx, end_idx = paginate_list(admins, page, DEFAULT_PAGE_SIZE)
    text = f"👑 Admin Users ({len(admins)} total)\n\n"
    for i, admin in enumerate(page_admins, start_idx + 1):
        text += f"{i}. ID: {admin['telegram_id']}\n"
    buttons = []
    if total_pages > 1:
        pagination = []
        if page > 0:
            pagination.append(InlineKeyboardButton("◀️ Prev", callback_data="admin_prev_page"))
        pagination.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            pagination.append(InlineKeyboardButton("Next ▶️", callback_data="admin_next_page"))
        if pagination:
            buttons.append(pagination)
    buttons.extend([
        [InlineKeyboardButton("♻️ Refresh", callback_data="admin_list")],
        [InlineKeyboardButton("✳️ Back", callback_data="admin_control")]
    ])
    markup = InlineKeyboardMarkup(buttons)
    await q.edit_message_text(text, reply_markup=markup)

async def handle_users_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays a paginated list of all users.
    """
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.edit_message_text("You don't have permission to access Admin Controls.")
        return
    page = ctx.user_data.get("users_page", 0)
    # Remove get_all_users and any references to 'users' and 'known_users' tables
    users = [] # Placeholder, as get_all_users is removed
    page_users, total_pages, start_idx, end_idx = paginate_list(users, page, DEFAULT_PAGE_SIZE)
    text = f"👥 All Users ({len(users)} total)\n\n"
    for i, user in enumerate(page_users, start_idx + 1):
        text += f"{i}. ID: {user['telegram_id']} | Email: {user['account_email']}\n"
    buttons = []
    if total_pages > 1:
        pagination = []
        if page > 0:
            pagination.append(InlineKeyboardButton("◀️ Prev", callback_data="users_prev_page"))
        pagination.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            pagination.append(InlineKeyboardButton("Next ▶️", callback_data="users_next_page"))
        if pagination:
            buttons.append(pagination)
    buttons.extend([
        [InlineKeyboardButton("♻️ Refresh", callback_data="users_list")],
        [InlineKeyboardButton("✳️ Back", callback_data="admin_control")]
    ])
    markup = InlineKeyboardMarkup(buttons)
    await q.edit_message_text(text, reply_markup=markup)

async def handle_admin_pagination(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.edit_message_text("You don't have permission to access Admin Controls.")
        return
    data = q.data
    current_page = ctx.user_data.get("admin_page", 0)
    if data == "admin_prev_page":
        ctx.user_data["admin_page"] = max(0, current_page - 1)
    elif data == "admin_next_page":
        ctx.user_data["admin_page"] = current_page + 1
    await handle_admin_list(update, ctx)

async def handle_users_pagination(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.edit_message_text("You don't have permission to access Admin Controls.")
        return
    data = q.data
    current_page = ctx.user_data.get("users_page", 0)
    if data == "users_prev_page":
        ctx.user_data["users_page"] = max(0, current_page - 1)
    elif data == "users_next_page":
        ctx.user_data["users_page"] = current_page + 1
    await handle_users_list(update, ctx) 

async def handle_performance_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.edit_message_text("You don't have permission to access Admin Controls.")
        return
    if ctx.user_data is None:
        ctx.user_data = {}
    ctx.user_data["state"] = "PERFORMANCE_PANEL"
    ctx.user_data["performance_panel_active"] = True
    async def update_panel():
        if ctx.user_data is None:
            ctx.user_data = {}
        while ctx.user_data.get("performance_panel_active", False):
            server = get_server_stats()
            bot = get_bot_stats()
            text = (
                "🖥 <b>Performance Panel</b>\n\n"
                "<b>Server Details</b>\n"
                f"Live bandwidth: {server['live_bandwidth']} Mbps\n"
                f"Bandwidth today: {server['bandwidth_today']} MB\n"
                f"Current Load: {server['load']:.2f}\n"
                f"CPU Usage: {server['cpu']}%\n"
                f"Memory Usage: {server['mem']}%\n"
                f"Uptime: {int(server['uptime']//3600)}h {int((server['uptime']%3600)//60)}m\n\n"
                "<b>CloudVerse Bot Details</b>\n"
                f"Users online: {bot['online_users']}\n"
                f"Total users: {bot['total_users']}\n"
                f"Queue Length: {bot['queue_length']}\n"
                f"Currently Uploading: {bot['currently_uploading']}\n"
            )
            buttons = [[InlineKeyboardButton("✳️ Back", callback_data="admin_control")]]
            try:
                await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
            except Exception:
                pass
            await asyncio.sleep(2)
    # Start the update loop
    asyncio.create_task(update_panel())

async def handle_performance_panel_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    ctx.user_data["performance_panel_active"] = False
    await handle_admin_control(update, ctx)

async def handle_live_terminal_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.from_user:
        logger.error("handle_live_terminal_logs called without callback_query or user context", extra={"operation": "handle_live_terminal_logs"})
        return
    user_id = q.from_user.id
    chat_id = q.message.chat_id
    message_id = q.message.message_id
    logger.info(f"User {user_id} requested live terminal logs. Chat: {chat_id}, Message: {message_id}", extra={"user_id": user_id, "operation": "handle_live_terminal_logs"})

    # Stop any previous live log task for this user
    task_key = (chat_id, message_id)
    if task_key in live_log_tasks:
        live_log_tasks[task_key].cancel()

    # Send initial dashboard with Back button
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = [[InlineKeyboardButton("Back", callback_data="live_terminal_logs_back")]]
    msg = await q.edit_message_text(
        f"</> Live Terminal Logs\n\n<pre>{get_total_users()}</pre>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    # Start periodic updater
    async def updater():
        try:
            while True:
                await asyncio.sleep(2)
                try:
                    await ctx.bot.edit_message_text(
                        f"</> Live Terminal Logs\n\n<pre>{get_total_users()}</pre>",
                        chat_id=chat_id,
                        message_id=message_id,
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                except Exception:
                    break  # Message deleted or can't edit
        except asyncio.CancelledError:
            pass
    task = asyncio.create_task(updater())
    live_log_tasks[task_key] = task

async def handle_live_terminal_logs_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.from_user:
        return
    chat_id = q.message.chat_id
    message_id = q.message.message_id
    task_key = (chat_id, message_id)
    # Cancel the updater task
    if task_key in live_log_tasks:
        live_log_tasks[task_key].cancel()
        del live_log_tasks[task_key]
    # Return to previous menu (Admin Control)
    await handle_admin_control(update, ctx)

async def handle_edit_terms_condition(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.from_user:
        return
    from .database import is_admin
    if not is_admin(q.from_user.id):
        await q.edit_message_text("You don't have permission to edit Terms & Condition.")
        return
    if ctx.user_data is None:
        ctx.user_data = {}
    ctx.user_data['awaiting_terms_update'] = True
    await q.edit_message_text(
        "📝 *Edit Terms & Condition*\n\nPlease send the new Terms & Condition text. All formatting (bold, italic, etc.) will be preserved.\n\n*Note:* The last updated tag will be set to the current date.",
        parse_mode='Markdown'
    )

async def handle_terms_update_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    if not ctx.user_data.get('awaiting_terms_update'):
        return
    if update.message and update.message.from_user:
        from .database import is_admin
        telegram_id = update.message.from_user.id
        if not is_admin(telegram_id):
            await update.message.reply_text("You don't have permission to edit Terms & Condition.")
            ctx.user_data['awaiting_terms_update'] = False
            return
        new_terms = update.message.text
        from datetime import datetime
        last_updated = datetime.now().strftime('%d %B, %Y')
        import re
        # Insert/update last updated tag at the top
        if re.search(r'Last Updated.*', new_terms):
            new_terms = re.sub(r'Last Updated.*', f'Last Updated : {last_updated}', new_terms, count=1)
        else:
            new_terms = f'__Last Updated : {last_updated}__\n\n' + new_terms
        # Save to TermsAndCondition.md in project root
        with open(TERMS_MD_PATH, 'w', encoding='utf-8') as f:
            f.write(new_terms)
        await update.message.reply_text("✅ Terms & Condition updated successfully.")
        ctx.user_data['awaiting_terms_update'] = False 

async def handle_authenticate_session(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.edit_message_text("You don't have permission to authenticate a session.")
        return
    if ctx.user_data is None:
        ctx.user_data = {}
    ctx.user_data['awaiting_telethon_phone'] = True
    await q.edit_message_text(
        "🗝️ *Authenticate Telethon Session*\n\nPlease enter your phone number (with country code, e.g. +1234567890):",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✳️ Cancel", callback_data="cancel_telethon_auth")]])
    ) 

async def handle_telethon_auth_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from .config import TELETHON_API_ID, TELETHON_API_HASH
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    import os

    if ctx.user_data is None:
        ctx.user_data = {}
    text = update.message.text if update.message else None
    telegram_id = update.message.from_user.id if update.message and update.message.from_user else None
    if not telegram_id or not is_admin(telegram_id):
        return

    # Cancel flow
    if text and text.strip().lower() == 'cancel':
        ctx.user_data.pop('awaiting_telethon_phone', None)
        ctx.user_data.pop('awaiting_telethon_code', None)
        ctx.user_data.pop('awaiting_telethon_2fa', None)
        ctx.user_data.pop('telethon_auth', None)
        await update.message.reply_text('❌ Telethon authentication cancelled.')
        return

    # Step 1: Phone number
    if ctx.user_data.get('awaiting_telethon_phone'):
        phone = text.strip()
        session_name = f"telethon_{telegram_id}"
        client = TelegramClient(session_name, int(TELETHON_API_ID), TELETHON_API_HASH)
        await client.connect()
        try:
            sent = await client.send_code_request(phone)
            ctx.user_data['telethon_auth'] = {
                'phone': phone,
                'session_name': session_name,
                'sent': sent.phone_code_hash
            }
            ctx.user_data['awaiting_telethon_phone'] = False
            ctx.user_data['awaiting_telethon_code'] = True
            await update.message.reply_text(
                '📲 Please enter the code you received from Telegram:',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✳️ Cancel', callback_data='cancel_telethon_auth')]])
            )
        except Exception as e:
            await update.message.reply_text(f'❌ Failed to send code: {e}')
            await client.disconnect()
        return

    # Step 2: Code
    if ctx.user_data.get('awaiting_telethon_code'):
        code = text.strip()
        auth = ctx.user_data.get('telethon_auth', {})
        phone = auth.get('phone')
        session_name = auth.get('session_name')
        phone_code_hash = auth.get('sent')
        client = TelegramClient(session_name, int(TELETHON_API_ID), TELETHON_API_HASH)
        await client.connect()
        try:
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                ctx.user_data['awaiting_telethon_code'] = False
                ctx.user_data.pop('telethon_auth', None)
                await update.message.reply_text('✅ Telethon session authenticated and saved!')
                await client.disconnect()
                return
            except SessionPasswordNeededError:
                ctx.user_data['awaiting_telethon_code'] = False
                ctx.user_data['awaiting_telethon_2fa'] = True
                ctx.user_data['telethon_auth'] = {
                    'phone': phone,
                    'session_name': session_name,
                    'phone_code_hash': phone_code_hash,
                    'code': code
                }
                await update.message.reply_text(
                    '🔒 2FA is enabled. Please enter your 2FA password:',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✳️ Cancel', callback_data='cancel_telethon_auth')]])
                )
                await client.disconnect()
                return
        except Exception as e:
            await update.message.reply_text(f'❌ Failed to sign in: {e}')
            await client.disconnect()
        return

    # Step 3: 2FA password
    if ctx.user_data.get('awaiting_telethon_2fa'):
        password = text.strip()
        auth = ctx.user_data.get('telethon_auth', {})
        phone = auth.get('phone')
        session_name = auth.get('session_name')
        phone_code_hash = auth.get('phone_code_hash')
        code = auth.get('code')
        client = TelegramClient(session_name, int(TELETHON_API_ID), TELETHON_API_HASH)
        await client.connect()
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash, password=password)
            ctx.user_data['awaiting_telethon_2fa'] = False
            ctx.user_data.pop('telethon_auth', None)
            await update.message.reply_text('✅ Telethon session authenticated and saved!')
        except Exception as e:
            await update.message.reply_text(f'❌ Failed 2FA authentication: {e}')
        await client.disconnect()
        return 