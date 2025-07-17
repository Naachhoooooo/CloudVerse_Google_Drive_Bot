from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .database import (
    is_admin, get_admins, add_admin, remove_admin, get_whitelist, add_whitelist, remove_whitelist, get_blacklisted_users, add_blacklisted_user, remove_blacklisted_user, edit_blacklisted_user, is_super_admin,
    add_pending_user, get_pending_users, remove_pending_user, get_user_details_by_id, get_user_id_by_username, set_whitelist_expiration
)
from datetime import datetime
from .config import GROUP_CHAT_ID, TeamCloudverse_TOPIC_ID, DB_PATH
import sqlite3
from .Logger import log_access_change, log_role_change, log_error, get_logger
logger = get_logger()
from .Utilities import paginate_list
from .TeamCloudverse import handle_access_request
from typing import Any
from enum import Enum

DEFAULT_PAGE_SIZE = 5

class UserRole(Enum):
    ADMIN = 'admin'
    SUPER_ADMIN = 'super_admin'
    WHITELIST = 'whitelist'
    BLACKLIST = 'blacklist'

async def handle_access_control(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Display the main access control menu for admins."""
    q = getattr(update, 'callback_query', None)
    if not q:
        log_error("handle_access_control called without callback_query", context="handle_access_control")
        return
    try:
        await q.answer()
        telegram_id = getattr(q.from_user, 'id', None)
        if telegram_id is None or not is_admin(telegram_id):
            await q.edit_message_text("Access denied. You do not have permission to perform this action.")
            return
        buttons = [
            [InlineKeyboardButton("👑 Manage Admins", callback_data="manage_admins")],
            [InlineKeyboardButton("👀 White List", callback_data="manage_whitelist")],
            [InlineKeyboardButton("🚫 Black List", callback_data="manage_blacklist")],
            [InlineKeyboardButton("📝 Manage Requests", callback_data="manage_requests")],
            [InlineKeyboardButton("✳️ Back", callback_data="back")]
        ]
        await q.edit_message_text("Access Control", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        log_error(e, context=f"handle_access_control user_id={getattr(q.from_user, 'id', 'unknown')}")
        await q.edit_message_text("Failed to load Access Control")

async def manage_admins(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Display a paginated list of admins with options to demote or remove."""
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        log_error("manage_admins called without callback_query", context="manage_admins")
        return
    try:
        await q.answer()
        admins = get_admins()
        page = ctx.user_data.get("admin_page", 0)
        page_admins, total_pages, _, _ = paginate_list(admins, page, DEFAULT_PAGE_SIZE)
        # Fetch all known users for mapping
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, username, first_name, last_name FROM known_users")
        known_users = {str(row[0]): {'username': row[1], 'first_name': row[2], 'last_name': row[3]} for row in cursor.fetchall()}
        conn.close()
        text = "👑 Admin List"
        buttons = []
        for admin in page_admins:
            info = known_users.get(str(admin['telegram_id']), {})
            full_name = f"{info.get('first_name', '')} {info.get('last_name', '')}".strip()
            username = info.get('username', '') or admin.get('username', '')
            label = full_name or username or str(admin['telegram_id'])
            if username:
                label += f" (@{username})"
            buttons.append([InlineKeyboardButton(label, callback_data="noop")])
            # Don't show remove/demote buttons for super admin
            if is_super_admin(admin['telegram_id']):
                buttons.append([InlineKeyboardButton("👑 Super Admin - Cannot Remove", callback_data="noop")])
            else:
                buttons.append([
                    InlineKeyboardButton("🤞 Demote", callback_data=f"demote_admin:{admin['telegram_id']}"),
                    InlineKeyboardButton("❌ Remove", callback_data=f"remove_admin:{admin['telegram_id']}")
                ])
        # Pagination controls
        if total_pages > 1:
            pagination = []
            if page > 0:
                pagination.append(InlineKeyboardButton("◀️ Prev", callback_data="admin_prev_page"))
            pagination.append(InlineKeyboardButton(f"[{page+1}/{total_pages}]", callback_data="noop"))
            if page < total_pages - 1:
                pagination.append(InlineKeyboardButton("Next ▶️", callback_data="admin_next_page"))
            buttons.append(pagination)
        buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back_to_access")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        log_error(e, context=f"manage_admins user_id={getattr(q.from_user, 'id', 'unknown')}")
        await q.edit_message_text("Failed to load admin list. Please try again later.")

async def manage_whitelist(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Display a paginated list of whitelisted users with options to set/remove limits, promote, or remove."""
    q = getattr(update, 'callback_query', None)
    if not q:
        log_error("manage_whitelist called without callback_query", context="manage_whitelist")
        return
    try:
        await q.answer()
        whitelist = get_whitelist()
        page = ctx.user_data.get("whitelist_page", 0) if ctx.user_data else 0
        page_whitelist, total_pages, _, _ = paginate_list(whitelist, page, DEFAULT_PAGE_SIZE)
        text = "📃 Approved Users"
        buttons = []
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, username, first_name, last_name FROM known_users")
        known_users = {str(row[0]): {'username': row[1], 'first_name': row[2], 'last_name': row[3]} for row in cursor.fetchall()}
        conn.close()
        admins = set(str(a['telegram_id']) for a in get_admins())
        for user in page_whitelist:
            if str(user['telegram_id']) in admins:
                continue
            info = known_users.get(str(user['telegram_id']), {})
            full_name = f"{info.get('first_name', '')} {info.get('last_name', '')}".strip()
            username = info.get('username', '') or user.get('username', '')
            label = full_name or username or str(user['telegram_id'])
            if username:
                label += f" (@{username})"
            buttons.append([InlineKeyboardButton(label, callback_data="noop")])
            # Show Remove Limit if expiration_time is set, else Set Limit
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
        # Pagination controls
        if total_pages > 1:
            pagination = []
            if page > 0:
                pagination.append(InlineKeyboardButton("◀️ Prev", callback_data="whitelist_prev_page"))
            pagination.append(InlineKeyboardButton(f"[{page+1}/{total_pages}]", callback_data="noop"))
            if page < total_pages - 1:
                pagination.append(InlineKeyboardButton("Next ▶️", callback_data="whitelist_next_page"))
            buttons.append(pagination)
        buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back_to_access")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        log_error(e, context=f"manage_whitelist user_id={getattr(q.from_user, 'id', 'unknown')}")
        await q.edit_message_text("Failed to load whitelist. Please try again later.")

async def manage_requests(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Display a paginated list of pending access requests with options to approve or reject."""
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        log_error("manage_requests called without callback_query", context="manage_requests")
        return
    try:
        await q.answer()
        pending = get_pending_users()
        page = ctx.user_data.get("requests_page", 0)
        page_pending, total_pages, _, _ = paginate_list(pending, page, DEFAULT_PAGE_SIZE)
        buttons = []
        if not pending:
            buttons.append([
                InlineKeyboardButton("♻️ Refresh", callback_data="refresh_requests"),
                InlineKeyboardButton("✳️ Back", callback_data="back_to_access")
            ])
            await q.edit_message_text("Access denied. You do not have permission to perform this action.", reply_markup=InlineKeyboardMarkup(buttons))
            return
        text = ""
        for p in page_pending:
            text += (
                f"Bot : CloudVerse Google Drive Bot\n"
                f"Name: {p['first_name']} {p['last_name'] or ''}\n"
                f"Username: @{p['username'] or 'N/A'}\n"
                f"ID: {p['telegram_id']}\n\n"
            )
            buttons.append([
                InlineKeyboardButton(f"✅ Approve", callback_data=f"approve:{p['telegram_id']}"),
                InlineKeyboardButton(f"❌ Reject", callback_data=f"reject:{p['telegram_id']}")
            ])
        # Pagination for requests
        if total_pages > 1:
            pagination = []
            if page > 0:
                pagination.append(InlineKeyboardButton("◀️ Prev", callback_data="requests_prev_page"))
            pagination.append(InlineKeyboardButton(f"[{page+1}/{total_pages}]", callback_data="noop"))
            if page < total_pages - 1:
                pagination.append(InlineKeyboardButton("Next ▶️", callback_data="requests_next_page"))
            buttons.append(pagination)
        # Add Refresh and Back buttons
        buttons.append([
            InlineKeyboardButton("♻️ Refresh", callback_data="refresh_requests"),
            InlineKeyboardButton("✳️ Back", callback_data="back_to_access")
        ])
        await q.edit_message_text(text.strip(), reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        log_error(e, context=f"manage_requests user_id={getattr(q.from_user, 'id', 'unknown')}")
        await q.edit_message_text("Failed to load requests")

async def manage_blacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Display a paginated list of blacklisted users with options to unrestrict or edit."""
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        log_error("manage_blacklist called without callback_query", context="manage_blacklist")
        return
    try:
        await q.answer()
        blacklist = get_blacklisted_users()
        page = ctx.user_data.get("blacklist_page", 0)
        page_blacklist, total_pages, start_idx, end_idx = paginate_list(blacklist, page, DEFAULT_PAGE_SIZE)
        text = "🚫 Black Listed Users\n\n"
        if not blacklist:
            text += "No users are currently blacklisted."
        buttons = []
        for user in page_blacklist:
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
        # Pagination controls
        if total_pages > 1:
            pagination = []
            if page > 0:
                pagination.append(InlineKeyboardButton("◀️ Prev", callback_data="blacklist_prev_page"))
            pagination.append(InlineKeyboardButton(f"[{page+1}/{total_pages}]", callback_data="noop"))
            if page < total_pages - 1:
                pagination.append(InlineKeyboardButton("Next ▶️", callback_data="blacklist_next_page"))
            buttons.append(pagination)
        buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back_to_access")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        log_error(e, context=f"manage_blacklist user_id={getattr(q.from_user, 'id', 'unknown')}")
        await q.edit_message_text("Failed to load blacklist")

# Callback handlers for blacklist pagination and actions
async def handle_blacklist_pagination(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    data = q.data
    current_page = ctx.user_data.get("blacklist_page", 0)
    if data == "blacklist_prev_page":
        ctx.user_data["blacklist_page"] = max(0, current_page - 1)
    elif data == "blacklist_next_page":
        ctx.user_data["blacklist_page"] = current_page + 1
    await manage_blacklist(update, ctx)

async def handle_unrestrict_blacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        telegram_id = q.data.split(":")[1]
        remove_blacklisted_user(telegram_id)
        await q.edit_message_text(f"User {telegram_id} has been unrestricted.")
        await manage_blacklist(update, ctx)
    except Exception as e:
        log_error(e, context=f"handle_unrestrict_blacklist user_id={getattr(q.from_user, 'id', 'unknown')}")
        await q.edit_message_text("Failed to unrestrict user.")

async def handle_edit_blacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        return
    try:
        await q.answer()
        telegram_id = q.data.split(":")[1]
        # Show options for restriction type
        buttons = [
            [InlineKeyboardButton("Temporary", callback_data=f"edit_blacklist_type:Temporary:{telegram_id}"),
             InlineKeyboardButton("Permanent", callback_data=f"edit_blacklist_type:Permanent:{telegram_id}")],
            [InlineKeyboardButton("✳️ Cancel", callback_data="manage_blacklist")]
        ]
        await q.edit_message_text(f"Edit restriction for user {telegram_id}:\nChoose restriction type:", reply_markup=InlineKeyboardMarkup(buttons))
        ctx.user_data["edit_blacklist_user"] = telegram_id
    except Exception as e:
        log_error(e, context=f"handle_edit_blacklist user_id={getattr(q.from_user, 'id', 'unknown')}")
        await q.edit_message_text("Failed to edit restriction.")

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
            await q.edit_message_text(f"Enter the duration in hours for temporary restriction:")
            ctx.user_data["awaiting_blacklist_duration"] = telegram_id
        else:
            # Update restriction in DB as permanent
            from .database import edit_blacklisted_user
            edit_blacklisted_user(telegram_id, restriction_type, None)
            await q.edit_message_text(f"Restriction for user {telegram_id} set to Permanent.")
            ctx.user_data.pop("edit_blacklist_user", None)
    except Exception as e:
        log_error(e, context=f"handle_edit_blacklist_type user_id={getattr(q.from_user, 'id', 'unknown')}")
        await q.edit_message_text("Failed to set restriction type.")

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
        await update.message.reply_text(f"Restriction for user {telegram_id} set to Temporary for {hours} hours.")
    except Exception as e:
        log_error(e, context=f"handle_blacklist_duration_input user_id={getattr(update.message.from_user, 'id', 'unknown')}")
        await update.message.reply_text("Failed to set restriction duration. Please enter a valid number of hours.")

async def handle_request_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle approval or rejection of pending user requests."""
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        log_error("handle_request_action called without callback_query", context="handle_request_action")
        return
    try:
        await q.answer()
        data = q.data
        admin_username = getattr(q.from_user, 'username', 'an admin') if hasattr(q.from_user, "username") else "an admin"
        admin_id = getattr(q.from_user, 'id', 'N/A')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user_id = None
        action = None
        if data.startswith("approve:"):
            user_id = data.split("approve:")[1]
            action = "Approved"
        elif data.startswith("reject:"):
            user_id = data.split("reject:")[1]
            action = "Rejected"
        user_id = str(user_id) if user_id is not None else None
        user_details = get_user_details_by_id(user_id) if user_id else None
        if user_details:
            name = user_details.get('name', '')
            if ' ' in name:
                first_name, last_name = name.split(' ', 1)
            else:
                first_name, last_name = name, ''
            username = user_details.get('username', '')
        else:
            first_name, last_name, username = "", "", ""
        # New format for group message
        details = (
            f"Name: {first_name} {last_name}\n"
            f"Username: @{username or 'N/A'}\n"
            f"ID: {user_id or 'N/A'}\n\n"
            f"Bot : CloudVerse Google Drive Bot\n"
            f"Request Status : {action}\n"
            f"Timestamp: {timestamp}"
        )
        # Show a single status button (non-interactive)
        status_button = [[InlineKeyboardButton(f"{'✅ Approved' if action == 'Approved' else '❌ Rejected'} by @{admin_username}", callback_data="noop")]]
        if action == "Approved" and user_id:
            add_whitelist(user_id)
            remove_pending_user(user_id)
            log_access_change(user_id, "approved", admin_id)
            await q.edit_message_text(f"Access approved for user @{username} (ID: {user_id}).")
            await ctx.bot.send_message(chat_id=user_id, text="Welcome to the Access Control Menu.")
            await handle_access_request(ctx, 'approve', {
                'telegram_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'admin_username': admin_username
            })
        elif action == "Rejected" and user_id:
            remove_pending_user(user_id)
            log_access_change(user_id, "rejected", admin_id)
            await q.edit_message_text(f"Access rejected for user @{username} (ID: {user_id}).")
            await handle_access_request(ctx, 'reject', {
                'telegram_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'admin_username': admin_username
            })
        await q.edit_message_text(details, reply_markup=InlineKeyboardMarkup(status_button))
        await manage_requests(update, ctx)
    except Exception as e:
        log_error(e, context=f"handle_request_action user_id={getattr(q.from_user, 'id', 'unknown')}")
        await q.edit_message_text("Failed to process request action. Please try again later.")

async def skip_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        log_error("skip_message called without callback_query", context="skip_message")
        return
    try:
        await q.answer()
        data = q.data
        user_id, action = data.split("skip_message:")[1].split(":")
        message = "Your access request to use the bot has been " + ("approved." if action == "approve" else "rejected") + "by Team CloudVerse"
        await ctx.bot.send_message(chat_id=user_id, text=message)
        await q.edit_message_text("Default message sent to the user.")
        if ctx.user_data and "expecting_approval_message" in ctx.user_data:
            del ctx.user_data["expecting_approval_message"]
    except Exception as e:
        log_error(e, context=f"skip_message user_id={getattr(q.from_user, 'id', 'unknown')}")

async def handle_access_actions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        log_error("handle_access_actions called without callback_query", context="handle_access_actions")
        return
    try:
        await q.answer()
        data = q.data
        telegram_id = getattr(q.from_user, 'id', None)
        if telegram_id is None or not is_admin(telegram_id):
            await q.edit_message_text("Access denied. You do not have permission to perform this action.")
            return
        if data == "add_admin":
            if not is_super_admin(telegram_id):
                await q.edit_message_text("Access denied. Only super admins can add new admins.")
                return
            await q.edit_message_text("Enter the username of the new admin (e.g., @username):")
            ctx.user_data["next_action"] = "add_admin_username"
        elif data.startswith("remove_admin:"):
            if not is_super_admin(telegram_id):
                await q.edit_message_text("Access denied. Only super admins can remove admins.")
                return
            admin_id = data.split("remove_admin:")[1]
            # Check if trying to remove super admin
            if is_super_admin(admin_id):
                await q.edit_message_text("Access denied. You do not have permission to perform this action.")
                await manage_admins(update, ctx)
                return
            try:
                remove_admin(admin_id)
                log_role_change(admin_id, "admin", "user", telegram_id)
                await q.edit_message_text(f"Admin with ID {admin_id} has been removed.")
            except ValueError as e:
                await q.edit_message_text(f"❌ {str(e)}")
            await manage_admins(update, ctx)
        elif data == "add_whitelist":
            await q.edit_message_text("Enter the username of the new user (e.g., @username):")
            ctx.user_data["next_action"] = "add_whitelist_username"
        elif data.startswith("remove_whitelist:"):
            user_id = data.split("remove_whitelist:")[1]
            remove_whitelist(user_id)
            await q.edit_message_text(f"User with ID {user_id} has been removed from the whitelist.")
            await manage_whitelist(update, ctx)
        elif data.startswith("set_limit:"):
            user_id = data.split("set_limit:")[1]
            # TODO: Implement get_known_user_username()
            # username = get_known_user_username(user_id)
            username = None
            if username:
                prompt = f"Enter the time limit in hours for user @{username} (eg:3H):"
            else:
                prompt = f"Enter the time limit in hours for user {user_id} (eg:3H):"
            # Add back button to cancel time limit setting
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
        elif data == "requests_prev_page":
            ctx.user_data["requests_page"] = max(0, ctx.user_data.get("requests_page", 0) - 1)
            await manage_requests(update, ctx)
        elif data == "requests_next_page":
            ctx.user_data["requests_page"] = ctx.user_data.get("requests_page", 0) + 1
            await manage_requests(update, ctx)
        elif data == "back_to_access":
            await handle_access_control(update, ctx)
        elif data == "back_to_whitelist":
            await manage_whitelist(update, ctx)
        elif data == "manage_blacklist":
            await manage_blacklist(update, ctx)
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
        elif data == "refresh_requests":
            await manage_requests(update, ctx)
        elif data.startswith("remove_limit:"):
            user_id = data.split("remove_limit:")[1]
            set_whitelist_expiration(user_id, None) # Clear expiration time
            ctx.user_data.pop("pending_limit_user", None)
            ctx.user_data.pop("awaiting_limit_hours", None)
            ctx.user_data.pop("next_action", None)
            await manage_whitelist(update, ctx)
    except Exception as e:
        log_error(e, context=f"handle_access_actions user_id={getattr(q.from_user, 'id', 'unknown')}")
        log_error(e, context="handle_access_actions")

# Utility function to update and clean up group topic message
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
            log_error(e, context=f"update_group_topic_message_status user_id={getattr(ctx.bot.from_user, 'id', 'unknown')}")
        # Remove the mapping after handling
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("UPDATE pending_users SET group_message_id = NULL WHERE telegram_id=?", (str(telegram_id),))
        conn.commit()
        conn.close()

async def post_access_request_to_group(ctx, telegram_id, username, first_name, last_name):
    if GROUP_CHAT_ID is None or TeamCloudverse_TOPIC_ID is None:
        return
    try:
        await handle_access_request(ctx, 'request', {
            'telegram_id': telegram_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name
        })
    except Exception as e:
        log_error(e, context=f"post_access_request_to_group user_id={telegram_id}")

async def handle_access_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = getattr(update, 'callback_query', None)
    if not q:
        log_error("handle_access_request called without callback_query", context="handle_access_request")
        return
    try:
        await q.answer()
        data = q.data
        if data.startswith("access_limit:"):
            user_id = int(data.split(":")[1])
            ctx.user_data["pending_limit_user"] = user_id
            # Add back button to cancel time limit setting
            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("✳️ Cancel", callback_data="cancel_limit_setting")]])
            await q.edit_message_text("Enter the number of hours for limited access:", reply_markup=back_button)
            ctx.user_data["awaiting_limit_hours"] = True
        elif data.startswith("access_approve:"):
            user_id = int(data.split(":")[1])
            ctx.user_data["pending_approve_user"] = user_id
            await q.edit_message_text("Send an optional welcome message to the user, or click Skip.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ Skip", callback_data="access_skip_approve")]]))
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
                await ctx.bot.send_message(chat_id=user_id, text="Welcome to the Access Control Menu.")
                logger.info(f"Access approved for user {user_id}", extra={"user_id": user_id})
                await update_group_topic_message_status(user_id, f"✅ Approved by @{q.from_user.username or 'an admin'}", ctx)
            ctx.user_data.pop("pending_approve_user", None)
            ctx.user_data.pop("awaiting_approve_message", None)
        elif data == "access_skip_reject":
            user_id = ctx.user_data.get("pending_reject_user")
            if user_id is not None:
                remove_pending_user(user_id)
                await q.edit_message_text("Access to the bot has been rejected.")
                await ctx.bot.send_message(chat_id=user_id, text="Your access request to use the bot has been rejected by Team CloudVerse.")
                logger.info(f"Access rejected for user {user_id}", extra={"user_id": user_id})
                await update_group_topic_message_status(user_id, f"❌ Rejected by @{q.from_user.username or 'an admin'}", ctx)
            ctx.user_data.pop("pending_reject_user", None)
            ctx.user_data.pop("awaiting_reject_message", None)
        elif data == "cancel_limit_setting":
            # Clear the pending limit user and return to access control
            ctx.user_data.pop("pending_limit_user", None)
            ctx.user_data.pop("awaiting_limit_hours", None)
            await handle_access_control(update, ctx)
    except Exception as e:
        log_error(e, context=f"handle_access_request user_id={getattr(q.from_user, 'id', 'unknown')}")

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
                    await ctx.bot.send_message(chat_id=user_id, text=f"Your access request to use the bot has been rejected by Team CloudVerse.\n\nAdmin Message : {msg_text}.")
                else:
                    await ctx.bot.send_message(chat_id=user_id, text="Your access request to use the bot has been rejected by Team CloudVerse.")
                username = update.message.from_user.username if update.message.from_user and hasattr(update.message.from_user, 'username') else 'an admin'
                await update_group_topic_message_status(user_id, f"❌ Rejected by @{username}", ctx)
        ctx.user_data.pop("pending_reject_user", None)
        ctx.user_data.pop("awaiting_reject_message", None)
    elif (
        ctx.user_data.get("awaiting_limit_hours") or
        (ctx.user_data.get("next_action") and str(ctx.user_data.get("next_action")).startswith("set_limit_hours:"))
    ):
        user_id = ctx.user_data.get("pending_limit_user")
        # If state is already cleared, do nothing
        if not user_id:
            return
        # Always clear state first!
        ctx.user_data.pop("pending_limit_user", None)
        ctx.user_data.pop("awaiting_limit_hours", None)
        ctx.user_data.pop("next_action", None)
        if update.message and update.message.text:
            try:
                hours = int(update.message.text.strip())
                from datetime import datetime, timedelta
                expiration_time = (datetime.now() + timedelta(hours=hours)).isoformat()
                set_whitelist_expiration(user_id, expiration_time)
                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("✳️ Back to Whitelist", callback_data="back_to_whitelist")]])
                await update.message.reply_text(f"Your access  request to the bot has been approved for {hours} hours by Team CloudVerse.", reply_markup=back_button)
                await ctx.bot.send_message(chat_id=user_id, text=f"Your access  request to the bot has been approved for {hours} hours by Team CloudVerse.")
                username = update.message.from_user.username if update.message.from_user and hasattr(update.message.from_user, 'username') else 'an admin'
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                # New format for group message
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
                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("✳️ Back to Whitelist", callback_data="back_to_whitelist")]])
                await update.message.reply_text("Please enter valid hours (e.g., 12 or 12H).", reply_markup=back_button)
        return