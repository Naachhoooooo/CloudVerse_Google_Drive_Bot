from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .database import (
    is_admin, get_admins, add_admin, remove_admin, get_whitelist, add_whitelist, remove_whitelist, get_blacklisted_users, add_blacklisted_user, remove_blacklisted_user, edit_blacklisted_user, is_super_admin, get_super_admins,
    add_pending_user, get_pending_users, remove_pending_user, get_user_details_by_id, get_user_id_by_username, set_whitelist_expiration, is_whitelisted, get_admins_paginated, get_whitelist_paginated, get_blacklisted_users_paginated, get_pending_users_paginated
)
from datetime import datetime
from .config import GROUP_CHAT_ID, TeamCloudverse_TOPIC_ID, DB_PATH
import sqlite3
from .Utilities import pagination, admin_required, super_admin_required, handle_errors
from .database import get_known_user_username
from .TeamCloudverse import handle_access_request as teamcloudverse_handle_access_request
from typing import Any
from enum import Enum

# Message constants (user-facing)
ACCESS_CONTROL_TITLE = "Access Control"
FAILED_TO_LOAD_ACCESS_CONTROL = "Failed to load Access Control"
SUPER_ADMIN_LIST_TITLE = "👑 Super Admin List"
ADMIN_LIST_TITLE = "⭐ Admin List"
WHITELISTED_USERS_TITLE = "📃 Whitelisted Users"
BLACKLISTED_USERS_TITLE = "🚫 Blacklisted Users"
FAILED_TO_LOAD_SUPER_ADMIN_LIST = "Failed to load super admin list. Please try again later."
FAILED_TO_LOAD_ADMIN_LIST = "Failed to load admin list. Please try again later."
FAILED_TO_LOAD_WHITELIST = "Failed to load whitelist. Please try again later."
FAILED_TO_LOAD_BLACKLIST = "Failed to load blacklist. Please try again later."
NO_BLACKLISTED_USERS_MSG = "No users are currently blacklisted."
FAILED_TO_LOAD_REQUESTS = "Failed to load requests"
USER_UNRESTRICTED_MSG = "User {telegram_id} has been unrestricted."
FAILED_TO_UNRESTRICT_USER = "Failed to unrestrict user."
EDIT_RESTRICTION_PROMPT = "Edit restriction for user {telegram_id}:\nChoose restriction type:"
FAILED_TO_EDIT_RESTRICTION = "Failed to edit restriction."
ENTER_DURATION_PROMPT = "Enter the duration in hours for temporary restriction:"
RESTRICTION_SET_PERMANENT = "Restriction for user {telegram_id} set to Permanent."
FAILED_TO_SET_RESTRICTION_TYPE = "Failed to set restriction type."
RESTRICTION_SET_TEMPORARY = "Restriction for user {telegram_id} set to Temporary for {hours} hours."
FAILED_TO_SET_RESTRICTION_DURATION = "Failed to set restriction duration. Please enter a valid number of hours."
ACCESS_APPROVED_MSG = "Access approved for user @{username} (ID: {user_id})."
ACCESS_REJECTED_MSG = "Access rejected for user @{username} (ID: {user_id})."
FAILED_TO_PROCESS_REQUEST_ACTION = "Failed to process request action. Please try again later."
DEFAULT_ACCESS_REQUEST_MSG = "Your access request to use the bot has been {status} by Team CloudVerse"
DEFAULT_MESSAGE_SENT_TO_USER = "Default message sent to the user."
ENTER_NEW_ADMIN_USERNAME = "Enter the username of the new admin (e.g., @username):"
ADMIN_REMOVED_MSG = "Admin with ID {admin_id} has been removed."
FAILED_TO_REMOVE_ADMIN = "❌ {error}"
ENTER_NEW_USER_USERNAME = "Enter the username of the new user (e.g., @username):"
USER_REMOVED_FROM_WHITELIST = "User with ID {user_id} has been removed from the whitelist."
ENTER_TIME_LIMIT_FOR_USER = "Enter the time limit in hours for user {user} (eg:3H):"
ENTER_NUMBER_OF_HOURS_LIMITED_ACCESS = "Enter the number of hours for limited access:"
SEND_OPTIONAL_WELCOME_MESSAGE = "Send an optional welcome message to the user, or click Skip."

DEFAULT_PAGE_SIZE = 5
ACCESS_DENIED_MSG = "Access Denied : You are not authorised to perform this action\n\nContact *Team CloudVerse* for more"
SUPER_ADMIN_DENIED_MSG = "Access Denied : Only super admins can perform this action\n\nContact *Team CloudVerse* for more"
REJECTION_MSG = "Your access request to use the bot has been rejected by *Team CloudVerse* for professional reasons"
WELCOME_MSG = (
    "🎉 Welcome to *CloudVerse Google Drive Bot*\n\n"
    "your seamless solution for managing *Google Drive* directly from *Telegram* with various other functionalities\n\n"
    "Review the *Terms and Conditions* before getting started\n\n"
    "Reach out to *CloudVerse Support Team* anytime for assistance"
)
LIMITED_ACCESS_NEW_MSG = (
    "Your access request to use the bot has been approved by *Team CloudVerse* for *{hours} hours*\n\n"
    "🎉 Welcome to *CloudVerse Google Drive Bot*\n\n"
    "your seamless solution for managing *Google Drive* directly from *Telegram* with various other functionalities\n\n"
    "Review the *Terms and Conditions* before getting started\n\n"
    "Reach out to *CloudVerse Support Team* anytime for assistance"
)
LIMITED_ACCESS_EXISTING_MSG = "Your access to the bot has been modified by *Team  CloudVerse* to {hours} hour(s)"

class UserRole(Enum):
    ADMIN = 'admin'
    SUPER_ADMIN = 'super_admin'
    WHITELIST = 'whitelist'
    BLACKLIST = 'blacklist'

@handle_errors
@admin_required
async def handle_access_control(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Display the main access control menu for admins. Handles permission checks and menu rendering."""
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        telegram_id = getattr(q.from_user, 'id', None)
        buttons = [
            [InlineKeyboardButton("👑 Manage Super Admins", callback_data="manage_super_admins")],
            [InlineKeyboardButton("⭐ Manage Admins", callback_data="manage_admins")],
            [InlineKeyboardButton("👀 White List", callback_data="manage_whitelist")],
            [InlineKeyboardButton("🚫 Black List", callback_data="manage_blacklist")],
            [InlineKeyboardButton("✳️ Back", callback_data="back")]
        ]
        await q.edit_message_text(ACCESS_CONTROL_TITLE, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await q.edit_message_text(FAILED_TO_LOAD_ACCESS_CONTROL)

@handle_errors
async def manage_admins(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        data = getattr(q, 'data', None)
        current_page = ctx.user_data.get("admin_page", 0)
        if data == "admin_prev_page":
            ctx.user_data["admin_page"] = max(0, current_page - 1)
        elif data == "admin_next_page":
            ctx.user_data["admin_page"] = current_page + 1
        page = ctx.user_data.get("admin_page", 0)
        all_admins = get_admins()
        admins = [a for a in all_admins if not is_super_admin(a['telegram_id'])]
        admins, total_pages, _, _, pagination_buttons = pagination(admins, page, DEFAULT_PAGE_SIZE, "admin_prev_page", "admin_next_page")
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, username, name FROM cloudverse_users")
        users_data = {str(row[0]): {'username': row[1], 'name': row[2]} for row in cursor.fetchall()}
        conn.close()
        text = ADMIN_LIST_TITLE
        buttons = []
        for admin in admins:
            info = users_data.get(str(admin['telegram_id']), {})
            full_name = info.get('name', '')
            username = info.get('username', '') or admin.get('username', '')
            label = full_name or username or str(admin['telegram_id'])
            if username:
                label += f" (@{username})"
            buttons.append([InlineKeyboardButton(label, callback_data="noop")])
            buttons.append([
                InlineKeyboardButton("🫰 Promote", callback_data=f"promote_admin:{admin['telegram_id']}"),
                InlineKeyboardButton("🤞 Demote", callback_data=f"demote_admin:{admin['telegram_id']}"),
                InlineKeyboardButton("❌ Remove", callback_data=f"remove_admin:{admin['telegram_id']}")
            ])
        if pagination_buttons:
            buttons.append(pagination_buttons)
        buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back_to_access")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        telegram_id = getattr(q.from_user, 'id', None)
    except Exception as e:
        await q.edit_message_text(FAILED_TO_LOAD_ADMIN_LIST)

@handle_errors
async def manage_super_admins(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        data = getattr(q, 'data', None)
        current_page = ctx.user_data.get("super_admin_page", 0)
        if data == "super_admin_prev_page":
            ctx.user_data["super_admin_page"] = max(0, current_page - 1)
        elif data == "super_admin_next_page":
            ctx.user_data["super_admin_page"] = current_page + 1
        page = ctx.user_data.get("super_admin_page", 0)
        all_super_admins = get_super_admins()
        super_admins, total_pages, _, _, pagination_buttons = pagination(all_super_admins, page, DEFAULT_PAGE_SIZE, "super_admin_prev_page", "super_admin_next_page")
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, username, name FROM cloudverse_users")
        users_data = {str(row[0]): {'username': row[1], 'name': row[2]} for row in cursor.fetchall()}
        conn.close()
        text = SUPER_ADMIN_LIST_TITLE
        buttons = []
        for admin in super_admins:
            info = users_data.get(str(admin['telegram_id']), {})
            full_name = info.get('name', '')
            username = info.get('username', '') or admin.get('username', '')
            label = full_name or username or str(admin['telegram_id'])
            if username:
                label += f" (@{username})"
            buttons.append([InlineKeyboardButton(label, callback_data="noop")])
            buttons.append([
                InlineKeyboardButton("🤞 Demote", callback_data=f"demote_super_admin:{admin['telegram_id']}"),
                InlineKeyboardButton("❌ Remove", callback_data=f"remove_super_admin:{admin['telegram_id']}")
            ])
        if pagination_buttons:
            buttons.append(pagination_buttons)
        buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back_to_access")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        telegram_id = getattr(q.from_user, 'id', None)
    except Exception as e:
        await q.edit_message_text(FAILED_TO_LOAD_SUPER_ADMIN_LIST)

@handle_errors
async def manage_whitelist(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        data = getattr(q, 'data', None)
        current_page = ctx.user_data.get("whitelist_page", 0)
        if data == "whitelist_prev_page":
            ctx.user_data["whitelist_page"] = max(0, current_page - 1)
        elif data == "whitelist_next_page":
            ctx.user_data["whitelist_page"] = current_page + 1
        page = ctx.user_data.get("whitelist_page", 0)
        all_whitelist = get_whitelist()
        whitelist, total_pages, _, _, pagination_buttons = pagination(all_whitelist, page, DEFAULT_PAGE_SIZE, "whitelist_prev_page", "whitelist_next_page")
        text = WHITELISTED_USERS_TITLE
        buttons = []
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, username, name FROM cloudverse_users")
        users_data = {str(row[0]): {'username': row[1], 'name': row[2]} for row in cursor.fetchall()}
        conn.close()
        admins = set(str(a['telegram_id']) for a in get_admins())
        for user in whitelist:
            if str(user['telegram_id']) in admins:
                continue
            info = users_data.get(str(user['telegram_id']), {})
            full_name = info.get('name', '')
            username = info.get('username', '') or user.get('username', '')
            label = full_name or username or str(user['telegram_id'])
            if username:
                label += f" (@{username})"
            buttons.append([InlineKeyboardButton(label, callback_data="noop")])
            if user.get('expiration_time'):
                buttons.append([
                    InlineKeyboardButton("🗑️ Remove Limit", callback_data=f"remove_limit:{user['telegram_id']}"),
                    InlineKeyboardButton("♛ Promote", callback_data=f"promote_admin:{user['telegram_id']}"),
                    InlineKeyboardButton("❌ Remove", callback_data=f"remove_whitelist:{user['telegram_id']}")
                ])
            else:
                buttons.append([
                    InlineKeyboardButton("⏳ Set Limit", callback_data=f"set_limit:{user['telegram_id']}"),
                    InlineKeyboardButton("♛ Promote", callback_data=f"promote_admin:{user['telegram_id']}"),
                    InlineKeyboardButton("❌ Remove", callback_data=f"remove_whitelist:{user['telegram_id']}")
                ])
        if pagination_buttons:
            buttons.append(pagination_buttons)
        buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back_to_access")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        telegram_id = getattr(q.from_user, 'id', None)
    except Exception as e:
        await q.edit_message_text(FAILED_TO_LOAD_WHITELIST)

@handle_errors
async def manage_blacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        data = getattr(q, 'data', None)
        current_page = ctx.user_data.get("blacklist_page", 0)
        if data == "blacklist_prev_page":
            ctx.user_data["blacklist_page"] = max(0, current_page - 1)
        elif data == "blacklist_next_page":
            ctx.user_data["blacklist_page"] = current_page + 1
        page = ctx.user_data.get("blacklist_page", 0)
        all_blacklist = get_blacklisted_users()
        blacklist, total_pages, _, _, pagination_buttons = pagination(all_blacklist, page, DEFAULT_PAGE_SIZE, "blacklist_prev_page", "blacklist_next_page")
        text = BLACKLISTED_USERS_TITLE
        if not blacklist:
            text += NO_BLACKLISTED_USERS_MSG
        buttons = []
        for user in blacklist:
            restriction = f"⩇⩇:⩇⩇{user['restriction_type']}"
            if user['restriction_type'] == 'Temporary' and user['restriction_end']:
                restriction += f" (until {user['restriction_end']})"
            elif user['restriction_type'] == 'Permanent':
                restriction += "/Permanent"
            row = [
                InlineKeyboardButton(f"{user['username'] or user['telegram_id']}", callback_data="noop"),
                InlineKeyboardButton(restriction, callback_data="noop"),
                InlineKeyboardButton("🤝 Unrestrict", callback_data=f"unrestrict_blacklist:{user['telegram_id']}"),
                InlineKeyboardButton("✏️ Edit", callback_data=f"edit_blacklist:{user['telegram_id']}")
            ]
            buttons.append(row)
        if pagination_buttons:
            buttons.append(pagination_buttons)
        buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back_to_access")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        telegram_id = getattr(q.from_user, 'id', None)
    except Exception as e:
        await q.edit_message_text(FAILED_TO_LOAD_BLACKLIST)

@handle_errors
async def handle_unrestrict_blacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        telegram_id = q.data.split(":")[1]
        remove_blacklisted_user(telegram_id)
        await q.edit_message_text(USER_UNRESTRICTED_MSG.format(telegram_id=telegram_id))
        await manage_blacklist(update, ctx)
    except Exception as e:
        await q.edit_message_text(FAILED_TO_UNRESTRICT_USER)

@handle_errors
async def handle_edit_blacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        telegram_id = q.data.split(":")[1]
        buttons = [
            [InlineKeyboardButton("Temporary", callback_data=f"edit_blacklist_type:Temporary:{telegram_id}"),
             InlineKeyboardButton("Permanent", callback_data=f"edit_blacklist_type:Permanent:{telegram_id}")],
            [InlineKeyboardButton("✳️ Cancel", callback_data="manage_blacklist")]
        ]
        await q.edit_message_text(EDIT_RESTRICTION_PROMPT.format(telegram_id=telegram_id), reply_markup=InlineKeyboardMarkup(buttons))
        ctx.user_data["edit_blacklist_user"] = telegram_id
    except Exception as e:
        await q.edit_message_text(FAILED_TO_EDIT_RESTRICTION)

@handle_errors
async def handle_edit_blacklist_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        data = q.data.split(":")
        restriction_type = data[1]
        telegram_id = data[2]
        if restriction_type == "Temporary":
            await q.edit_message_text(ENTER_DURATION_PROMPT)
            ctx.user_data["awaiting_blacklist_duration"] = telegram_id
        else:
            from .database import edit_blacklisted_user
            edit_blacklisted_user(telegram_id, restriction_type, None)
            await q.edit_message_text(RESTRICTION_SET_PERMANENT.format(telegram_id=telegram_id))
            ctx.user_data.pop("edit_blacklist_user", None)
    except Exception as e:
        await q.edit_message_text(FAILED_TO_SET_RESTRICTION_TYPE)

@handle_errors
async def handle_blacklist_duration_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    telegram_id = ctx.user_data.pop("awaiting_blacklist_duration", None)
    if not telegram_id:
        return
    text = update.message.text if update.message else ''
    try:
        hours = int(text.strip())
        from datetime import datetime, timedelta
        until = datetime.now() + timedelta(hours=hours)
        from .database import edit_blacklisted_user
        edit_blacklisted_user(telegram_id, "Temporary", until)
        await update.message.reply_text(RESTRICTION_SET_TEMPORARY.format(telegram_id=telegram_id, hours=hours))
    except Exception as e:
        await update.message.reply_text(FAILED_TO_SET_RESTRICTION_DURATION)

@handle_errors
async def handle_access_actions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        data = q.data
        telegram_id = getattr(q.from_user, 'id', None)
        if data == "add_admin":
            if not is_super_admin(telegram_id):
                await q.edit_message_text(SUPER_ADMIN_DENIED_MSG, parse_mode='Markdown')
                return
            await q.edit_message_text(ENTER_NEW_ADMIN_USERNAME)
            ctx.user_data["next_action"] = "add_admin_username"
        elif data.startswith("remove_admin:"):
            if not is_super_admin(telegram_id):
                await q.edit_message_text(SUPER_ADMIN_DENIED_MSG, parse_mode='Markdown')
                return
            admin_id = data.split("remove_admin:")[1]
            if is_super_admin(admin_id):
                await q.edit_message_text(ACCESS_DENIED_MSG, parse_mode='Markdown')
                await manage_admins(update, ctx)
                return
            try:
                remove_admin(admin_id)
                await q.edit_message_text(ADMIN_REMOVED_MSG.format(admin_id=admin_id))
            except ValueError as e:
                await q.edit_message_text(FAILED_TO_REMOVE_ADMIN.format(error=str(e)))
            await manage_admins(update, ctx)
        elif data.startswith("promote_admin:"):
            admin_id = data.split(":")[1]
            import sqlite3
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("UPDATE cloudverse_users SET is_super_admin = 1 WHERE telegram_id = ? AND role = 'admin'", (str(admin_id),))
            conn.commit()
            conn.close()
            await q.edit_message_text(f"User {admin_id} has been promoted to Super Admin.")
            await manage_admins(update, ctx)
        elif data.startswith("demote_admin:"):
            admin_id = data.split(":")[1]
            import sqlite3
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("UPDATE cloudverse_users SET is_super_admin = 0 WHERE telegram_id = ? AND role = 'admin'", (str(admin_id),))
            conn.commit()
            conn.close()
            await q.edit_message_text(f"User {admin_id} has been demoted from Admin.")
            await manage_admins(update, ctx)
        elif data.startswith("demote_super_admin:"):
            admin_id = data.split(":")[1]
            import sqlite3
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("UPDATE cloudverse_users SET is_super_admin = 0 WHERE telegram_id = ? AND role = 'admin'", (str(admin_id),))
            conn.commit()
            conn.close()
            await q.edit_message_text(f"User {admin_id} has been demoted from Super Admin to Admin.")
            await manage_super_admins(update, ctx)
        elif data == "add_whitelist":
            await q.edit_message_text(ENTER_NEW_USER_USERNAME)
            ctx.user_data["next_action"] = "add_whitelist_username"
        elif data.startswith("remove_whitelist:"):
            user_id = data.split("remove_whitelist:")[1]
            remove_whitelist(user_id)
            await q.edit_message_text(USER_REMOVED_FROM_WHITELIST.format(user_id=user_id))
            await manage_whitelist(update, ctx)
        elif data.startswith("set_limit:"):
            user_id = data.split("set_limit:")[1]
            username = get_known_user_username(user_id)
            if username:
                prompt = ENTER_TIME_LIMIT_FOR_USER.format(user=f"@{username}")
            else:
                prompt = ENTER_TIME_LIMIT_FOR_USER.format(user=user_id)
            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("✳️ Cancel", callback_data="back_to_whitelist")]])
            await q.edit_message_text(prompt, reply_markup=back_button)
            ctx.user_data["next_action"] = f"set_limit_hours:{user_id}"
            ctx.user_data["awaiting_limit_hours"] = True
            ctx.user_data["pending_limit_user"] = user_id
        elif data == "admin_prev_page":
            ctx.user_data["admin_page"] = max(0, ctx.user_data.get("admin_page", 0) - 1)
            await manage_admins(update, ctx)
        elif data == "admin_next_page":
            ctx.user_data["admin_page"] = ctx.user_data.get("admin_page", 0) + 1
            await manage_admins(update, ctx)
        elif data == "whitelist_prev_page":
            ctx.user_data["whitelist_page"] = max(0, ctx.user_data.get("whitelist_page", 0) - 1)
            await manage_whitelist(update, ctx)
        elif data == "whitelist_next_page":
            ctx.user_data["whitelist_page"] = ctx.user_data.get("whitelist_page", 0) + 1
            await manage_whitelist(update, ctx)
        elif data == "blacklist_prev_page":
            ctx.user_data["blacklist_page"] = max(0, ctx.user_data.get("blacklist_page", 0) - 1)
            await manage_blacklist(update, ctx)
        elif data == "blacklist_next_page":
            ctx.user_data["blacklist_page"] = ctx.user_data.get("blacklist_page", 0) + 1
            await manage_blacklist(update, ctx)
        elif data.startswith("unrestrict_blacklist:"):
            await handle_unrestrict_blacklist(update, ctx)
        elif data.startswith("edit_blacklist:"):
            await handle_edit_blacklist(update, ctx)
        elif data.startswith("remove_limit:"):
            user_id = data.split("remove_limit:")[1]
            set_whitelist_expiration(user_id, None)
            ctx.user_data.pop("pending_limit_user", None)
            ctx.user_data.pop("awaiting_limit_hours", None)
            ctx.user_data.pop("next_action", None)
            await manage_whitelist(update, ctx)
    except Exception as e:
        await q.edit_message_text(FAILED_TO_PROCESS_REQUEST_ACTION)

@handle_errors
async def update_group_topic_message_status(telegram_id, status_text, ctx, status_button=None):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT group_message_id FROM pending_users WHERE telegram_id=?", (str(telegram_id),))
    row = cursor.fetchone()
    conn.close()
    if row and GROUP_CHAT_ID is not None and row[0] is not None:
        message_id = row[0]
        try:
            chat_id = int(str(GROUP_CHAT_ID))
            msg_id = int(str(message_id))
            await ctx.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=status_text,
                reply_markup=InlineKeyboardMarkup(status_button) if status_button else None
            )
        except Exception as e:
            pass
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("UPDATE pending_users SET group_message_id = NULL WHERE telegram_id=?", (str(telegram_id),))
        conn.commit()
        conn.close()

@handle_errors
async def post_access_request_to_group(ctx, telegram_id, username, first_name, last_name):
    from .TeamCloudverse import handle_access_request as teamcloudverse_handle_access_request
    user_details = get_user_details_by_id(telegram_id)
    expired_note = ""
    last_access_note = ""
    if user_details:
        if user_details.get("role") == "expired":
            expired_note = "\n\n⚠️ This user is an expired user."
            exp_time = user_details.get("expiration_time")
            approved_at = user_details.get("approved_at")
            if exp_time and approved_at:
                from datetime import datetime
                try:
                    exp_dt = datetime.fromisoformat(exp_time)
                    app_dt = datetime.fromisoformat(approved_at)
                    duration = exp_dt - app_dt
                    hours = int(duration.total_seconds() // 3600)
                    last_access_note = f"\nLast allotted access: {hours} hours"
                except Exception:
                    pass
    message = f"Access request from user:{expired_note}{last_access_note}"
    await teamcloudverse_handle_access_request(ctx, 'request', {
        'telegram_id': telegram_id,
        'username': username,
        'first_name': first_name,
        'last_name': last_name,
        'message': message
    })

@handle_errors
async def handle_access_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        data = q.data
        if data.startswith("access_limit:"):
            user_id = int(data.split(":")[1])
            ctx.user_data["pending_limit_user"] = user_id
            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("✳️ Back", callback_data="cancel_limit_setting")]])
            await q.edit_message_text(ENTER_NUMBER_OF_HOURS_LIMITED_ACCESS, reply_markup=back_button)
            ctx.user_data["awaiting_limit_hours"] = True
        elif data.startswith("access_approve:"):
            user_id = int(data.split(":")[1])
            ctx.user_data["pending_approve_user"] = user_id
            await q.edit_message_text(SEND_OPTIONAL_WELCOME_MESSAGE, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ Skip", callback_data="access_skip_approve")]]))
            ctx.user_data["awaiting_approve_message"] = True
        elif data.startswith("access_reject:"):
            user_id = int(data.split(":")[1])
            ctx.user_data["pending_reject_user"] = user_id
            await q.edit_message_text("Send an optional rejection message to the user, or click Skip.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ Skip", callback_data="access_skip_reject")]]))
            ctx.user_data["awaiting_reject_message"] = True
        elif data == "access_skip_approve":
            user_id = ctx.user_data.get("pending_approve_user")
            if user_id is not None:
                add_whitelist(user_id)
                remove_pending_user(user_id)
                await q.edit_message_text("Access to the bot has been approved.")
                await ctx.bot.send_message(chat_id=user_id, text=WELCOME_MSG, parse_mode='Markdown')
                await update_group_topic_message_status(user_id, f"✅ Approved by @{q.from_user.username or 'an admin'}", ctx)
            ctx.user_data.pop("pending_approve_user", None)
            ctx.user_data.pop("awaiting_approve_message", None)
        elif data == "access_skip_reject":
            user_id = ctx.user_data.get("pending_reject_user")
            if user_id is not None:
                remove_pending_user(user_id)
                await q.edit_message_text("Access to the bot has been rejected.")
                await ctx.bot.send_message(chat_id=user_id, text=REJECTION_MSG, parse_mode='Markdown')
                await update_group_topic_message_status(user_id, f"❌ Rejected by @{q.from_user.username or 'an admin'}", ctx)
            ctx.user_data.pop("pending_reject_user", None)
            ctx.user_data.pop("awaiting_reject_message", None)
        elif data == "cancel_limit_setting":
            ctx.user_data.pop("pending_limit_user", None)
            ctx.user_data.pop("awaiting_limit_hours", None)
            await handle_access_control(update, ctx)
    except Exception as e:
        await q.edit_message_text(FAILED_TO_PROCESS_REQUEST_ACTION)

@handle_errors
async def handle_access_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    if ctx.user_data.get("awaiting_approve_message"):
        user_id = ctx.user_data.get("pending_approve_user")
        if user_id is not None:
            add_whitelist(user_id)
            remove_pending_user(user_id)
            if update.message and hasattr(update.message, 'reply_text'):
                await update.message.reply_text("Access to the bot has been approved.")
                admin_message = update.message.text.strip() if update.message.text else ''
                username = update.message.from_user.username if update.message.from_user and hasattr(update.message.from_user, 'username') else 'an admin'
                await update_group_topic_message_status(user_id, f"✅ Approved by @{username}", ctx)
        ctx.user_data.pop("pending_approve_user", None)
        ctx.user_data.pop("awaiting_approve_message", None)
    elif ctx.user_data.get("awaiting_reject_message"):
        user_id = ctx.user_data.get("pending_reject_user")
        if user_id is not None:
            remove_pending_user(user_id)
            if update.message and hasattr(update.message, 'reply_text'):
                await update.message.reply_text("Access to the bot has been rejected.")
                msg_text = update.message.text if update.message and update.message.text else ''
                if msg_text:
                    await ctx.bot.send_message(chat_id=user_id, text=f"{REJECTION_MSG}\n\nAdmin Message : {msg_text}.", parse_mode='Markdown')
                else:
                    await ctx.bot.send_message(chat_id=user_id, text=REJECTION_MSG, parse_mode='Markdown')
                username = update.message.from_user.username if update.message.from_user and hasattr(update.message.from_user, 'username') else 'an admin'
                await update_group_topic_message_status(user_id, f"❌ Rejected by @{username}", ctx)
        ctx.user_data.pop("pending_reject_user", None)
        ctx.user_data.pop("awaiting_reject_message", None)
    elif (
        ctx.user_data.get("awaiting_limit_hours") or
        (ctx.user_data.get("next_action") and str(ctx.user_data.get("next_action")).startswith("set_limit_hours:"))
    ):
        user_id = ctx.user_data.get("pending_limit_user")
        if not user_id:
            return
        ctx.user_data.pop("pending_limit_user", None)
        ctx.user_data.pop("awaiting_limit_hours", None)
        ctx.user_data.pop("next_action", None)
        if update.message and update.message.text:
            try:
                hours = int(update.message.text.strip())
                from datetime import datetime, timedelta
                expiration_time = (datetime.now() + timedelta(hours=hours)).isoformat()
                set_whitelist_expiration(user_id, expiration_time)
                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("✳️ Back", callback_data="back_to_whitelist")]])
                if not is_whitelisted(user_id):
                    await update.message.reply_text(LIMITED_ACCESS_NEW_MSG.format(hours=hours), parse_mode='Markdown', reply_markup=back_button)
                    await ctx.bot.send_message(chat_id=user_id, text=LIMITED_ACCESS_NEW_MSG.format(hours=hours), parse_mode='Markdown')
                else:
                    msg = LIMITED_ACCESS_EXISTING_MSG.format(hours=hours)
                    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=back_button)
                    await ctx.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
                username = update.message.from_user.username if update.message.from_user and hasattr(update.message.from_user, 'username') else 'an admin'
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                details = (
                    f"Name: {update.message.from_user.first_name or ''} {update.message.from_user.last_name or ''}\n"
                    f"Username: @{username or 'N/A'}\n"
                    f"ID: {user_id or 'N/A'}\n\n"
                    f"Bot : CloudVerse Google Drive Bot\n"
                    f"Request Status : Limited Access ({hours} hours)\n"
                    f"Timestamp: {timestamp}"
                )
                status_button = [[InlineKeyboardButton(f"⏳ Limited by @{username}", callback_data="noop")]]
                await update_group_topic_message_status(user_id, details, ctx, status_button)
            except Exception:
                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("✳️ Back", callback_data="back_to_whitelist")]])
                await update.message.reply_text("Please enter valid hours (e.g., 12 or 12H).", reply_markup=back_button)
        return