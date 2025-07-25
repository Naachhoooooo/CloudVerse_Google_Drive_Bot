import tempfile
import os
import asyncio
import re
import requests
from googleapiclient.http import MediaFileUpload
from .Settings import handle_settings, login, logout, handle_logout_action, switch_account_menu, set_primary, update_def_location, update_parallel_uploads
from .MessageForDeveloper import handle_cloudverse_support, send_to_developer, handle_developer_reply, handle_reply_callback, handle_user_reply
from .TermsAndCondition import show_terms_and_conditions
from .config import BOT_TOKEN, GROUP_CHAT_ID, SUPER_ADMIN_ID
from .database import init_db, is_admin, is_whitelisted, add_admin, add_whitelist, add_pending_user, get_user_id_by_username, set_whitelist_expiration, is_super_admin, get_whitelist_expiring_soon, mark_expired_users, unban_expired_temporary_blacklist
from .drive import get_drive_service, search_files, create_folder, rename_file, get_storage_info
from .MainMenu import start as menu_start, handle_menu
from .FileManager import handle_file_manager, handle_folder_navigation, handle_file_selection, handle_file_actions, handle_file_size, handle_folder_size
from .AccountProfile import handle_profile
from .StorageDetails import handle_storage, refresh_storage
from .RecycleBin import handle_bin, handle_bin_navigation
from .AccessControl import handle_access_control, handle_access_actions, post_access_request_to_group, handle_access_request, handle_access_message, manage_admins, manage_whitelist, manage_blacklist, handle_blacklist_pagination, handle_unrestrict_blacklist, handle_edit_blacklist
from .Broadcast import handle_broadcast_message, handle_broadcast_media_message, handle_broadcast_approval
from .AnalyticsReport import handle_analytics_report, handle_analytics_report_type
from .Utilities import format_size, is_url, handle_errors, access_required
from .Search import search_next_page, search_prev_page, handle_search_item, handle_inline_query
from .Uploader import cancel_upload, handle_file_upload, handle_url_upload
from .AdminControls import handle_admin_control, handle_admin_list, handle_users_list, handle_admin_pagination, handle_users_pagination, handle_performance_panel, handle_performance_panel_back, handle_edit_terms_condition, handle_terms_update_message, handle_authenticate_session, handle_telethon_auth_message, handle_delete_records, handle_delete_user_typein, handle_delete_user_typein_prompt, handle_delete_user_confirm
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, filters, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, InlineQueryHandler
from telegram import BotCommand, Update, InlineKeyboardButton, InlineKeyboardMarkup, InputTextMessageContent
import aiohttp
from telegram import InlineQueryResultArticle
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")
warnings.filterwarnings("ignore", category=UserWarning, message="`Application` instances should be built via the `ApplicationBuilder`.")
warnings.filterwarnings("ignore", category=UserWarning, module="googleapiclient")
import signal
import threading
import time
import curses
import webbrowser
import http.server
import socketserver
import subprocess
import sys
from .UserState import UserState, UserStateEnum
from .AccessManager import mark_expired_users_and_notify, unban_expired_temporary_blacklist_and_notify

load_dotenv()

# Message constants (user-facing)
ERROR_OCCURRED_MSG = "An error occurred. Please try again or use /cancel."
ACCESS_EXPIRED_MSG = "Your access to the bot has expired. Please request access again by sending /start."
USER_INFO_NOT_FOUND_MSG = "User info not found. Please try again or contact support."
ACCESS_PENDING_MSG = "Your access request has been submitted to *Team CloudVerse* for Verification"
ACCESS_DENIED_MSG = "Access Denied : You are not authorised to perform this action\n\nContact *Team CloudVerse* for more"
PERMANENT_DELETE_CANCELLED_MSG = "Permanent delete cancelled."
SERVICE_UNAVAILABLE_MSG = "Service unavailable. Please try again later."
MESSAGE_SENT_TO_USER_MSG = "Message sent to user."
LOGOUT_CANCELLED_MSG = "Logout cancelled."
LOGIN_FAILED_MSG = "Login failed: {error}"
FILE_RENAMED_SUCCESS_MSG = "File renamed successfully."
FOLDER_RENAMED_SUCCESS_MSG = "Folder renamed successfully."
FOLDER_CREATED_SUCCESS_MSG = "Folder created successfully. ID: {folder_id}"
PARALLEL_UPLOAD_LIMIT_UPDATED_MSG = "Parallel upload limit updated."
PARALLEL_UPLOAD_LIMIT_RANGE_MSG = "Please enter a number between 1 and 5."
ACCESS_DENIED_SUPER_ADMIN_MSG = "Access denied. Only super admins can add new admins."
USER_ADDED_AS_ADMIN_MSG = "User @{username} added as admin."
USER_NOT_FOUND_MSG = "User @{username} not found."
USER_ADDED_TO_WHITELIST_MSG = "User @{username} added to whitelist."
TIME_LIMIT_SET_MSG = "Time limit set to {hours} hours."
TIME_LIMIT_INPUT_MSG = "Please enter the time in hours (e.g., 12 or 12H)."
AN_ERROR_OCCURRED_MSG = "An error occurred: {error}"
NO_RESULTS_FOUND_MSG = "No results found."
HERE_ARE_SEARCH_RESULTS_MSG = "Here are the search results for '{text}':\n\n{result}"
INLINE_SEARCH_UNAVAILABLE_TITLE = "Inline search unavailable"
INLINE_SEARCH_UNAVAILABLE_MSG = "Please open the bot and press Search to use inline mode."
INLINE_SEARCH_NO_LOGIN_TITLE = "Please log in to use inline search"
INLINE_SEARCH_NO_LOGIN_MSG = "Please log in to the bot to use inline search."
NO_FILES_FOUND_TITLE = "No files found"
NO_MATCHING_FILES_MSG = "No matching files found in your Google Drive."
NOTIFY_COMPLETION_ON = "🔕 Don't notify completion"
NOTIFY_COMPLETION_OFF = "🛎️ Notify completion"
CANCEL_BUTTON = "❎ Cancel"
FILE_SIZE_MSG = "File size: {size}"
FAILED_TO_GET_FILE_SIZE_MSG = "Failed to get file size: {error}"
FOLDER_SIZE_MSG = "Folder size: {size}"
FAILED_TO_GET_FOLDER_INFO_MSG = "Failed to get folder info: {error}"
ACCESS_DENIED_ACTION_MSG = "Access denied. You do not have permission to perform this action."
ACCESS_EXPIRY_REMINDER_MSG = "Your access will expire in 30 minutes. Contact *Team CloudVerse* for help"
STARTING_WEB_INTERFACE_MSG = "Starting web interface..."
WEB_INTERFACE_STARTED_SUCCESS_MSG = "✅ Web interface started successfully"
FAILED_TO_START_WEB_INTERFACE_MSG = "❌ Failed to start web interface: {error}"
BOT_CONTINUE_NO_WEB_INTERFACE_MSG = "Bot will continue without web interface"
INITIALIZING_DATABASE_MSG = "Initializing database..."
BUILDING_BOT_APPLICATION_MSG = "Building bot application..."
SHUTTING_DOWN_BOT_MSG = "Shutting down bot gracefully..."
SHUTDOWN_COMPLETE_MSG = "Shutdown complete."
RECEIVED_SIGNAL_MSG = "Received signal {sig}. Exiting..."
BOT_STOPPED_BY_USER_MSG = "Bot stopped by user."

if BOT_TOKEN is None:
    raise ValueError("BOT_TOKEN is not set in config.")
if GROUP_CHAT_ID is None:
    raise ValueError("GROUP_CHAT_ID is not set in config.")
if SUPER_ADMIN_ID is None:
    raise ValueError("SUPER_ADMIN_ID is not set in config.")

# --- Global Error Handler ---
async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uncaught errors and notify the user."""
    try:
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=ERROR_OCCURRED_MSG)
    except Exception:
        pass

async def set_bot_commands(app):
    """Set available bot commands for the user interface."""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("login", "Login to Google Drive"),
        BotCommand("profile", "View account profile"),
        BotCommand("filemanager", "Open file manager"),
        BotCommand("storage", "View storage details"),
        BotCommand("recyclebin", "Open recycle bin"),
        BotCommand("settings", "Open settings"),
        BotCommand("message", "Message developer"),
        BotCommand("privacy", "Privacy policy"),
    ]
    await app.bot.set_my_commands(commands)

async def notify_access_expired(update, telegram_id):
    """Notify user if their access has expired."""
    await update.effective_chat.send_message(
        ACCESS_EXPIRED_MSG
    )

access_filter = filters.BaseFilter() # This filter is no longer used as access_required is imported directly

@handle_errors
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Entry point for /start command. Handles user access and menu display."""
    if ctx.user_data is None:
        ctx.user_data = {}
    if not hasattr(update, 'effective_user') or update.effective_user is None:
        if update.message and hasattr(update.message, 'reply_text'):
            await update.message.reply_text(USER_INFO_NOT_FOUND_MSG)
            return
        elif hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(USER_INFO_NOT_FOUND_MSG)
            return
    else:
        telegram_id = update.effective_user.id
        username = getattr(update.effective_user, 'username', '')
        first_name = getattr(update.effective_user, 'first_name', '')
        last_name = getattr(update.effective_user, 'last_name', '') or ''
    if is_admin(telegram_id) or is_whitelisted(telegram_id):
        await menu_start(update, ctx)
    else:
        add_pending_user(telegram_id, username, first_name, last_name)
        access_pending_msg = ACCESS_PENDING_MSG
        if update.message:
            await update.message.reply_text(access_pending_msg, parse_mode='Markdown')
        elif hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(access_pending_msg, parse_mode='Markdown')
        await post_access_request_to_group(ctx, telegram_id, username, first_name, last_name)

@handle_errors
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    if "state" not in ctx.user_data or not isinstance(ctx.user_data["state"], UserState):
        ctx.user_data["state"] = UserState()
    user_state: UserState = ctx.user_data["state"]
    if update.message and update.message.from_user:
        telegram_id = update.message.from_user.id
    else:
        return
    service = get_drive_service(telegram_id) if telegram_id else None
    text = update.message.text if update.message else ''

    # Handle message to developer
    if user_state.is_state(UserStateEnum.EXPECTING_DEV_MESSAGE):
        from .MessageForDeveloper import send_to_developer
        await send_to_developer(update, ctx)
        user_state.reset()
        return

    if user_state.is_state(UserStateEnum.EXPECTING_DELETE_CONFIRMATION):
        file = user_state.data.get("file")
        if file is not None:
            if isinstance(text, str) and text.strip().lower() == "delete":
                service = get_drive_service(telegram_id)
                if service:
                    service.files().delete(fileId=file["id"]).execute()
                    if update.message:
                        await update.message.reply_text(f"{'Folder' if file['mimeType'] == 'application/vnd.google-apps.folder' else 'File'} : {file['name']} permanently deleted.")
                else:
                    if update.message:
                        await update.message.reply_text(SERVICE_UNAVAILABLE_MSG)
            else:
                if update.message:
                    await update.message.reply_text(PERMANENT_DELETE_CANCELLED_MSG)
        else:
            if update.message:
                await update.message.reply_text("No file information found for deletion.")
        user_state.reset()
        return
    elif user_state.is_state(UserStateEnum.EXPECTING_APPROVAL_MESSAGE):
        data = user_state.data
        user_id = data.get("user_id")
        action = data.get("action")
        if user_id is not None:
            message = text if text else "Your request has been submitted for approval." + ("approved." if action == "approve" else "rejected.")
            await ctx.bot.send_message(chat_id=user_id, text=message)
            if update.message:
                await update.message.reply_text(MESSAGE_SENT_TO_USER_MSG)
        else:
            if update.message:
                await update.message.reply_text("User ID not found for approval message.")
        user_state.reset()
        return
    elif user_state.is_state(UserStateEnum.EXPECTING_CODE):
        flow = user_state.data.get("flow")
        try:
            if flow is not None:
                if isinstance(text, str):
                    flow.fetch_token(code=text.strip())
                creds = flow.credentials
                from googleapiclient.discovery import build
                temp_service = build("drive", "v3", credentials=creds)
                user_info = temp_service.about().get(fields="user").execute()
                email = user_info["user"]["emailAddress"]
                username = getattr(update.effective_user, 'username', '') if hasattr(update, 'effective_user') and update.effective_user else ''
            else:
                if update.message:
                    await update.message.reply_text("No authentication flow found. Please try logging in again.")
        except Exception as e:
            if update.message:
                await update.message.reply_text(LOGIN_FAILED_MSG.format(error=str(e)))
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(LOGIN_FAILED_MSG.format(error=str(e)))
        finally:
            user_state.reset()
        return
    elif user_state.is_state(UserStateEnum.EXPECTING_LOGOUT_CONFIRMATION):
        confirmation = user_state.data.get("confirmation")
        if isinstance(text, str) and text.strip() == confirmation:
            user_state.reset()
        else:
            await update.message.reply_text(LOGOUT_CANCELLED_MSG)
            user_state.reset()
        return
    elif service and user_state.state in [
        UserStateEnum.EXPECTING_ADMIN_USERNAME,
        UserStateEnum.EXPECTING_WHITELIST_USERNAME,
        UserStateEnum.EXPECTING_LIMIT_HOURS,
        UserStateEnum.EXPECTING_PARALLEL_UPLOADS
    ]:
        action = user_state.state
        try:
            if action == UserStateEnum.EXPECTING_ADMIN_USERNAME:
                if not is_super_admin(telegram_id):
                    await update.message.reply_text(ACCESS_DENIED_SUPER_ADMIN_MSG)
                    user_state.reset()
                    return
                username = text.strip('@') if isinstance(text, str) else ''
                user_id = get_user_id_by_username(username)
                if user_id:
                    add_admin(user_id)
                    await update.message.reply_text(USER_ADDED_AS_ADMIN_MSG.format(username=username))
                else:
                    await update.message.reply_text(USER_NOT_FOUND_MSG.format(username=username))
                user_state.reset()
                return
            elif action == UserStateEnum.EXPECTING_WHITELIST_USERNAME:
                username = text.strip('@') if isinstance(text, str) else ''
                user_id = get_user_id_by_username(username)
                if user_id:
                    add_whitelist(user_id)
                    await update.message.reply_text(USER_ADDED_TO_WHITELIST_MSG.format(username=username))
                else:
                    await update.message.reply_text(USER_NOT_FOUND_MSG.format(username=username))
                user_state.reset()
                return
            elif action == UserStateEnum.EXPECTING_LIMIT_HOURS:
                user_id = user_state.data.get("user_id")
                hours = None
                if isinstance(text, str):
                    text_clean = text.strip()
                    if text_clean.endswith('H'):
                        hours_str = text_clean[:-1]
                        if hours_str.isdigit():
                            hours = int(hours_str)
                    elif text_clean.isdigit():
                        hours = int(text_clean)
                if hours is not None:
                    from datetime import datetime, timedelta
                    expiration_time = (datetime.now() + timedelta(hours=hours)).isoformat()
                    set_whitelist_expiration(user_id, expiration_time)
                    await update.message.reply_text(TIME_LIMIT_SET_MSG.format(hours=hours))
                    user_state.reset()
                    return
                else:
                    await update.message.reply_text(TIME_LIMIT_INPUT_MSG)
            elif action == UserStateEnum.EXPECTING_PARALLEL_UPLOADS:
                if isinstance(text, str) and text.isdigit():
                    num = int(text)
                    if 1 <= num <= 5:
                        await update.message.reply_text(PARALLEL_UPLOAD_LIMIT_UPDATED_MSG)
                        user_state.reset()
                        return
                    else:
                        await update.message.reply_text(PARALLEL_UPLOAD_LIMIT_RANGE_MSG)
        except Exception as e:
            await update.message.reply_text(AN_ERROR_OCCURRED_MSG.format(error=str(e)))
        # No explicit return here, so log at the end
    elif await is_url(text) and service:
        await handle_url(update, ctx)
        return
    # If none of the above, log that the message was not handled by a specific state

@handle_errors
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads."""
    await handle_file_upload(update, ctx)

@handle_errors
async def handle_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle URL uploads."""
    await handle_url_upload(update, ctx)

@handle_errors
async def toggle_notify_completion(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Toggle notification for file completion."""
    if ctx.user_data is None:
        ctx.user_data = {}
    current = ctx.user_data.get('notify_completion', True)
    ctx.user_data['notify_completion'] = not current
    btn_text = NOTIFY_COMPLETION_ON if ctx.user_data['notify_completion'] else NOTIFY_COMPLETION_OFF
    if update.callback_query and hasattr(update.callback_query, 'edit_message_reply_markup'):
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(btn_text, callback_data='toggle_notify_completion'),
                InlineKeyboardButton(CANCEL_BUTTON, callback_data='cancel_upload')
            ]
        ])
        await update.callback_query.edit_message_reply_markup(reply_markup=markup)
    if update.callback_query and hasattr(update.callback_query, 'answer'):
        await update.callback_query.answer()

@handle_errors
async def handle_refresh_requests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle callback for refreshing access control requests."""
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.edit_message_text(ACCESS_DENIED_ACTION_MSG)
        return
    ctx.user_data["requests_page"] = 0

@handle_errors
@access_required
async def handle_recyclebin_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /recyclebin command."""
    if ctx.user_data is None:
        ctx.user_data = {}
    from .RecycleBin import handle_bin
    return await handle_bin(update, ctx)

@handle_errors
@access_required
async def handle_message_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /message command."""
    if ctx.user_data is None:
        ctx.user_data = {}
    from .MessageForDeveloper import handle_cloudverse_support
    return await handle_cloudverse_support(update, ctx)

@handle_errors
@access_required
async def handle_privacy_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /privacy command."""
    if ctx.user_data is None:
        ctx.user_data = {}
    from .TermsAndCondition import show_terms_and_conditions
    return await show_terms_and_conditions(update, ctx)

@handle_errors
@access_required
async def handle_terms_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /terms command."""
    if ctx.user_data is None:
        ctx.user_data = {}
    from .TermsAndCondition import show_terms_and_conditions
    return await show_terms_and_conditions(update, ctx)

@handle_errors
@access_required
async def handle_storage_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /storage command."""
    if ctx.user_data is None:
        ctx.user_data = {}
    from .StorageDetails import handle_storage
    return await handle_storage(update, ctx)

def tail_log(log_file, n=30):
    """Read the last n lines of a log file."""
    if not os.path.exists(log_file):
        return []
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    return lines[-n:]

def terminal_dashboard():
    """Start a terminal dashboard for real-time logging."""
    def _dashboard(stdscr):
        log_file = "bot.log"
        curses.curs_set(0)
        stdscr.nodelay(True)
        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            logs = tail_log(log_file, height - 1)
            for idx, line in enumerate(logs[-(height - 1):]):
                stdscr.addstr(idx, 0, line[:width-1])
            stdscr.refresh()
            time.sleep(1)
    curses.wrapper(_dashboard)

async def access_expiry_reminder_task(app):
    """Background task to remind users of access expiry."""
    while True:
        try:
            users = get_whitelist_expiring_soon(30)
            for user in users:
                try:
                    await app.bot.send_message(
                        chat_id=user['telegram_id'],
                        text=ACCESS_EXPIRY_REMINDER_MSG,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    pass
        except Exception as e:
            pass
        await asyncio.sleep(300)

def main():
    """Main function to run the bot and register all handlers."""
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    # --- Refactored Handler Registration ---
    handler_defs = [
        ("command", ("start", start)),
        ("command", ("login", login)),
        ("command", ("profile", handle_profile)),
        ("command", ("filemanager", handle_file_manager)),
        ("command", ("storage", handle_storage_command)),
        ("command", ("recyclebin", handle_recyclebin_command)),
        ("command", ("settings", handle_settings)),
        ("command", ("message", handle_message_command)),
        ("command", ("terms", handle_terms_command)),
        ("command", ("privacy", handle_privacy_command)),
        ("callback", (handle_menu, r"^(FILE_MGR|SEARCH|PROFILE|STORAGE|BIN|SETTINGS|MESSAGE_DEV|PRIVACY|ACCESS|back|cancel)$")),
        ("callback", (handle_file_manager, r"^FILE_MGR$")),
        ("callback", (handle_folder_navigation, r"^(folder:.*|back_folder|next_page:.*|prev_page:.*|switch_account:.*)$")),
        ("callback", (handle_file_selection, r"^(file:.*|folder_options:.*)$")),
        ("callback", (handle_file_actions, r"^(rename_file:.*|delete_file:.*|confirm_delete_file:.*|copy_link:.*|rename_folder:.*|delete_folder:.*|confirm_delete_folder:.*|toggle_sharing:.*|new_folder:.*|back_to_folder)$")),
        ("callback", (handle_profile, r"^PROFILE$")),
        ("callback", (handle_storage, r"^STORAGE$")),
        ("callback", (refresh_storage, r"^refresh_storage$")),
        ("callback", (handle_bin, r"^BIN$")),
        ("callback", (handle_bin_navigation, r"^(bin_next_page|bin_prev_page|bin_item:.*|restore:.*|perm_delete:.*|confirm_empty_bin|back_to_bin|empty_bin)$")),
        ("callback", (handle_settings, r"^SETTINGS$")),
        ("callback", (login, r"^login$")),
        ("callback", (logout, r"^logout$")),
        ("callback", (handle_logout_action, r"^(logout_account|logout_specific:.*|logout_all_prompt)$")),
        ("callback", (switch_account_menu, r"^switch_account$")),
        ("callback", (set_primary, r"^set_primary:.*$")),
        ("callback", (update_def_location, r"^update_def_location$")),
        ("callback", (update_parallel_uploads, r"^update_parallel_uploads$")),
        ("callback", (handle_cloudverse_support, r"^CLOUDVERSE_SUPPORT$")),
        ("callback", (show_terms_and_conditions, r"^TERMS$")),
        ("callback", (handle_access_control, r"^ACCESS$")),
        ("callback", (manage_admins, r"^manage_admins$")),
        ("callback", (manage_whitelist, r"^manage_whitelist$")),
        ("callback", (manage_blacklist, r"^manage_blacklist$")),
        ("callback", (handle_blacklist_pagination, r"^(blacklist_prev_page|blacklist_next_page)$")),
        ("callback", (handle_unrestrict_blacklist, r"^unrestrict_blacklist:.*$")),
        ("callback", (handle_edit_blacklist, r"^edit_blacklist:.*$")),
        ("callback", (handle_access_actions, r"^(manage_admins|manage_whitelist|add_admin|remove_admin:.*|add_whitelist|remove_whitelist:.*|set_limit:.*|remove_limit:.*|promote_admin:.*|demote_admin:.*|admin_prev_page|admin_next_page|whitelist_prev_page|whitelist_next_page|requests_prev_page|requests_next_page|back_to_access|back_to_whitelist)$")),
        ("callback", (cancel_upload, r"^cancel_upload$")),
        ("callback", (search_next_page, r"^search_next_page$")),
        ("callback", (search_prev_page, r"^search_prev_page$")),
        ("callback", (handle_search_item, r"^search_item:.*$")),
        ("callback", (handle_access_request, r"^access_limit:.*$")),
        ("callback", (handle_access_request, r"^access_approve:.*$")),
        ("callback", (handle_access_request, r"^access_reject:.*$")),
        ("callback", (handle_access_request, r"^access_skip_approve$")),
        ("callback", (handle_access_request, r"^access_skip_reject$")),
        ("callback", (handle_access_request, r"^cancel_limit_setting$")),
        ("callback", (toggle_notify_completion, r"^toggle_notify_completion$")),
        ("callback", (handle_broadcast_message, r"^broadcast_message$")),
        ("callback", (handle_broadcast_approval, r"^(super_approve_broadcast|approve_broadcast|reject_broadcast):.*$")),
        ("callback", (handle_analytics_report, r"^analytics_report$")),
        ("callback", (handle_analytics_report_type, r"^analytics_(professional|dashboard|minimalist)$")),
        ("callback", (handle_refresh_requests, r"^refresh_requests$")),
        ("callback", (handle_authenticate_session, r"^authenticate_session$")),
        ("callback", (handle_delete_records, r"^delete_records$")),
        ("callback", (handle_delete_records, r"^delete_records_prev_page$")),
        ("callback", (handle_delete_records, r"^delete_records_next_page$")),
        ("callback", (handle_delete_user_confirm, r"^delete_user_confirm:.*$")),
        ("message", (filters.TEXT & filters.Chat(int(GROUP_CHAT_ID)), handle_access_message)),
        ("message", (filters.REPLY, handle_developer_reply)),
        ("message", (filters.TEXT & ~filters.COMMAND & ~filters.Chat(int(GROUP_CHAT_ID)), handle_access_message)),
        ("message", (filters.TEXT & ~filters.COMMAND & access_filter, handle_broadcast_media_message)),
        ("message", (filters.PHOTO & access_filter, handle_broadcast_media_message)),
        ("message", (filters.VIDEO & access_filter, handle_broadcast_media_message)),
        ("message", (filters.Document.ALL & access_filter, handle_broadcast_media_message)),
        ("message", (filters.AUDIO & access_filter, handle_broadcast_media_message)),
        ("message", (filters.VOICE & access_filter, handle_broadcast_media_message)),
        ("message", (filters.TEXT & ~filters.COMMAND & access_filter, handle_message)),
        ("message", (filters.Document.ALL & access_filter, handle_file)),
        ("inline", handle_inline_query),
        ("callback", (handle_reply_callback, r"^(reply_to_user:|reply_to_dev:).*$")),
        ("message", (filters.TEXT & filters.ChatType.PRIVATE, handle_user_reply)),
        ("message", (filters.TEXT & filters.Chat(int(GROUP_CHAT_ID)), handle_developer_reply)),
        ("message", (filters.TEXT & filters.ChatType.PRIVATE, handle_telethon_auth_message)),
        ("message", (filters.TEXT & filters.ChatType.PRIVATE, handle_delete_user_typein)),
        ("callback", (handle_delete_user_typein_prompt, r"^delete_user_typein:.*$")),
        ("callback", (handle_file_size, r"^file_size:.*$")),
        ("callback", (handle_folder_size, r"^folder_size:.*$")),
    ]
    for htype, args in handler_defs:
        if htype == "command":
            app.add_handler(CommandHandler(*args))
        elif htype == "callback":
            app.add_handler(CallbackQueryHandler(*args))
        elif htype == "message":
            app.add_handler(MessageHandler(*args))
        elif htype == "inline":
            app.add_handler(InlineQueryHandler(args))
    # --- End Refactored Handler Registration ---
    async def setup_commands(application):
        try:
            await set_bot_commands(application)
            # Schedule the access_expiry_reminder_task after bot is initialized
            asyncio.create_task(access_expiry_reminder_task(application))
            # Schedule the expired user update and unban tasks using AccessManager
            asyncio.create_task(mark_expired_users_and_notify(application))
            asyncio.create_task(unban_expired_temporary_blacklist_and_notify(application))
        except Exception as e:
            pass
    app.post_init = setup_commands
    # Remove: loop = asyncio.get_event_loop(); loop.create_task(access_expiry_reminder_task(app))
    # Remove deprecated event loop management code
    try:
        pass
    except ValueError as e:
        pass
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    async def shutdown():
        try:
            # logger.info("[Shutdown] Initiating graceful shutdown...") # Removed logger
            # logger.info(SHUTTING_DOWN_BOT_MSG) # Removed logger
            await app.stop()
            # logger.info("[Shutdown] Bot stopped successfully.") # Removed logger
        except Exception as e:
            pass
        finally:
            # if hasattr(logger, 'handlers'): # Removed logger
            #     for handler in logger.handlers: # Removed logger
            #         handler.flush() # Removed logger
            # logger.info(SHUTDOWN_COMPLETE_MSG) # Removed logger
            pass
    def handle_signal(sig, frame):
        # logger.info(f"[Shutdown] Received signal {sig}. Exiting...") # Removed logger
        # logger.info(RECEIVED_SIGNAL_MSG.format(sig=sig)) # Removed logger
        loop.create_task(shutdown())
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    try:
        app.run_polling()
    except (KeyboardInterrupt, SystemExit):
        # logger.info("[Shutdown] Bot stopped by user.") # Removed logger
        # logger.info(BOT_STOPPED_BY_USER_MSG) # Removed logger
        pass
    except Exception as e:
        # logger.error(f"[Startup] Unhandled exception: {e}", exc_info=True) # Removed logger
        # logger.info(f"Unhandled exception: {e}") # Removed logger
        pass

if __name__ == "__main__":
    executor = ThreadPoolExecutor(max_workers=5)
    main()