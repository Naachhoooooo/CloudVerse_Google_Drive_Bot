import tempfile
import os
import asyncio
import re
import requests
from googleapiclient.http import MediaFileUpload
from .Settings import handle_settings, login, logout, handle_logout_action, switch_account_menu, set_primary, update_def_location, update_parallel_uploads
from .MessageForDeveloper import handle_message_dev, send_to_developer, handle_developer_reply, handle_reply_callback, handle_user_reply
from .TermsAndCondition import show_terms_and_conditions
from .config import BOT_TOKEN, GROUP_CHAT_ID, SUPER_ADMIN_ID
from .database import init_db, is_admin, is_whitelisted, add_admin, add_whitelist, add_pending_user, get_user_id_by_username, set_whitelist_expiration, is_super_admin
from .drive import get_drive_service, search_files, create_folder, rename_file, get_storage_info
from .MainMenu import start as menu_start, handle_menu
from .FileManager import handle_file_manager, handle_folder_navigation, handle_file_selection, handle_file_actions
from .AccountProfile import handle_profile
from .StorageDetails import handle_storage, refresh_storage
from .RecycleBin import handle_bin, handle_bin_navigation
from .AccessControl import handle_access_control, manage_requests, handle_request_action, handle_access_actions, skip_message, post_access_request_to_group, handle_access_request, handle_access_message, manage_admins, manage_whitelist, manage_blacklist, handle_blacklist_pagination, handle_unrestrict_blacklist, handle_edit_blacklist
from .Broadcast import handle_broadcast_message, handle_broadcast_media_message, handle_broadcast_approval
from .AnalyticsReport import handle_analytics_report, handle_analytics_report_type
from .Logger import log_upload, log_bandwidth, log_error, get_logger
logger = get_logger()
from .Utilities import format_size, is_url
from .Search import search_next_page, search_prev_page, handle_search_item, handle_inline_query
from .Uploader import cancel_upload, handle_file_upload, handle_url_upload
from .AdminControls import handle_live_terminal_logs, handle_authenticate_session, handle_telethon_auth_message
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

load_dotenv()

# Ensure BOT_TOKEN and GROUP_CHAT_ID are not None
if BOT_TOKEN is None:
    raise ValueError("BOT_TOKEN is not set in config.")
if GROUP_CHAT_ID is None:
    raise ValueError("GROUP_CHAT_ID is not set in config.")
if SUPER_ADMIN_ID is None:
    raise ValueError("SUPER_ADMIN_ID is not set in config.")

# Remove any direct Application() instantiation (none found, but ensure only ApplicationBuilder is used)
# The following is already correct:
# app = ApplicationBuilder().token(BOT_TOKEN).build()

# Register a global error handler after all handlers are added
from telegram.ext import ContextTypes
async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    log_error(context.error, context="global_error_handler")
    # Optionally, send a message to the user
    try:
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred. Please try again or use /cancel.")
    except Exception:
        pass
# The following line is already correct:
# app.add_error_handler(error_handler)

async def set_bot_commands(app):
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

class AccessFilter(filters.BaseFilter):
    def filter(self, update):
        telegram_id = update.effective_user.id
        if is_admin(telegram_id) or is_whitelisted(telegram_id):
            return True
        else:
            asyncio.create_task(notify_access_expired(update, telegram_id))
            return False

async def notify_access_expired(update, telegram_id):
    await update.effective_chat.send_message(
        "Your access to the bot has expired. Please request access again by sending /start."
    )

access_filter = AccessFilter()

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Ensure ctx.user_data is always a dict
    if ctx.user_data is None:
        ctx.user_data = {}
    # Defensive fix for update.effective_user.id
    if not hasattr(update, 'effective_user') or update.effective_user is None:
        if update.message and hasattr(update.message, 'reply_text'):
            await update.message.reply_text("User info not found. Please try again or contact support.")
            return
        elif hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text("User info not found. Please try again or contact support.")
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
        if update.message:
            await update.message.reply_text("Your request has been submitted for approval.")
        elif hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text("Your request has been submitted for approval.")
        # Post to group topic using AccessControl
        await post_access_request_to_group(ctx, telegram_id, username, first_name, last_name)

# Decorator for access control
from functools import wraps

def access_required(handler):
    @wraps(handler)
    async def wrapper(update, ctx):
        telegram_id = None
        if hasattr(update, 'effective_user') and update.effective_user:
            telegram_id = update.effective_user.id
        elif hasattr(update, 'message') and update.message and hasattr(update.message, 'from_user') and update.message.from_user:
            telegram_id = update.message.from_user.id
        elif hasattr(update, 'callback_query') and update.callback_query and hasattr(update.callback_query, 'from_user') and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
        if not (telegram_id and (is_admin(telegram_id) or is_whitelisted(telegram_id))):
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.answer("Access denied. You do not have permission to perform this action.")
            elif hasattr(update, 'message') and update.message:
                await update.message.reply_text("Access denied. You do not have permission to perform this action.")
            return
        return await handler(update, ctx)
    return wrapper

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Ensure ctx.user_data is always a dict
    if ctx.user_data is None:
        ctx.user_data = {}
    # Defensive fix for update.message.from_user.id
    if update.message and update.message.from_user:
        telegram_id = update.message.from_user.id
    else:
        return
    service = get_drive_service(telegram_id) if telegram_id else None
    text = update.message.text if update.message else ''

    # Add this block to handle message to developer
    if ctx.user_data.get("expecting_dev_message"):
        from .MessageForDeveloper import send_to_developer
        await send_to_developer(update, ctx)
        return

    if ctx.user_data and "expecting_delete_confirmation" in ctx.user_data:
        file = ctx.user_data.pop("expecting_delete_confirmation")
        if isinstance(text, str) and text.strip().lower() == "delete":
            service = get_drive_service(telegram_id)
            if service:
                service.files().delete(fileId=file["id"]).execute()
                if update.message:
                    await update.message.reply_text(f"{'Folder' if file['mimeType'] == 'application/vnd.google-apps.folder' else 'File'} : {file['name']} permanently deleted.")
            else:
                if update.message:
                    await update.message.reply_text("Service unavailable. Please try again later.")
        else:
            if update.message:
                await update.message.reply_text("Permanent delete cancelled.")
    elif ctx.user_data and "expecting_approval_message" in ctx.user_data:
        data = ctx.user_data.pop("expecting_approval_message")
        user_id = data["user_id"]
        action = data["action"]
        message = text if text else "Your request has been submitted for approval." + ("approved." if action == "approve" else "rejected.")
        await ctx.bot.send_message(chat_id=user_id, text=message)
        if update.message:
            await update.message.reply_text("Message sent to user.")
    elif ctx.user_data.get("expecting_code"):
        flow = ctx.user_data["flow"]
        try:
            if isinstance(text, str):
                flow.fetch_token(code=text.strip())
            creds = flow.credentials
            from googleapiclient.discovery import build
            temp_service = build("drive", "v3", credentials=creds)
            user_info = temp_service.about().get(fields="user").execute()
            email = user_info["user"]["emailAddress"]
            username = getattr(update.effective_user, 'username', '') if hasattr(update, 'effective_user') and update.effective_user else ''
            # store_credentials(telegram_id, email, creds.to_json(), not get_primary_account(telegram_id), username=username) # This function is removed
            # await update.message.reply_text(WELCOME_MENU) # This function is removed
            # ctx.user_data["current_account"] = email # This function is removed
            logger.info(f"User logged in with email {email}", extra={"user_id": telegram_id})
            # The following lines are removed as per the edit hint
            # else:
            #     if update.message:
            #         await update.message.reply_text("Max accounts (3) reached.")
            #     elif hasattr(update, 'callback_query') and update.callback_query:
            #         await update.callback_query.edit_message_text("Max accounts (3) reached.")
        except Exception as e:
            if update.message:
                await update.message.reply_text(f"Login failed: {str(e)}")
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(f"Login failed: {str(e)}")
            logger.error(f"Login failed: {str(e)}", extra={"user_id": telegram_id})
        finally:
            ctx.user_data["expecting_code"] = False
            if "flow" in ctx.user_data:
                del ctx.user_data["flow"]
    elif ctx.user_data.get("expecting_logout_confirmation"):
        confirmation = ctx.user_data["expecting_logout_confirmation"]
        if isinstance(text, str) and text.strip() == confirmation:
            # remove_account(telegram_id) # This function is removed
            # await update.message.reply_text(LOGOUT_SUCCESS) # This function is removed
            # email = confirmation.split("Logout ")[1] # This function is removed
            # remove_account(telegram_id, email) # This function is removed
            # await update.message.reply_text(LOGOUT_SUCCESS) # This function is removed
            ctx.user_data.pop("expecting_logout_confirmation")
        else:
            await update.message.reply_text("Logout cancelled.")
            ctx.user_data.pop("expecting_logout_confirmation")
    elif service and (action := ctx.user_data.get("next_action")):
        # settings = get_user_settings(telegram_id) # This function is removed
        try:
            if action == "search_by_name":
                files, next_token = search_files(service, text)
                ctx.user_data["search_results"] = files
                ctx.user_data["search_next_token"] = next_token
                ctx.user_data["search_prev_token"] = None
                buttons = [
                    [InlineKeyboardButton(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}", callback_data=f"search_item:{f['id']}:{f['mimeType']}")]
                    for f in files
                ]
                if next_token:
                    buttons.append([InlineKeyboardButton("Next ▶️", callback_data="search_next_page")])
                buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back")])
                result = "\n".join(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}" for f in files) or "No results found."
                await update.message.reply_text(f"Here are the search results for '{text}':\n\n{result}", reply_markup=InlineKeyboardMarkup(buttons))
            elif action.startswith("rename_file:"):
                file_id = action.split("rename_file:")[1]
                rename_file(service, file_id, text)
                await update.message.reply_text("File renamed successfully.")
                logger.info(f"File {file_id} renamed to {text}", extra={"user_id": telegram_id})
            elif action.startswith("rename_folder:"):
                folder_id = action.split("rename_folder:")[1]
                rename_file(service, folder_id, text)
                await update.message.reply_text("Folder renamed successfully.")
                logger.info(f"Folder {folder_id} renamed to {text}", extra={"user_id": telegram_id})
            elif action.startswith("create_folder:"):
                parent_id = action.split("create_folder:")[1]
                folder = create_folder(service, text, parent_id)
                await update.message.reply_text(f"Folder created successfully. ID: {folder['id']}")
                logger.info(f"Folder {folder['id']} created with name {text}", extra={"user_id": telegram_id})
            elif action == "set_parallel_uploads":
                if isinstance(text, str) and text.isdigit():
                    num = int(text)
                    if 1 <= num <= 5:
                        # update_user_settings(telegram_id, num) # This function is removed
                        await update.message.reply_text("Parallel upload limit updated.")
                        logger.info(f"Parallel uploads set to {num}", extra={"user_id": telegram_id})
                    else:
                        await update.message.reply_text("Please enter a number between 1 and 5.")
            elif action == "add_admin_username":
                if not is_super_admin(telegram_id):
                    await update.message.reply_text("Access denied. Only super admins can add new admins.")
                    ctx.user_data["next_action"] = None
                    return
                if isinstance(text, str):
                    username = text.strip('@')
                else:
                    username = ''
                user_id = get_user_id_by_username(username)
                if user_id:
                    add_admin(user_id)
                    await update.message.reply_text(f"User @{username} added as admin.")
                    logger.info(f"Admin @{username} added", extra={"user_id": telegram_id})
                else:
                    await update.message.reply_text(f"User @{username} not found.")
                ctx.user_data["next_action"] = None
            elif action == "add_whitelist_username":
                if isinstance(text, str):
                    username = text.strip('@')
                else:
                    username = ''
                user_id = get_user_id_by_username(username)
                if user_id:
                    add_whitelist(user_id)
                    await update.message.reply_text(f"User @{username} added to whitelist.")
                    logger.info(f"User @{username} added to whitelist", extra={"user_id": telegram_id})
                else:
                    await update.message.reply_text(f"User @{username} not found.")
                ctx.user_data["next_action"] = None
            elif action.startswith("set_limit_hours:"):
                user_id = action.split("set_limit_hours:")[1]
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
                    await update.message.reply_text(f"Time limit set to {hours} hours.")
                else:
                    await update.message.reply_text("Please enter the time in hours (e.g., 12 or 12H).")
        except Exception as e:
            await update.message.reply_text(f"An error occurred: {str(e)}")
            logger.error(f"Action {action} failed: {str(e)}", extra={"user_id": telegram_id})
        if action not in ["add_admin_username", "add_whitelist_username", "set_limit_hours"]:
            ctx.user_data["next_action"] = None
    elif await is_url(text) and service:
        await handle_url(update, ctx)

async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await handle_file_upload(update, ctx)

async def handle_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await handle_url_upload(update, ctx)

async def handle_inline_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    inline_query = getattr(update, 'inline_query', None)
    if not inline_query:
        return
    query = getattr(inline_query, 'query', '')
    user = getattr(inline_query, 'from_user', None)
    user_id = getattr(user, 'id', None)
    if not user_id:
        return
    # Restrict inline search to only when user is in SEARCH state
    user_state = ctx.user_data.get('state') if ctx.user_data else None
    if user_state != 'SEARCH':
        await inline_query.answer([
            InlineQueryResultArticle(
                id='not_in_search',
                title='Inline search unavailable',
                input_message_content=InputTextMessageContent('Please open the bot and press Search to use inline mode.')
            )
        ], cache_time=1)
        return
    service = get_drive_service(user_id)
    if not service:
        await inline_query.answer([
            InlineQueryResultArticle(
                id='no_login',
                title='Please log in to use inline search',
                input_message_content=InputTextMessageContent('Please log in to the bot to use inline search.')
            )
        ], cache_time=1)
        return
    files, _ = search_files(service, query)
    results = []
    for f in files[:10]:
        file_url = f"https://drive.google.com/file/d/{f['id']}/view"
        results.append(
            InlineQueryResultArticle(
                id=f["id"],
                title=f["name"],
                description=f.get("mimeType", ""),
                input_message_content=InputTextMessageContent(f"Google Drive file: {f['name']}\n{file_url}")
            )
        )
    if not results:
        results.append(
            InlineQueryResultArticle(
                id='no_results',
                title='No files found',
                input_message_content=InputTextMessageContent('No matching files found in your Google Drive.')
            )
        )
    await inline_query.answer(results, cache_time=1)

# Add a callback handler for toggling notify completion
async def toggle_notify_completion(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    current = ctx.user_data.get('notify_completion', True)
    ctx.user_data['notify_completion'] = not current
    btn_text = '🔕 Don\'t notify completion' if ctx.user_data['notify_completion'] else '🛎️ Notify completion'
    if update.callback_query and hasattr(update.callback_query, 'edit_message_reply_markup'):
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(btn_text, callback_data='toggle_notify_completion'),
                InlineKeyboardButton('❎ Cancel', callback_data='cancel_upload')
            ]
        ])
        await update.callback_query.edit_message_reply_markup(reply_markup=markup)
    if update.callback_query and hasattr(update.callback_query, 'answer'):
        await update.callback_query.answer()

# Add missing handlers for file size and folder size
async def handle_file_size(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not q.data or not q.data.startswith("file_size:"):
        return
    file_id = q.data.split(":")[1]
    service = get_drive_service(telegram_id)
    if not service:
        await q.edit_message_text("Service unavailable. Please try again later.")
        return
    try:
        file = service.files().get(fileId=file_id, fields="name,size").execute()
        size = int(file.get('size', 0))
        size_str = format_size(size)
        await q.edit_message_text(f"File size: {size_str}")
    except Exception as e:
        await q.edit_message_text(f"Failed to get file size: {str(e)}")

async def handle_folder_size(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not q.data or not q.data.startswith("folder_size:"):
        return
    folder_id = q.data.split(":")[1]
    service = get_drive_service(telegram_id)
    if not service:
        await q.edit_message_text("Service unavailable. Please try again later.")
        return
    try:
        folder = service.files().get(fileId=folder_id, fields="name").execute()
        # Note: Google Drive API doesn't provide folder size directly
        # This would require recursive calculation which is expensive
        size_str = format_size(0) # Placeholder for folder size, as API doesn't directly provide it
        await q.edit_message_text(f"Folder size: {size_str}")
    except Exception as e:
        await q.edit_message_text(f"Failed to get folder info: {str(e)}")

# Add handler for refresh requests
async def handle_refresh_requests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.edit_message_text("Access denied. You do not have permission to perform this action.")
        return
    # Reset pagination and refresh the requests list
    ctx.user_data["requests_page"] = 0
    await manage_requests(update, ctx)

# Apply @access_required to all relevant handlers
@access_required
async def handle_recyclebin_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    from .RecycleBin import handle_bin
    return await handle_bin(update, ctx)

@access_required
async def handle_message_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    from .MessageForDeveloper import handle_message_dev
    return await handle_message_dev(update, ctx)

@access_required
async def handle_terms_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    from .TermsAndCondition import show_terms_and_conditions
    return await show_terms_and_conditions(update, ctx)

@access_required
async def handle_storage_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    from .StorageDetails import handle_storage
    return await handle_storage(update, ctx)

def tail_log(log_file, n=30):
    if not os.path.exists(log_file):
        return []
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    return lines[-n:]

def terminal_dashboard():
    def _dashboard(stdscr):
        log_file = "bot.log"
        curses.curs_set(0)
        stdscr.nodelay(True)
        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            # Recompute dashboard in case stats change
            # Draw logs
            logs = tail_log(log_file, height - 1)
            for idx, line in enumerate(logs[-(height - 1):]):
                stdscr.addstr(idx, 0, line[:width-1])
            stdscr.refresh()
            time.sleep(1)
    curses.wrapper(_dashboard)

def start_websocket_server():
    import os
    logger_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Logger')
    ws_script = os.path.join(logger_dir, 'WebSocketServer.py')
    print(f"Starting WebSocket server from: {ws_script}")
    subprocess.Popen([sys.executable, ws_script], cwd=logger_dir)

def start_logger_web_ui():
    print("start_logger_web_ui() called")
    try:
        import os
        import http.server
        import socketserver
        import webbrowser
        import threading
        import time
        
        # Use configuration values
        PORT = 8766  # WebSocket uses 8765, HTTP uses 8766
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        web_dir = os.path.join(project_root, 'Logger')
        
        print(f"Project root: {project_root}")
        print(f"Web directory: {web_dir}")
        print(f"HTTP server port: {PORT}")
        
        # Check if Logger directory exists
        if not os.path.exists(web_dir):
            print(f"Logger directory not found: {web_dir}")
            return
        
        # Check if App.html exists
        html_file = os.path.join(web_dir, 'App.html')
        if not os.path.exists(html_file):
            print(f"App.html not found: {html_file}")
            return
        
        # Create a custom handler that serves from the Logger directory
        class LoggerHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=web_dir, **kwargs)
            
            def log_message(self, format, *args):
                # Suppress HTTP server logs unless there's an error
                if args[1] != '200':
                    super().log_message(format, *args)
        
        # Start HTTP server
        Handler = LoggerHTTPRequestHandler
        class ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True
        httpd = ReusableTCPServer(("", PORT), Handler)
        
        # Start server in a separate thread
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        
        # Wait a moment for server to start
        time.sleep(1)
        
        url = f"http://localhost:{PORT}/App.html"
        print(f"Web interface started at: {url}")
        print("Opening browser...")
        
        # Try to open browser
        try:
            # webbrowser.open(url)
            print("[INFO] Browser auto-open temporarily disabled.")
            print(f"Please manually open: {url}")
            print("Browser opened successfully")
        except Exception as browser_error:
            print(f"Failed to open browser automatically: {browser_error}")
            print(f"Please manually open: {url}")
            
    except Exception as e:
        print(f"Error in start_logger_web_ui: {e}")
        import traceback
        traceback.print_exc()

def main():
    # Start web interface with error handling
    print("Starting web interface...")
    try:
        start_logger_web_ui()
        print("✅ Web interface started successfully")
    except Exception as e:
        print(f"❌ Failed to start web interface: {e}")
        print("Bot will continue without web interface")
    
    # Initialize database
    print("Initializing database...")
    init_db()
    
    # Build and configure the bot application
    print("Building bot application...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("profile", handle_profile))
    app.add_handler(CommandHandler("filemanager", handle_file_manager))
    app.add_handler(CommandHandler("storage", handle_storage_command))
    app.add_handler(CommandHandler("recyclebin", handle_recyclebin_command))
    app.add_handler(CommandHandler("settings", handle_settings))
    app.add_handler(CommandHandler("message", handle_message_command))
    app.add_handler(CommandHandler("terms", handle_terms_command))
    app.add_handler(CallbackQueryHandler(handle_menu, pattern="^(FILE_MGR|SEARCH|PROFILE|STORAGE|BIN|SETTINGS|MESSAGE_DEV|PRIVACY|ACCESS|back|cancel)$"))
    app.add_handler(CallbackQueryHandler(handle_file_manager, pattern="^FILE_MGR$"))
    app.add_handler(CallbackQueryHandler(handle_folder_navigation, pattern="^(folder:.*|back_folder|next_page:.*|prev_page:.*|switch_account:.*)$"))
    app.add_handler(CallbackQueryHandler(handle_file_selection, pattern="^(file:.*|folder_options:.*)$"))
    app.add_handler(CallbackQueryHandler(handle_file_actions, pattern="^(rename_file:.*|delete_file:.*|confirm_delete_file:.*|copy_link:.*|rename_folder:.*|delete_folder:.*|confirm_delete_folder:.*|toggle_sharing:.*|new_folder:.*|back_to_folder)$"))
    app.add_handler(CallbackQueryHandler(handle_profile, pattern="^PROFILE$"))
    app.add_handler(CallbackQueryHandler(handle_storage, pattern="^STORAGE$"))
    app.add_handler(CallbackQueryHandler(refresh_storage, pattern="^refresh_storage$"))
    app.add_handler(CallbackQueryHandler(handle_bin, pattern="^BIN$"))
    app.add_handler(CallbackQueryHandler(handle_bin_navigation, pattern="^(bin_next_page|bin_prev_page|bin_item:.*|restore:.*|perm_delete:.*|confirm_empty_bin|back_to_bin|empty_bin)$"))
    app.add_handler(CallbackQueryHandler(handle_settings, pattern="^SETTINGS$"))
    app.add_handler(CallbackQueryHandler(login, pattern="^login$"))
    app.add_handler(CallbackQueryHandler(logout, pattern="^logout$"))
    app.add_handler(CallbackQueryHandler(handle_logout_action, pattern="^(logout_account|logout_specific:.*|logout_all_prompt)$"))
    app.add_handler(CallbackQueryHandler(switch_account_menu, pattern="^switch_account$"))
    app.add_handler(CallbackQueryHandler(set_primary, pattern="^set_primary:.*$"))
    app.add_handler(CallbackQueryHandler(update_def_location, pattern="^update_def_location$"))
    app.add_handler(CallbackQueryHandler(update_parallel_uploads, pattern="^update_parallel_uploads$"))
    app.add_handler(CallbackQueryHandler(handle_message_dev, pattern="^MESSAGE_DEV$"))
    app.add_handler(CallbackQueryHandler(show_terms_and_conditions, pattern="^TERMS$"))
    app.add_handler(CallbackQueryHandler(handle_access_control, pattern="^ACCESS$"))
    app.add_handler(CallbackQueryHandler(manage_requests, pattern="^manage_requests$"))
    app.add_handler(CallbackQueryHandler(handle_request_action, pattern="^(approve:.*|reject:.*)$"))
    app.add_handler(CallbackQueryHandler(manage_admins, pattern="^manage_admins$"))
    app.add_handler(CallbackQueryHandler(manage_whitelist, pattern="^manage_whitelist$"))
    app.add_handler(CallbackQueryHandler(manage_blacklist, pattern="^manage_blacklist$"))
    app.add_handler(CallbackQueryHandler(handle_blacklist_pagination, pattern="^(blacklist_prev_page|blacklist_next_page)$"))
    app.add_handler(CallbackQueryHandler(handle_unrestrict_blacklist, pattern="^unrestrict_blacklist:.*$"))
    app.add_handler(CallbackQueryHandler(handle_edit_blacklist, pattern="^edit_blacklist:.*$"))
    app.add_handler(CallbackQueryHandler(handle_access_actions, pattern="^(manage_admins|manage_whitelist|add_admin|remove_admin:.*|add_whitelist|remove_whitelist:.*|set_limit:.*|remove_limit:.*|promote_admin:.*|demote_admin:.*|admin_prev_page|admin_next_page|whitelist_prev_page|whitelist_next_page|requests_prev_page|requests_next_page|back_to_access|back_to_whitelist)$"))
    app.add_handler(CallbackQueryHandler(skip_message, pattern="^skip_message:.*$"))
    app.add_handler(CallbackQueryHandler(cancel_upload, pattern="^cancel_upload$"))
    app.add_handler(CallbackQueryHandler(search_next_page, pattern="^search_next_page$"))
    app.add_handler(CallbackQueryHandler(search_prev_page, pattern="^search_prev_page$"))
    app.add_handler(CallbackQueryHandler(handle_search_item, pattern="^search_item:.*$"))
    app.add_handler(CallbackQueryHandler(handle_access_request, pattern="^access_limit:.*$"))
    app.add_handler(CallbackQueryHandler(handle_access_request, pattern="^access_approve:.*$"))
    app.add_handler(CallbackQueryHandler(handle_access_request, pattern="^access_reject:.*$"))
    app.add_handler(CallbackQueryHandler(handle_access_request, pattern="^access_skip_approve$"))
    app.add_handler(CallbackQueryHandler(handle_access_request, pattern="^access_skip_reject$"))
    app.add_handler(CallbackQueryHandler(handle_access_request, pattern="^cancel_limit_setting$"))
    app.add_handler(CallbackQueryHandler(toggle_notify_completion, pattern="^toggle_notify_completion$"))
    app.add_handler(CallbackQueryHandler(handle_broadcast_message, pattern="^broadcast_message$"))
    app.add_handler(CallbackQueryHandler(handle_broadcast_approval, pattern="^(super_approve_broadcast|approve_broadcast|reject_broadcast):.*$"))
    app.add_handler(CallbackQueryHandler(handle_analytics_report, pattern="^analytics_report$"))
    app.add_handler(CallbackQueryHandler(handle_analytics_report_type, pattern="^analytics_(professional|dashboard|minimalist)$"))
    app.add_handler(CallbackQueryHandler(handle_file_size, pattern="^file_size:.*$"))
    app.add_handler(CallbackQueryHandler(handle_folder_size, pattern="^folder_size:.*$"))
    app.add_handler(CallbackQueryHandler(handle_refresh_requests, pattern="^refresh_requests$"))
    app.add_handler(CallbackQueryHandler(handle_live_terminal_logs, pattern="^live_terminal_logs$"))
    app.add_handler(CallbackQueryHandler(handle_authenticate_session, pattern="^authenticate_session$"))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(int(GROUP_CHAT_ID)), handle_access_message))
    app.add_handler(MessageHandler(filters.REPLY, handle_developer_reply))  # Must be above general text handler!
    # Add handler for private chat messages (access control)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Chat(int(GROUP_CHAT_ID)), handle_access_message))
    # Add broadcast media message handlers (must be before general text handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & access_filter, handle_broadcast_media_message))
    app.add_handler(MessageHandler(filters.PHOTO & access_filter, handle_broadcast_media_message))
    app.add_handler(MessageHandler(filters.VIDEO & access_filter, handle_broadcast_media_message))
    app.add_handler(MessageHandler(filters.Document.ALL & access_filter, handle_broadcast_media_message))
    app.add_handler(MessageHandler(filters.AUDIO & access_filter, handle_broadcast_media_message))
    app.add_handler(MessageHandler(filters.VOICE & access_filter, handle_broadcast_media_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & access_filter, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL & access_filter, handle_file))
    app.add_handler(InlineQueryHandler(handle_inline_query))
    # Register developer messaging handlers
    app.add_handler(CallbackQueryHandler(handle_reply_callback, pattern=r"^(reply_to_user:|reply_to_dev:).*$"))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_user_reply))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(int(GROUP_CHAT_ID)), handle_developer_reply))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_telethon_auth_message))
    
    # Set bot commands properly using the application's event loop
    async def setup_commands(application):
        try:
            await set_bot_commands(application)
        except Exception as e:
            log_error(e, context="setup_commands")
    
    # Add the setup_commands as a post_init handler
    app.post_init = setup_commands
    
    try:
        # add_admin(SUPER_ADMIN_ID) # This function is removed
        pass # No longer needed
    except ValueError as e:
        log_error(e, context="super_admin_initialization")
    # dashboard_thread = threading.Thread(target=terminal_dashboard, daemon=True)
    # dashboard_thread.start()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    async def shutdown():
        try:
            logger.info("[Shutdown] Initiating graceful shutdown...")
            print("Shutting down bot gracefully...")
            await app.stop()
            logger.info("[Shutdown] Bot stopped successfully.")
        except Exception as e:
            log_error(e, context="shutdown")
        finally:
            # If logger has handlers, flush them
            if hasattr(logger, 'handlers'):
                for handler in logger.handlers:
                    handler.flush()
            print("Shutdown complete.")
    def handle_signal(sig, frame):
        logger.info(f"[Shutdown] Received signal {sig}. Exiting...")
        print(f"Received signal {sig}. Exiting...")
        loop.create_task(shutdown())
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    try:
        app.run_polling()
    except (KeyboardInterrupt, SystemExit):
        logger.info("[Shutdown] Bot stopped by user.")
        print("Bot stopped by user.")

if __name__ == "__main__":
    executor = ThreadPoolExecutor(max_workers=5)
    main()