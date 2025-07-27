"""
CloudVerse Google Drive Bot - Main Application Entry Point

This module serves as the main entry point for the CloudVerse Google Drive Bot,
a Telegram bot that provides seamless integration with Google Drive services.
It handles user authentication, file management, access control, and various
administrative functions.

Key Features:
- Google Drive integration for file operations
- User access control and permission management
- File upload/download capabilities
- Admin panel for user management
- Real-time logging and monitoring
- Background tasks for maintenance

Author: CloudVerse Team
License: Open Source
"""

import tempfile
import os
import asyncio
import re
import requests
from googleapiclient.http import MediaFileUpload

# Import logging configuration
from .Logger import get_logger
logger = get_logger(__name__)
# Import bot modules for different functionalities
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
from .AdminControls import handle_admin_control, handle_admin_list, handle_users_list, handle_admin_pagination, handle_users_pagination, handle_performance_panel, handle_performance_panel_back, handle_edit_terms_condition, handle_terms_update_message, handle_authenticate_session, handle_telethon_auth_message, handle_delete_records, handle_delete_user_typein, handle_delete_user_typein_prompt, handle_delete_user_confirm, handle_manage_quota, handle_quota_user_details, handle_edit_quota, handle_quota_input_message
# External library imports
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, filters, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, InlineQueryHandler
from telegram import BotCommand, Update, InlineKeyboardButton, InlineKeyboardMarkup, InputTextMessageContent
import aiohttp
from telegram import InlineQueryResultArticle
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Standard library imports
import warnings
import signal
import threading
import time
import curses
import webbrowser
import http.server
import socketserver
import subprocess
import sys

# Suppress deprecation warnings for cleaner output
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")
warnings.filterwarnings("ignore", category=UserWarning, message="`Application` instances should be built via the `ApplicationBuilder`.")
warnings.filterwarnings("ignore", category=UserWarning, module="googleapiclient")

# Import user state management and access control
from .UserState import UserState, UserStateEnum
from .AccessManager import mark_expired_users_and_notify, unban_expired_temporary_blacklist_and_notify

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# MESSAGE CONSTANTS - User-facing messages for consistent communication
# ============================================================================

# Error and status messages
ERROR_OCCURRED_MSG = "An error occurred. Please try again or use /cancel."
ACCESS_EXPIRED_MSG = "Your access to the bot has expired. Please request access again by sending /start."
USER_INFO_NOT_FOUND_MSG = "User info not found. Please try again or contact support."
ACCESS_PENDING_MSG = "Your access request has been submitted to *Team CloudVerse* for Verification"
ACCESS_DENIED_MSG = "Access Denied : You are not authorised to perform this action\n\nContact *Team CloudVerse* for more"
PERMANENT_DELETE_CANCELLED_MSG = "Permanent delete cancelled."
SERVICE_UNAVAILABLE_MSG = "Service unavailable. Please try again later."
MESSAGE_SENT_TO_USER_MSG = "Message sent to user."

# Authentication and login messages
LOGOUT_CANCELLED_MSG = "Logout cancelled."
LOGIN_FAILED_MSG = "Login failed: {error}"

# File operation messages
FILE_RENAMED_SUCCESS_MSG = "File renamed successfully."
FOLDER_RENAMED_SUCCESS_MSG = "Folder renamed successfully."
FOLDER_CREATED_SUCCESS_MSG = "Folder created successfully. ID: {folder_id}"
PARALLEL_UPLOAD_LIMIT_UPDATED_MSG = "Parallel upload limit updated."
PARALLEL_UPLOAD_LIMIT_RANGE_MSG = "Please enter a number between 1 and 5."

# Admin and user management messages
ACCESS_DENIED_SUPER_ADMIN_MSG = "Access denied. Only super admins can add new admins."
USER_ADDED_AS_ADMIN_MSG = "User @{username} added as admin."
USER_NOT_FOUND_MSG = "User @{username} not found."
USER_ADDED_TO_WHITELIST_MSG = "User @{username} added to whitelist."
TIME_LIMIT_SET_MSG = "Time limit set to {hours} hours."
TIME_LIMIT_INPUT_MSG = "Please enter the time in hours (e.g., 12 or 12H)."

# Search and query messages
AN_ERROR_OCCURRED_MSG = "An error occurred: {error}"
NO_RESULTS_FOUND_MSG = "No results found."
HERE_ARE_SEARCH_RESULTS_MSG = "Here are the search results for '{text}':\n\n{result}"
INLINE_SEARCH_UNAVAILABLE_TITLE = "Inline search unavailable"
INLINE_SEARCH_UNAVAILABLE_MSG = "Please open the bot and press Search to use inline mode."
INLINE_SEARCH_NO_LOGIN_TITLE = "Please log in to use inline search"
INLINE_SEARCH_NO_LOGIN_MSG = "Please log in to the bot to use inline search."
NO_FILES_FOUND_TITLE = "No files found"
NO_MATCHING_FILES_MSG = "No matching files found in your Google Drive."

# UI and interaction messages
NOTIFY_COMPLETION_ON = "🔕 Don't notify completion"
NOTIFY_COMPLETION_OFF = "🛎️ Notify completion"
CANCEL_BUTTON = "❎ Cancel"
FILE_SIZE_MSG = "File size: {size}"
FAILED_TO_GET_FILE_SIZE_MSG = "Failed to get file size: {error}"
FOLDER_SIZE_MSG = "Folder size: {size}"
FAILED_TO_GET_FOLDER_INFO_MSG = "Failed to get folder info: {error}"
ACCESS_DENIED_ACTION_MSG = "Access denied. You do not have permission to perform this action."
ACCESS_EXPIRY_REMINDER_MSG = "Your access will expire in 30 minutes. Contact *Team CloudVerse* for help"

# System and application messages
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

# ============================================================================
# CONFIGURATION VALIDATION - Ensure required environment variables are set
# ============================================================================

if BOT_TOKEN is None:
    raise ValueError("BOT_TOKEN is not set in config.")
if GROUP_CHAT_ID is None:
    raise ValueError("GROUP_CHAT_ID is not set in config.")
if SUPER_ADMIN_ID is None:
    raise ValueError("SUPER_ADMIN_ID is not set in config.")

# ============================================================================
# GLOBAL ERROR HANDLING
# ============================================================================

async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    """
    Global error handler for uncaught exceptions in the bot.
    
    This function catches any unhandled errors that occur during bot operation
    and sends a generic error message to the user to maintain a good user experience.
    
    Args:
        update: The Telegram update object containing the message/callback
        context: The context object containing bot and user data
        
    Note:
        Errors are silently caught to prevent the bot from crashing.
        In production, you might want to log these errors for debugging.
    """
    try:
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=ERROR_OCCURRED_MSG)
    except Exception:
        # Silently handle any errors in error handling to prevent infinite loops
        pass

async def set_bot_commands(app):
    """
    Configure the bot's command menu that appears in Telegram clients.
    
    This function sets up the list of available commands that users can see
    when they type '/' in the chat. These commands provide quick access to
    the bot's main features.
    
    Args:
        app: The Telegram Application instance
        
    Commands configured:
        - /start: Initialize the bot and show main menu
        - /login: Authenticate with Google Drive
        - /profile: Display user account information
        - /filemanager: Access Google Drive file management
        - /storage: View storage usage statistics
        - /recyclebin: Access deleted files
        - /settings: Configure bot preferences
        - /message: Contact support/developers
        - /privacy: View privacy policy and terms
    """
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
    """
    Send notification to user when their bot access has expired.
    
    This function is called when a user's temporary access to the bot
    has expired and they need to request access again.
    
    Args:
        update: The Telegram update object
        telegram_id: The user's Telegram ID (for logging purposes)
        
    Note:
        The user will need to send /start again to request new access.
    """
    await update.effective_chat.send_message(
        ACCESS_EXPIRED_MSG
    )

# Legacy filter - kept for compatibility but no longer used
# Access control is now handled by the @access_required decorator
access_filter = filters.BaseFilter()

@handle_errors
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Main entry point for the /start command - handles user authentication and access control.
    
    This function is the first point of contact for users interacting with the bot.
    It performs several critical functions:
    1. Validates user information from Telegram
    2. Checks if user has admin or whitelist access
    3. If authorized, displays the main menu
    4. If not authorized, adds user to pending list and notifies admins
    
    Access Control Flow:
    - Admins and whitelisted users: Direct access to main menu
    - New users: Added to pending list, access request sent to admin group
    - Invalid users: Error message displayed
    
    Args:
        update (Update): Telegram update object containing user message/callback
        ctx (ContextTypes.DEFAULT_TYPE): Bot context containing user data and bot instance
        
    Returns:
        None: Function handles response directly through Telegram API
        
    Raises:
        Handled by @handle_errors decorator - logs errors and shows generic error message
    """
    # Initialize user data if not present
    if ctx.user_data is None:
        ctx.user_data = {}
    
    # Validate user information from Telegram update
    if not hasattr(update, 'effective_user') or update.effective_user is None:
        # Handle case where user information is not available
        if update.message and hasattr(update.message, 'reply_text'):
            await update.message.reply_text(USER_INFO_NOT_FOUND_MSG)
            return
        elif hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(USER_INFO_NOT_FOUND_MSG)
            return
    else:
        # Extract user information from Telegram
        telegram_id = update.effective_user.id
        username = getattr(update.effective_user, 'username', '')
        first_name = getattr(update.effective_user, 'first_name', '')
        last_name = getattr(update.effective_user, 'last_name', '') or ''
    
    # Check user access permissions
    if is_admin(telegram_id) or is_whitelisted(telegram_id):
        # User has access - show main menu
        await menu_start(update, ctx)
    else:
        # User needs access approval - add to pending list
        add_pending_user(telegram_id, username, first_name, last_name)
        access_pending_msg = ACCESS_PENDING_MSG
        
        # Send pending message to user
        if update.message:
            await update.message.reply_text(access_pending_msg, parse_mode='Markdown')
        elif hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(access_pending_msg, parse_mode='Markdown')
        
        # Notify admin group about access request
        await post_access_request_to_group(ctx, telegram_id, username, first_name, last_name)

@handle_errors
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Central message handler for processing user text input based on current user state.
    
    This function acts as a state machine, routing user messages to appropriate handlers
    based on the user's current interaction state. It handles various scenarios including:
    - Developer messages
    - File deletion confirmations
    - Approval messages
    - Authentication codes
    - Admin/user management inputs
    - URL uploads
    
    State Management:
    The function uses UserState to track what the bot is expecting from the user,
    ensuring that user input is processed in the correct context.
    
    Args:
        update (Update): Telegram update containing the user's message
        ctx (ContextTypes.DEFAULT_TYPE): Bot context with user data and bot instance
        
    Returns:
        None: Function processes the message and responds directly
        
    Note:
        This function is decorated with @handle_errors for automatic error handling
    """
    # Initialize user data and state management
    if ctx.user_data is None:
        ctx.user_data = {}
    if "state" not in ctx.user_data or not isinstance(ctx.user_data["state"], UserState):
        ctx.user_data["state"] = UserState()
    
    # Get current user state and basic message info
    user_state: UserState = ctx.user_data["state"]
    if update.message and update.message.from_user:
        telegram_id = update.message.from_user.id
    else:
        return
    
    # Get Google Drive service and message text
    service = get_drive_service(telegram_id) if telegram_id else None
    text = update.message.text if update.message else ''

    # ========================================================================
    # STATE-BASED MESSAGE HANDLING
    # ========================================================================
    
    # Handle message to developer support
    if user_state.is_state(UserStateEnum.EXPECTING_DEV_MESSAGE):
        """Process user message intended for developer/support team"""
        from .MessageForDeveloper import send_to_developer
        await send_to_developer(update, ctx)
        user_state.reset()
        return

    # Handle file/folder deletion confirmation
    if user_state.is_state(UserStateEnum.EXPECTING_DELETE_CONFIRMATION):
        """Process user confirmation for permanent file/folder deletion"""
        file = user_state.data.get("file")
        if file is not None:
            # Check if user typed "delete" to confirm
            if isinstance(text, str) and text.strip().lower() == "delete":
                service = get_drive_service(telegram_id)
                if service:
                    # Permanently delete the file/folder from Google Drive
                    service.files().delete(fileId=file["id"]).execute()
                    if update.message:
                        file_type = 'Folder' if file['mimeType'] == 'application/vnd.google-apps.folder' else 'File'
                        await update.message.reply_text(f"{file_type} : {file['name']} permanently deleted.")
                else:
                    if update.message:
                        await update.message.reply_text(SERVICE_UNAVAILABLE_MSG)
            else:
                # User didn't confirm - cancel deletion
                if update.message:
                    await update.message.reply_text(PERMANENT_DELETE_CANCELLED_MSG)
        else:
            if update.message:
                await update.message.reply_text("No file information found for deletion.")
        user_state.reset()
        return
    # Handle custom approval message from admin
    elif user_state.is_state(UserStateEnum.EXPECTING_APPROVAL_MESSAGE):
        """Process custom message from admin to send to user regarding their access request"""
        data = user_state.data
        user_id = data.get("user_id")
        action = data.get("action")
        if user_id is not None:
            # Use admin's custom message or default message
            message = text if text else "Your request has been submitted for approval." + ("approved." if action == "approve" else "rejected.")
            await ctx.bot.send_message(chat_id=user_id, text=message)
            if update.message:
                await update.message.reply_text(MESSAGE_SENT_TO_USER_MSG)
        else:
            if update.message:
                await update.message.reply_text("User ID not found for approval message.")
        user_state.reset()
        return
    # Handle Google OAuth authentication code
    elif user_state.is_state(UserStateEnum.EXPECTING_CODE):
        """Process OAuth authorization code from Google for Drive access"""
        flow = user_state.data.get("flow")
        try:
            if flow is not None:
                if isinstance(text, str):
                    # Exchange authorization code for access token
                    flow.fetch_token(code=text.strip())
                creds = flow.credentials
                
                # Test the credentials by getting user info
                from googleapiclient.discovery import build
                temp_service = build("drive", "v3", credentials=creds)
                user_info = temp_service.about().get(fields="user").execute()
                email = user_info["user"]["emailAddress"]
                username = getattr(update.effective_user, 'username', '') if hasattr(update, 'effective_user') and update.effective_user else ''
            else:
                if update.message:
                    await update.message.reply_text("No authentication flow found. Please try logging in again.")
        except Exception as e:
            # Handle authentication errors
            if update.message:
                await update.message.reply_text(LOGIN_FAILED_MSG.format(error=str(e)))
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(LOGIN_FAILED_MSG.format(error=str(e)))
        finally:
            user_state.reset()
        return
    # Handle logout confirmation
    elif user_state.is_state(UserStateEnum.EXPECTING_LOGOUT_CONFIRMATION):
        """Process user confirmation for logging out of Google Drive"""
        confirmation = user_state.data.get("confirmation")
        if isinstance(text, str) and text.strip() == confirmation:
            # User confirmed logout - proceed with logout process
            user_state.reset()
        else:
            # User didn't provide correct confirmation - cancel logout
            await update.message.reply_text(LOGOUT_CANCELLED_MSG)
            user_state.reset()
        return
    
    # Handle admin and user management input states
    elif service and user_state.state in [
        UserStateEnum.EXPECTING_ADMIN_USERNAME,
        UserStateEnum.EXPECTING_WHITELIST_USERNAME,
        UserStateEnum.EXPECTING_LIMIT_HOURS,
        UserStateEnum.EXPECTING_PARALLEL_UPLOADS
    ]:
        """Handle various admin and user management input states"""
        action = user_state.state
        try:
            # Process admin username input (super admin only)
            if action == UserStateEnum.EXPECTING_ADMIN_USERNAME:
                if not is_super_admin(telegram_id):
                    await update.message.reply_text(ACCESS_DENIED_SUPER_ADMIN_MSG)
                    user_state.reset()
                    return
                # Clean username and look up user ID
                username = text.strip('@') if isinstance(text, str) else ''
                user_id = get_user_id_by_username(username)
                if user_id:
                    add_admin(user_id)
                    await update.message.reply_text(USER_ADDED_AS_ADMIN_MSG.format(username=username))
                else:
                    await update.message.reply_text(USER_NOT_FOUND_MSG.format(username=username))
                user_state.reset()
                return
            
            # Process whitelist username input
            elif action == UserStateEnum.EXPECTING_WHITELIST_USERNAME:
                # Clean username and look up user ID
                username = text.strip('@') if isinstance(text, str) else ''
                user_id = get_user_id_by_username(username)
                if user_id:
                    add_whitelist(user_id)
                    await update.message.reply_text(USER_ADDED_TO_WHITELIST_MSG.format(username=username))
                else:
                    await update.message.reply_text(USER_NOT_FOUND_MSG.format(username=username))
                user_state.reset()
                return
            # Process time limit hours input
            elif action == UserStateEnum.EXPECTING_LIMIT_HOURS:
                user_id = user_state.data.get("user_id")
                hours = None
                if isinstance(text, str):
                    text_clean = text.strip()
                    # Parse hours input - supports formats like "24" or "24H"
                    if text_clean.endswith('H'):
                        hours_str = text_clean[:-1]
                        if hours_str.isdigit():
                            hours = int(hours_str)
                    elif text_clean.isdigit():
                        hours = int(text_clean)
                
                if hours is not None:
                    # Set expiration time for user's whitelist access
                    from datetime import datetime, timedelta
                    expiration_time = (datetime.now() + timedelta(hours=hours)).isoformat()
                    set_whitelist_expiration(user_id, expiration_time)
                    await update.message.reply_text(TIME_LIMIT_SET_MSG.format(hours=hours))
                    user_state.reset()
                    return
                else:
                    await update.message.reply_text(TIME_LIMIT_INPUT_MSG)
            
            # Process parallel uploads limit input
            elif action == UserStateEnum.EXPECTING_PARALLEL_UPLOADS:
                if isinstance(text, str) and text.isdigit():
                    num = int(text)
                    # Validate range (1-5 parallel uploads)
                    if 1 <= num <= 5:
                        await update.message.reply_text(PARALLEL_UPLOAD_LIMIT_UPDATED_MSG)
                        user_state.reset()
                        return
                    else:
                        await update.message.reply_text(PARALLEL_UPLOAD_LIMIT_RANGE_MSG)
        except Exception as e:
            await update.message.reply_text(AN_ERROR_OCCURRED_MSG.format(error=str(e)))
    
    # Handle URL uploads if message contains a URL
    elif await is_url(text) and service:
        await handle_url(update, ctx)
        return

@handle_errors
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Handle file uploads from users.
    
    This function processes files sent by users and delegates the actual
    upload handling to the specialized file upload handler.
    
    Args:
        update (Update): Telegram update containing the file
        ctx (ContextTypes.DEFAULT_TYPE): Bot context with user data
        
    Note:
        Files are processed through the Uploader module which handles
        Google Drive integration and upload progress tracking.
    """
    await handle_file_upload(update, ctx)

@handle_errors
async def handle_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Handle URL uploads from users.
    
    This function processes URLs sent by users for downloading and uploading
    to Google Drive. It delegates to the specialized URL upload handler.
    
    Args:
        update (Update): Telegram update containing the URL
        ctx (ContextTypes.DEFAULT_TYPE): Bot context with user data
        
    Note:
        URLs are processed through the Uploader module which handles
        downloading from the URL and uploading to Google Drive.
    """
    await handle_url_upload(update, ctx)

@handle_errors
async def toggle_notify_completion(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Toggle the notification setting for upload completion.
    
    This function allows users to enable/disable notifications when their
    file uploads are completed. The setting is stored in user_data and
    affects the upload process behavior.
    
    Args:
        update (Update): Telegram callback query update
        ctx (ContextTypes.DEFAULT_TYPE): Bot context with user data
        
    User Experience:
        - Shows current notification status in button text
        - Toggles between "🔕 Don't notify completion" and "🛎️ Notify completion"
        - Updates the inline keyboard to reflect the new state
    """
    if ctx.user_data is None:
        ctx.user_data = {}
    
    # Toggle the notification setting
    current = ctx.user_data.get('notify_completion', True)
    ctx.user_data['notify_completion'] = not current
    
    # Update button text to reflect current state
    btn_text = NOTIFY_COMPLETION_ON if ctx.user_data['notify_completion'] else NOTIFY_COMPLETION_OFF
    
    # Update the inline keyboard with new button text
    if update.callback_query and hasattr(update.callback_query, 'edit_message_reply_markup'):
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(btn_text, callback_data='toggle_notify_completion'),
                InlineKeyboardButton(CANCEL_BUTTON, callback_data='cancel_upload')
            ]
        ])
        await update.callback_query.edit_message_reply_markup(reply_markup=markup)
    
    # Acknowledge the callback query
    if update.callback_query and hasattr(update.callback_query, 'answer'):
        await update.callback_query.answer()

@handle_errors
async def handle_refresh_requests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Handle callback for refreshing access control requests list.
    
    This function allows admins to refresh the pending access requests
    list to see newly submitted requests. It resets the pagination to
    the first page and validates admin permissions.
    
    Args:
        update (Update): Telegram callback query update
        ctx (ContextTypes.DEFAULT_TYPE): Bot context with user data
        
    Access Control:
        Only admins can refresh the requests list. Non-admins receive
        an access denied message.
        
    Side Effects:
        Resets the requests_page to 0 in user_data for pagination
    """
    if ctx.user_data is None:
        ctx.user_data = {}
    
    q = update.callback_query
    if not q or not q.from_user:
        return
    
    telegram_id = q.from_user.id
    
    # Verify admin permissions
    if not is_admin(telegram_id):
        await q.edit_message_text(ACCESS_DENIED_ACTION_MSG)
        return
    
    # Reset pagination to first page
    ctx.user_data["requests_page"] = 0

# ============================================================================
# COMMAND HANDLERS - Direct command processing functions
# ============================================================================

@handle_errors
@access_required
async def handle_recyclebin_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /recyclebin command to access Google Drive trash.
    
    This command allows users to view and manage files in their Google Drive
    recycle bin (trash). Users can restore or permanently delete files.
    
    Args:
        update (Update): Telegram update containing the command
        ctx (ContextTypes.DEFAULT_TYPE): Bot context with user data
        
    Access Control:
        Requires user to be whitelisted or admin (@access_required decorator)
        
    Returns:
        Result from RecycleBin.handle_bin function
    """
    if ctx.user_data is None:
        ctx.user_data = {}
    from .RecycleBin import handle_bin
    return await handle_bin(update, ctx)

@handle_errors
@access_required
async def handle_message_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /message command to contact support/developers.
    
    This command opens the messaging interface allowing users to send
    messages to the CloudVerse support team or developers.
    
    Args:
        update (Update): Telegram update containing the command
        ctx (ContextTypes.DEFAULT_TYPE): Bot context with user data
        
    Access Control:
        Requires user to be whitelisted or admin (@access_required decorator)
        
    Returns:
        Result from MessageForDeveloper.handle_cloudverse_support function
    """
    if ctx.user_data is None:
        ctx.user_data = {}
    from .MessageForDeveloper import handle_cloudverse_support
    return await handle_cloudverse_support(update, ctx)

@handle_errors
@access_required
async def handle_privacy_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /privacy command to display privacy policy.
    
    This command shows the bot's privacy policy and terms of service
    to help users understand data usage and policies.
    
    Args:
        update (Update): Telegram update containing the command
        ctx (ContextTypes.DEFAULT_TYPE): Bot context with user data
        
    Access Control:
        Requires user to be whitelisted or admin (@access_required decorator)
        
    Returns:
        Result from TermsAndCondition.show_terms_and_conditions function
    """
    if ctx.user_data is None:
        ctx.user_data = {}
    from .TermsAndCondition import show_terms_and_conditions
    return await show_terms_and_conditions(update, ctx)

@handle_errors
@access_required
async def handle_terms_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /terms command to display terms and conditions.
    
    This command shows the bot's terms and conditions that users
    must agree to when using the service.
    
    Args:
        update (Update): Telegram update containing the command
        ctx (ContextTypes.DEFAULT_TYPE): Bot context with user data
        
    Access Control:
        Requires user to be whitelisted or admin (@access_required decorator)
        
    Returns:
        Result from TermsAndCondition.show_terms_and_conditions function
    """
    if ctx.user_data is None:
        ctx.user_data = {}
    from .TermsAndCondition import show_terms_and_conditions
    return await show_terms_and_conditions(update, ctx)

@handle_errors
@access_required
async def handle_storage_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /storage command to display storage information.
    
    This command shows detailed information about the user's Google Drive
    storage usage, including used space, available space, and quotas.
    
    Args:
        update (Update): Telegram update containing the command
        ctx (ContextTypes.DEFAULT_TYPE): Bot context with user data
        
    Access Control:
        Requires user to be whitelisted or admin (@access_required decorator)
        
    Returns:
        Result from StorageDetails.handle_storage function
    """
    if ctx.user_data is None:
        ctx.user_data = {}
    from .StorageDetails import handle_storage
    return await handle_storage(update, ctx)

# ============================================================================
# UTILITY FUNCTIONS - Helper functions for logging and monitoring
# ============================================================================

def tail_log(log_file, n=30):
    """
    Read the last n lines from a log file.
    
    This utility function reads the tail of a log file, similar to the
    Unix 'tail' command. It's used for displaying recent log entries
    in the terminal dashboard.
    
    Args:
        log_file (str): Path to the log file to read
        n (int): Number of lines to read from the end (default: 30)
        
    Returns:
        list: List of strings containing the last n lines from the file
        
    Note:
        Returns empty list if file doesn't exist. Uses UTF-8 encoding
        with error handling for corrupted characters.
    """
    if not os.path.exists(log_file):
        return []
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    return lines[-n:]

def terminal_dashboard():
    """
    Start a real-time terminal dashboard for monitoring bot logs.
    
    This function creates a curses-based terminal interface that displays
    the bot's log file in real-time. It's useful for monitoring bot
    activity during development and debugging.
    
    Features:
        - Real-time log updates (refreshes every second)
        - Automatically fits terminal window size
        - Shows most recent log entries
        - Handles terminal resizing
        
    Usage:
        Call this function to start the dashboard. Press Ctrl+C to exit.
        
    Note:
        This function blocks execution and should be run in a separate
        thread if used alongside the bot.
    """
    def _dashboard(stdscr):
        log_file = "bot.log"
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(True)  # Non-blocking input
        
        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            
            # Get recent log entries that fit the screen
            logs = tail_log(log_file, height - 1)
            
            # Display logs, truncating lines that are too long
            for idx, line in enumerate(logs[-(height - 1):]):
                stdscr.addstr(idx, 0, line[:width-1])
            
            stdscr.refresh()
            time.sleep(1)  # Update every second
    
    curses.wrapper(_dashboard)

# ============================================================================
# BACKGROUND TASKS - Automated maintenance and notification tasks
# ============================================================================

async def access_expiry_reminder_task(app):
    """
    Background task to send access expiry reminders to users.
    
    This task runs continuously in the background, checking for users
    whose whitelist access is about to expire and sending them reminder
    notifications. It helps ensure users are aware of their access status.
    
    Args:
        app: The Telegram Application instance for sending messages
        
    Behavior:
        - Runs every 5 minutes (300 seconds)
        - Checks for users expiring within 30 minutes
        - Sends reminder messages in Markdown format
        - Silently handles individual message failures
        - Continues running even if database queries fail
        
    Error Handling:
        Individual message failures are ignored to prevent the task from
        stopping due to blocked users or network issues.
    """
    while True:
        try:
            # Get users whose access expires within 30 minutes
            users = get_whitelist_expiring_soon(30)
            
            for user in users:
                try:
                    await app.bot.send_message(
                        chat_id=user['telegram_id'],
                        text=ACCESS_EXPIRY_REMINDER_MSG,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    # Silently handle individual message failures
                    # (user may have blocked bot, network issues, etc.)
                    pass
        except Exception as e:
            # Silently handle database or other system errors
            # to keep the task running
            pass
        
        # Wait 5 minutes before next check
        await asyncio.sleep(300)

# ============================================================================
# MAIN APPLICATION ENTRY POINT
# ============================================================================

def main():
    """
    Main entry point for the CloudVerse Google Drive Bot application.
    
    This function initializes and starts the entire bot system, including:
    1. Database initialization
    2. Telegram bot application setup
    3. Handler registration for all bot commands and callbacks
    4. Background task scheduling
    5. Bot startup and polling
    
    The function handles the complete lifecycle of the bot from startup
    to shutdown, including graceful error handling and logging.
    
    Architecture:
        - Uses python-telegram-bot library for Telegram integration
        - SQLite database for user and session management
        - Google Drive API for file operations
        - Async/await pattern for concurrent operations
        - Comprehensive logging for monitoring and debugging
        
    Error Handling:
        - Catches and logs initialization errors
        - Handles graceful shutdown on interruption
        - Provides detailed error messages for troubleshooting
        
    Raises:
        SystemExit: On critical initialization failures
        KeyboardInterrupt: On user interruption (Ctrl+C)
    """
    logger.info("Starting CloudVerse Bot application")
    try:
        # Initialize the SQLite database and create necessary tables
        logger.info("Initializing database")
        init_db()
        logger.info("Database initialized successfully")
        
        # Create the Telegram bot application instance
        logger.info("Building Telegram application")
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        logger.info("Telegram application built successfully")
        
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
        ("callback", (handle_manage_quota, r"^manage_quota$")),
        ("callback", (handle_manage_quota, r"^quota_(prev_page|next_page)$")),
        ("callback", (handle_quota_user_details, r"^quota_user:.*$")),
        ("callback", (handle_edit_quota, r"^edit_quota:.*$")),
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
        ("message", (filters.TEXT & filters.ChatType.PRIVATE, handle_quota_input_message)),
        ("callback", (handle_delete_user_typein_prompt, r"^delete_user_typein:.*$")),
        ("callback", (handle_file_size, r"^file_size:.*$")),
        ("callback", (handle_folder_size, r"^folder_size:.*$")),
    ]
    
    logger.info("Registering bot handlers")
    handler_count = 0
    for htype, args in handler_defs:
        try:
            if htype == "command":
                app.add_handler(CommandHandler(*args))
            elif htype == "callback":
                app.add_handler(CallbackQueryHandler(*args))
            elif htype == "message":
                app.add_handler(MessageHandler(*args))
            elif htype == "inline":
                app.add_handler(InlineQueryHandler(args))
            handler_count += 1
        except Exception as e:
            logger.error(f"Failed to register {htype} handler: {str(e)}", exc_info=True)
    
    logger.info(f"Successfully registered {handler_count} handlers")
    # --- End Refactored Handler Registration ---
    async def setup_commands(application):
        logger.info("Setting up bot commands and background tasks")
        try:
            logger.debug("Setting bot commands")
            await set_bot_commands(application)
            logger.info("Bot commands set successfully")
            
            # Schedule the access_expiry_reminder_task after bot is initialized
            logger.debug("Starting access expiry reminder task")
            asyncio.create_task(access_expiry_reminder_task(application))
            
            # Schedule the expired user update and unban tasks using AccessManager
            logger.debug("Starting expired users management task")
            asyncio.create_task(mark_expired_users_and_notify(application))
            
            logger.debug("Starting temporary blacklist unban task")
            asyncio.create_task(unban_expired_temporary_blacklist_and_notify(application))
            
            logger.info("All background tasks started successfully")
        except Exception as e:
            logger.error(f"Failed to setup commands and tasks: {str(e)}", exc_info=True)
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
        logger.info("Initiating graceful shutdown...")
        try:
            await app.stop()
            logger.info("Bot stopped successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
        finally:
            logger.info("Shutdown complete")
    def handle_signal(sig, frame):
        logger.info(f"Received signal {sig}. Exiting...")
        loop.create_task(shutdown())
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
        logger.info("Starting bot polling...")
        app.run_polling()
        
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot application: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    executor = ThreadPoolExecutor(max_workers=5)
    main()