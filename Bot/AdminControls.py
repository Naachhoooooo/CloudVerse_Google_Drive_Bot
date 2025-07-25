from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .database import (
    get_whitelisted_users, is_admin, get_admins, get_whitelist, is_super_admin, get_all_users_for_analytics
)
import sqlite3
from .config import GROUP_CHAT_ID, TeamCloudverse_TOPIC_ID, DB_PATH
import uuid
from datetime import datetime
from .Utilities import pagination, handle_errors
import os
import asyncio
TERMS_MD_PATH = os.path.join(os.path.dirname(__file__), 'TermsAndCondition.md')
from .Utilities import admin_required
from .database import get_admins_paginated, get_all_users_for_analytics_paginated
from .UserState import UserStateEnum

# Message constants (user-facing)
NO_PERMISSION_ADMIN_CONTROLS_MSG = "You don't have permission to access Admin Controls."
ADMIN_CONTROL_PANEL_TITLE = "👑 Admin Control Panel"
FAILED_TO_LOAD_ADMIN_CONTROL_PANEL_MSG = "Failed to load admin control panel. Please try again later."
ADMIN_USERS_TITLE = "👑 Admin Users ({total} total)\n\n"
ALL_USERS_TITLE = "👥 All Users ({total} total)\n\n"
REFRESH_BUTTON = "♻️ Refresh"
BACK_BUTTON = "✳️ Back"
PREV_PAGE_BUTTON = "◀️ Prev"
NEXT_PAGE_BUTTON = "Next ▶️"
DEFAULT_PAGE_SIZE = 10

import psutil
import time
import threading
from .Utilities import get_server_stats, get_bot_stats

import os
ALLOWED_DOMAIN_PATH = os.path.join(os.path.dirname(__file__), 'AllowedDomain.md')

@admin_required
@handle_errors
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
        buttons = [
            [InlineKeyboardButton("👑 Admin", callback_data="admin_list")],
            [InlineKeyboardButton("👥 Users", callback_data="users_list")],
            [InlineKeyboardButton("📊 Analytics", callback_data="analytics_report")],
            [InlineKeyboardButton("🖥 Performance", callback_data="performance_panel")],
            [InlineKeyboardButton("🗑️ Delete Records", callback_data="delete_records")],
            [InlineKeyboardButton("🟢 Modify Allowed Link Domains", callback_data="modify_allowed_domain")],
            [InlineKeyboardButton("🗝️ Authenticate Session", callback_data="authenticate_session")],
            [InlineKeyboardButton("📝 Edit Terms of Use", callback_data="edit_terms_condition")],
            [InlineKeyboardButton("✳️ Back", callback_data="back")]
        ]
        text = ADMIN_CONTROL_PANEL_TITLE
        markup = InlineKeyboardMarkup(buttons)
        if q:
            await q.edit_message_text(text, reply_markup=markup)
        elif m:
            await m.reply_text(text, reply_markup=markup)
        ctx.user_data["state"] = UserStateEnum.ADMIN_CONTROL
    except Exception as e:
        if 'q' in locals() and q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text(FAILED_TO_LOAD_ADMIN_CONTROL_PANEL_MSG)
        elif 'm' in locals() and m:
            await m.reply_text(FAILED_TO_LOAD_ADMIN_CONTROL_PANEL_MSG)

@admin_required
@handle_errors
async def handle_admin_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    data = getattr(q, 'data', None)
    current_page = ctx.user_data.get("admin_page", 0)
    if data == "admin_prev_page":
        ctx.user_data["admin_page"] = max(0, current_page - 1)
    elif data == "admin_next_page":
        ctx.user_data["admin_page"] = current_page + 1
    page = ctx.user_data.get("admin_page", 0)
    from .database import get_admins
    from .Utilities import pagination
    all_admins = get_admins()
    admins, total_pages, _, _, pagination_buttons = pagination(all_admins, page, DEFAULT_PAGE_SIZE, "admin_prev_page", "admin_next_page")
    total_admins = len(all_admins)
    text = ADMIN_USERS_TITLE.format(total=total_admins)
    for i, admin in enumerate(admins, page * DEFAULT_PAGE_SIZE + 1):
        text += f"{i}. ID: {admin['telegram_id']}\n"
    buttons = []
    if pagination_buttons:
        buttons.append(pagination_buttons)
    buttons.extend([
        [InlineKeyboardButton(REFRESH_BUTTON, callback_data="admin_list")],
        [InlineKeyboardButton(BACK_BUTTON, callback_data="admin_control")]
    ])
    markup = InlineKeyboardMarkup(buttons)
    await q.edit_message_text(text, reply_markup=markup)

@admin_required
@handle_errors
async def handle_users_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    data = getattr(q, 'data', None)
    current_page = ctx.user_data.get("users_page", 0)
    if data == "users_prev_page":
        ctx.user_data["users_page"] = max(0, current_page - 1)
    elif data == "users_next_page":
        ctx.user_data["users_page"] = current_page + 1
    page = ctx.user_data.get("users_page", 0)
    from .database import get_all_users_for_analytics
    from .Utilities import pagination
    all_users = get_all_users_for_analytics()
    users, total_pages, _, _, pagination_buttons = pagination(all_users, page, DEFAULT_PAGE_SIZE, "users_prev_page", "users_next_page")
    total_users = len(all_users)
    text = ALL_USERS_TITLE.format(total=total_users)
    for i, user in enumerate(users, page * DEFAULT_PAGE_SIZE + 1):
        text += f"{i}. ID: {user[0]} | Username: {user[1]} | Name: {user[2]}\n"
    buttons = []
    if pagination_buttons:
        buttons.append(pagination_buttons)
    buttons.extend([
        [InlineKeyboardButton(REFRESH_BUTTON, callback_data="users_list")],
        [InlineKeyboardButton(BACK_BUTTON, callback_data="admin_control")]
    ])
    markup = InlineKeyboardMarkup(buttons)
    await q.edit_message_text(text, reply_markup=markup)

@handle_errors
async def handle_performance_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.edit_message_text(NO_PERMISSION_ADMIN_CONTROLS_MSG)
        return
    data = getattr(q, 'data', None)
    if data == "performance_panel_back":
        ctx.user_data["performance_panel_active"] = False
        await handle_admin_control(update, ctx)
        return
    ctx.user_data["state"] = UserStateEnum.PERFORMANCE_PANEL
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
                f"Total users: {bot['total_users']}\n"
                f"Queue Length: {bot['queue_length']}\n"
            )
            buttons = [[InlineKeyboardButton("✳️ Back", callback_data="performance_panel_back")]]
            try:
                await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
            except Exception:
                pass
            await asyncio.sleep(2)
    # Start the update loop
    asyncio.create_task(update_panel())

@handle_errors
async def handle_update_terms_and_condition(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    m = getattr(update, 'message', None)
    if q:
        await q.answer()
        if q.data == "edit_terms_condition":
            try:
                with open(TERMS_MD_PATH, 'r', encoding='utf-8') as f:
                    terms_text = f.read()
            except Exception:
                terms_text = "Failed to load terms and conditions."
            buttons = [[InlineKeyboardButton("Update Terms", callback_data="update_terms_message")], [InlineKeyboardButton(BACK_BUTTON, callback_data="admin_control")]]
            await q.edit_message_text(f"<b>Terms and Conditions</b>\n\n<pre>{terms_text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
            return
        elif q.data == "update_terms_message":
            await q.edit_message_text("Send the new Terms and Conditions as a message.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BACK_BUTTON, callback_data="edit_terms_condition")]]))
            ctx.user_data["awaiting_terms_update"] = True
            return
        elif q.data == "admin_control":
            ctx.user_data.pop("awaiting_terms_update", None)
            await handle_admin_control(update, ctx)
            return
    if m and ctx.user_data.get("awaiting_terms_update"):
        new_terms = m.text
        try:
            with open(TERMS_MD_PATH, 'w', encoding='utf-8') as f:
                f.write(new_terms)
            await m.reply_text("Terms and Conditions updated successfully.")
        except Exception as e:
            await m.reply_text(f"Failed to update terms: {e}")
        ctx.user_data.pop("awaiting_terms_update", None)
        return

@admin_required
@handle_errors
async def handle_authenticate_session(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.from_user:
        return
    if not is_admin(q.from_user.id):
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

@admin_required
@handle_errors
async def handle_telethon_auth_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from .config import TELETHON_API_ID, TELETHON_API_HASH
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    import os

    if ctx.user_data is None:
        ctx.user_data = {}
    text = update.message.text if update.message and update.message.text is not None else None
    telegram_id = update.message.from_user.id if update.message and update.message.from_user else None
    if not telegram_id or not is_admin(telegram_id):
        return

    if text and isinstance(text, str) and text.strip().lower() == 'cancel':
        ctx.user_data.pop('awaiting_telethon_phone', None)
        ctx.user_data.pop('awaiting_telethon_code', None)
        ctx.user_data.pop('awaiting_telethon_2fa', None)
        ctx.user_data.pop('telethon_auth', None)
        await update.message.reply_text('❌ Telethon authentication cancelled.')
        return

    # Step 1: Phone number
    if ctx.user_data.get('awaiting_telethon_phone'):
        if not text or not isinstance(text, str):
            await update.message.reply_text('❌ Invalid phone number.')
            return
        phone = text.strip()
        session_name = f"telethon_{telegram_id}"
        if TELETHON_API_ID is None or TELETHON_API_HASH is None:
            await update.message.reply_text('❌ Telethon API credentials are not set.')
            return
        client = TelegramClient(session_name, int(TELETHON_API_ID), str(TELETHON_API_HASH))
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
            client.disconnect()
        return

    # Step 2: Code
    if ctx.user_data.get('awaiting_telethon_code'):
        if not text or not isinstance(text, str):
            await update.message.reply_text('❌ Invalid code.')
            return
        code = text.strip()
        auth = ctx.user_data.get('telethon_auth', {})
        phone = auth.get('phone')
        session_name = auth.get('session_name')
        phone_code_hash = auth.get('sent')
        if TELETHON_API_ID is None or TELETHON_API_HASH is None:
            await update.message.reply_text('❌ Telethon API credentials are not set.')
            return
        client = TelegramClient(session_name, int(TELETHON_API_ID), str(TELETHON_API_HASH))
        await client.connect()
        try:
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                ctx.user_data['awaiting_telethon_code'] = False
                ctx.user_data.pop('telethon_auth', None)
                await update.message.reply_text('✅ Telethon session authenticated and saved!')
                client.disconnect()
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
                client.disconnect()
                return
        except Exception as e:
            await update.message.reply_text(f'❌ Failed to sign in: {e}')
            client.disconnect()
        return

    # Step 3: 2FA password
    if ctx.user_data.get('awaiting_telethon_2fa'):
        if not text or not isinstance(text, str):
            await update.message.reply_text('❌ Invalid 2FA password.')
            return
        password = text.strip()
        auth = ctx.user_data.get('telethon_auth', {})
        phone = auth.get('phone')
        session_name = auth.get('session_name')
        phone_code_hash = auth.get('phone_code_hash')
        code = auth.get('code')
        if TELETHON_API_ID is None or TELETHON_API_HASH is None:
            await update.message.reply_text('❌ Telethon API credentials are not set.')
            return
        client = TelegramClient(session_name, int(TELETHON_API_ID), str(TELETHON_API_HASH))
        await client.connect()
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash, password=password)
            ctx.user_data['awaiting_telethon_2fa'] = False
            ctx.user_data.pop('telethon_auth', None)
            await update.message.reply_text('✅ Telethon session authenticated and saved!')
        except Exception as e:
            await update.message.reply_text(f'❌ Failed 2FA authentication: {e}')
        client.disconnect()
        return 

@handle_errors
async def handle_delete_records(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    m = getattr(update, 'message', None)
    data = q.data if q else None
    page = ctx.user_data.get("delete_records_page", 0)
    if data == "delete_records_prev_page":
        ctx.user_data["delete_records_page"] = max(0, page - 1)
        page = ctx.user_data["delete_records_page"]
    elif data == "delete_records_next_page":
        ctx.user_data["delete_records_page"] = page + 1
        page = ctx.user_data["delete_records_page"]
    from .database import get_whitelisted_users, is_super_admin
    users, total_users = get_whitelisted_users(page, DEFAULT_PAGE_SIZE)
    from .config import SUPER_ADMIN_ID
    users = [u for u in users if str(u[0]) != str(SUPER_ADMIN_ID)]
    user_display = []
    for u in users:
        if u[1]:
            label = f"{u[2]} (@{u[1]})"
        else:
            label = f"{u[2]}"
        user_display.append((u[0], label))
    if data and data.startswith("delete_user_typein:"):
        user_id = data.split(":", 1)[1]
        ctx.user_data["delete_user_id"] = user_id
        ctx.user_data["awaiting_delete_typein"] = True
        username = next((label for uid, label in user_display if str(uid) == str(user_id)), user_id)
        prompt = f"<b>Final Confirmation</b>\n\nType: <code>Remove records for {username}</code> to confirm.\n\nThis action cannot be undone."
        buttons = [
            [InlineKeyboardButton("Cancel", callback_data="delete_records")],
            [InlineKeyboardButton(BACK_BUTTON, callback_data="delete_records")]
        ]
        await q.edit_message_text(prompt, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        return
    if data and data.startswith("delete_user_confirm:"):
        user_id = data.split(":", 1)[1]
        ctx.user_data["delete_user_id"] = user_id
        ctx.user_data["awaiting_delete_typein"] = False
        username = next((label for uid, label in user_display if str(uid) == str(user_id)), user_id)
        prompt = f"<b>Confirm Deletion</b>\n\nYou are about to delete records for: <b>{username}</b>\n\nAre you absolutely sure?"
        buttons = [
            [InlineKeyboardButton("Confirm, am 100% sure", callback_data=f"delete_user_typein:{user_id}")],
            [InlineKeyboardButton("Cancel", callback_data="delete_records")],
            [InlineKeyboardButton(BACK_BUTTON, callback_data="delete_records")]
        ]
        await q.edit_message_text(prompt, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        return
    page_users, total_pages, start_idx, end_idx = pagination(user_display, page, DEFAULT_PAGE_SIZE)
    buttons = [[InlineKeyboardButton(label, callback_data=f"delete_user_confirm:{user_id}")] for user_id, label in page_users]
    pagination = []
    if total_pages > 1:
        if page > 0:
            pagination.append(InlineKeyboardButton(PREV_PAGE_BUTTON, callback_data="delete_records_prev_page"))
        pagination.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            pagination.append(InlineKeyboardButton(NEXT_PAGE_BUTTON, callback_data="delete_records_next_page"))
        if pagination:
            buttons.append(pagination)
    buttons.append([InlineKeyboardButton(REFRESH_BUTTON, callback_data="delete_records")])
    buttons.append([InlineKeyboardButton(BACK_BUTTON, callback_data="admin_control")])
    text = "🗑️ <b>Delete Records</b>\n\nSelect a user to delete their records.\n<b>Note:</b> Super Admin cannot be deleted."
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
    return

@handle_errors
async def handle_confirm_delete_records(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    if not ctx.user_data.get("awaiting_delete_typein"):
        return
    user_id = ctx.user_data.get("delete_user_id")
    if not user_id:
        await update.message.reply_text("No user selected for deletion.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BACK_BUTTON, callback_data="delete_records")]]))
        ctx.user_data["awaiting_delete_typein"] = False
        return
    expected = f"Remove records for {user_id}"
    typed = update.message.text.strip()
    from .database import remove_admin, remove_whitelist, remove_blacklisted_user, remove_pending_user, is_super_admin
    if is_super_admin(user_id):
        await update.message.reply_text("Cannot delete Super Admin.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BACK_BUTTON, callback_data="delete_records")]]))
        ctx.user_data["awaiting_delete_typein"] = False
        return
    if typed == expected:
        errors = []
        try:
            remove_admin(user_id)
        except Exception as e:
            errors.append(str(e))
        try:
            remove_whitelist(user_id)
        except Exception as e:
            errors.append(str(e))
        try:
            remove_blacklisted_user(user_id)
        except Exception as e:
            errors.append(str(e))
        try:
            remove_pending_user(user_id)
        except Exception as e:
            errors.append(str(e))
        ctx.user_data["awaiting_delete_typein"] = False
        ctx.user_data.pop("delete_user_id", None)
        if errors:
            await update.message.reply_text(f"Some errors occurred: {'; '.join(errors)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BACK_BUTTON, callback_data="delete_records")]]))
        else:
            await update.message.reply_text(f"✅ Records for {user_id} have been deleted.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BACK_BUTTON, callback_data="delete_records")]]))
    else:
        await update.message.reply_text(f"❌ Incorrect confirmation. Please type exactly: {expected}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="delete_records")]])) 

@admin_required
@handle_errors
async def handle_modify_allowed_domain(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if ctx.user_data is None:
        ctx.user_data = {}
    page = ctx.user_data.get("allowed_domain_page", 0)
    data = getattr(q, 'data', None)
    # Handle pagination
    if data == "allowed_domain_prev_page":
        ctx.user_data["allowed_domain_page"] = max(0, page - 1)
        page = ctx.user_data["allowed_domain_page"]
    elif data == "allowed_domain_next_page":
        ctx.user_data["allowed_domain_page"] = page + 1
        page = ctx.user_data["allowed_domain_page"]
    # Read allowed domains
    with open(ALLOWED_DOMAIN_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    domains = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
    from .Utilities import pagination
    page_domains, total_pages, start_idx, end_idx, pagination_buttons = pagination(domains, page, DEFAULT_PAGE_SIZE, "allowed_domain_prev_page", "allowed_domain_next_page")
    text = f"<b>Allowed Domains ({len(domains)} total)</b>\n\n"
    for i, domain in enumerate(page_domains, start_idx + 1):
        text += f"{i}. {domain}\n"
    buttons = [[InlineKeyboardButton(f"Remove {domain}", callback_data=f"remove_allowed_domain:{domain}")] for domain in page_domains]
    if pagination_buttons:
        buttons.append(pagination_buttons)
    buttons.append([InlineKeyboardButton("Add Domain", callback_data="add_allowed_domain")])
    buttons.append([InlineKeyboardButton(BACK_BUTTON, callback_data="admin_control")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

@admin_required
@handle_errors
async def handle_remove_allowed_domain(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if ctx.user_data is None:
        ctx.user_data = {}
    domain = q.data.split(":", 1)[1]
    with open(ALLOWED_DOMAIN_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    domains = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
    if domain in domains:
        domains.remove(domain)
        with open(ALLOWED_DOMAIN_PATH, 'w', encoding='utf-8') as f:
            f.write('# Allowed Streaming/Media Domains\n\n')
            for d in domains:
                f.write(d + '\n')
    await handle_modify_allowed_domain(update, ctx)

@admin_required
@handle_errors
async def handle_add_allowed_domain(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if ctx.user_data is None:
        ctx.user_data = {}
    ctx.user_data["awaiting_new_domain"] = True
    await q.edit_message_text("Send the new domain (e.g. youtube.com) as a message.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BACK_BUTTON, callback_data="modify_allowed_domain")]]))

@admin_required
@handle_errors
async def handle_new_domain_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    if not ctx.user_data.get("awaiting_new_domain"):
        return
    new_domain = update.message.text.strip()
    with open(ALLOWED_DOMAIN_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    domains = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
    if new_domain and new_domain not in domains:
        domains.append(new_domain)
        with open(ALLOWED_DOMAIN_PATH, 'w', encoding='utf-8') as f:
            f.write('# Allowed Streaming/Media Domains\n\n')
            for d in domains:
                f.write(d + '\n')
        await update.message.reply_text(f"Domain '{new_domain}' added.")
    else:
        await update.message.reply_text(f"Domain '{new_domain}' is already in the list or invalid.")
    ctx.user_data["awaiting_new_domain"] = False
    # Show the updated list
    await handle_modify_allowed_domain(update, ctx)

# Register new handlers in your dispatcher as needed:
# dispatcher.add_handler(CallbackQueryHandler(handle_modify_allowed_domain, pattern="^modify_allowed_domain$"))
# dispatcher.add_handler(CallbackQueryHandler(handle_remove_allowed_domain, pattern="^remove_allowed_domain:"))
# dispatcher.add_handler(CallbackQueryHandler(handle_add_allowed_domain, pattern="^add_allowed_domain$"))
# dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_domain_message)) 