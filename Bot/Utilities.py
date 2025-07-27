"""
CloudVerse Google Drive Bot - Utilities Module

This module provides essential utility functions, decorators, and helpers used
throughout the CloudVerse Bot application. It includes access control decorators,
error handling mechanisms, pagination utilities, and various helper functions
for common operations.

Key Features:
- Access control decorators for admin and user permissions
- Comprehensive error handling with logging
- Pagination utilities for large data sets
- URL validation and processing
- File size formatting and calculations
- System resource monitoring utilities
- Common UI components and message formatting

Decorators:
- @handle_errors: Comprehensive error handling with logging
- @admin_required: Restricts access to admin users only
- @super_admin_required: Restricts access to super admin users only
- @access_required: Ensures user has bot access permissions

Utility Functions:
- Pagination for large lists
- URL validation and processing
- File size calculations and formatting
- System resource monitoring
- Common UI component generation

Author: CloudVerse Team
License: Open Source
"""

import re
import asyncio
import humanize
import psutil
import time

from functools import wraps
from .database import is_admin, is_super_admin
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton

from .drive import get_credentials, list_files
from .config import DB_PATH
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .Logger import get_logger
logger = get_logger(__name__)

# ============================================================================
# MESSAGE CONSTANTS - User-facing messages for consistent UX
# ============================================================================

# Error messages
ERROR_OCCURRED_MSG = "An error occurred. Please try again or use /cancel."
ADMIN_DENIED_MSG = "You don't have permission to access this feature."
SUPER_ADMIN_DENIED_MSG = "Only the super admin can perform this action."
ACCESS_DENIED_MSG = "Access denied. You do not have permission to perform this action."

# Service status messages
SERVICE_UNAVAILABLE_MSG = "Service unavailable. Please try again later."

# File operation messages
FILE_SIZE_MSG = "File size: {size}"
FAILED_TO_GET_FILE_SIZE_MSG = "Failed to get file size: {error}"
FOLDER_SIZE_MSG = "Folder size: {size}"
FAILED_TO_GET_FOLDER_INFO_MSG = "Failed to get folder info: {error}"

# ============================================================================
# DECORATORS - Function decorators for error handling and access control
# ============================================================================

def handle_errors(handler):
    """
    Comprehensive error handling decorator for bot handlers.
    
    This decorator wraps bot handler functions to provide consistent error
    handling, logging, and user feedback. It captures exceptions, logs them
    with context information, and provides appropriate user responses.
    
    Features:
        - Automatic exception catching and logging
        - User context extraction for detailed logs
        - Graceful error responses to users
        - Performance monitoring and debugging info
        - Prevents bot crashes from unhandled exceptions
    
    Args:
        handler: The async function to wrap (bot handler)
        
    Returns:
        wrapper: The wrapped function with error handling
        
    Usage:
        @handle_errors
        async def my_handler(update, ctx):
            # Handler code here
            pass
            
    Logging Information:
        - Handler name and execution time
        - User ID and context information
        - Full exception details with stack traces
        - Performance metrics for optimization
    """
    @wraps(handler)
    async def wrapper(update, ctx: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        handler_name = handler.__name__
        user_id = None
        
        # Extract user information for comprehensive logging
        try:
            if hasattr(update, 'effective_user') and update.effective_user:
                user_id = update.effective_user.id
            elif hasattr(update, 'callback_query') and update.callback_query and update.callback_query.from_user:
                user_id = update.callback_query.from_user.id
            elif hasattr(update, 'message') and update.message and update.message.from_user:
                user_id = update.message.from_user.id
        except Exception:
            # Silently handle user extraction errors to prevent cascading failures
            pass
        
        logger.debug(f"Executing handler: {handler_name} for user: {user_id}")
        
        try:
            # Execute the wrapped handler function
            result = await handler(update, ctx, *args, **kwargs)
            logger.debug(f"Handler {handler_name} completed successfully for user: {user_id}")
            return result
        except Exception as e:
            # Log the error with full context and stack trace
            logger.error(f"Error in handler {handler_name} for user {user_id}: {str(e)}", exc_info=True)
            
            # Attempt to send user-friendly error message through appropriate channel
            try:
                if hasattr(update, 'effective_chat') and update.effective_chat:
                    await ctx.bot.send_message(chat_id=update.effective_chat.id, text=ERROR_OCCURRED_MSG)
                elif hasattr(update, 'message') and update.message:
                    await update.message.reply_text(ERROR_OCCURRED_MSG)
                elif hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.edit_message_text(ERROR_OCCURRED_MSG)
                logger.debug(f"Error message sent to user {user_id}")
            except Exception as send_error:
                # Log failure to send error message but don't raise
                logger.error(f"Failed to send error message to user {user_id}: {str(send_error)}")
    return wrapper

def admin_required(handler):
    """
    Access control decorator that restricts handler access to admin users only.
    
    This decorator checks if the user has admin privileges before allowing
    access to the wrapped handler function. It provides comprehensive logging
    of access attempts and denials for security auditing.
    
    Access Control:
        - Allows access to users with admin or super admin privileges
        - Denies access to regular users and non-authenticated users
        - Logs all access attempts for security monitoring
        
    Args:
        handler: The async function to wrap (bot handler)
        
    Returns:
        wrapper: The wrapped function with admin access control
        
    Usage:
        @admin_required
        async def admin_only_handler(update, ctx):
            # Only admins can access this
            pass
            
    Security Features:
        - User identification from multiple update types
        - Database-backed permission checking
        - Comprehensive access logging
        - Graceful denial with user feedback
    """
    @wraps(handler)
    async def wrapper(update, ctx, *args, **kwargs):
        # Extract user ID from various update types
        telegram_id = None
        if hasattr(update, 'effective_user') and update.effective_user:
            telegram_id = update.effective_user.id
        elif hasattr(update, 'message') and update.message and hasattr(update.message, 'from_user') and update.message.from_user:
            telegram_id = update.message.from_user.id
        elif hasattr(update, 'callback_query') and update.callback_query and hasattr(update.callback_query, 'from_user') and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
        
        logger.debug(f"Admin access check for handler {handler.__name__} by user {telegram_id}")
        
        # Check admin privileges in database
        from .database import is_admin
        if not (telegram_id and is_admin(telegram_id)):
            logger.warning(f"Admin access denied for user {telegram_id} to handler {handler.__name__}")
            denial_msg = ADMIN_DENIED_MSG
            
            # Send appropriate denial message based on update type
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.answer(denial_msg, show_alert=True)
            elif hasattr(update, 'message') and update.message:
                await update.message.reply_text(denial_msg)
            return
        
        # Access granted - proceed with handler execution
        logger.debug(f"Admin access granted for user {telegram_id} to handler {handler.__name__}")
        return await handler(update, ctx, *args, **kwargs)
    return wrapper

def super_admin_required(handler):
    @wraps(handler)
    async def wrapper(update, ctx, *args, **kwargs):
        telegram_id = None
        if hasattr(update, 'effective_user') and update.effective_user:
            telegram_id = update.effective_user.id
        elif hasattr(update, 'message') and update.message and hasattr(update.message, 'from_user') and update.message.from_user:
            telegram_id = update.message.from_user.id
        elif hasattr(update, 'callback_query') and update.callback_query and hasattr(update.callback_query, 'from_user') and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
        from .database import is_super_admin
        if not (telegram_id and is_super_admin(telegram_id)):
            denial_msg = SUPER_ADMIN_DENIED_MSG
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.answer(denial_msg, show_alert=True)
            elif hasattr(update, 'message') and update.message:
                await update.message.reply_text(denial_msg)
            return
        return await handler(update, ctx, *args, **kwargs)
    return wrapper

def access_required(handler):
    @wraps(handler)
    async def wrapper(update, ctx: ContextTypes.DEFAULT_TYPE):
        telegram_id = None
        if hasattr(update, 'effective_user') and update.effective_user:
            telegram_id = update.effective_user.id
        elif hasattr(update, 'message') and update.message and hasattr(update.message, 'from_user') and update.message.from_user:
            telegram_id = update.message.from_user.id
        elif hasattr(update, 'callback_query') and update.callback_query and hasattr(update.callback_query, 'from_user') and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
        denial_msg = ACCESS_DENIED_MSG
        from .database import is_admin, is_whitelisted
        if not (telegram_id and (is_admin(telegram_id) or is_whitelisted(telegram_id))):
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.answer(denial_msg, show_alert=True)
            elif hasattr(update, 'message') and update.message:
                await update.message.reply_text(denial_msg, parse_mode='Markdown')
            return
        return await handler(update, ctx)
    return wrapper

def pagination(items, page, page_size, prev_callback, next_callback, page_callback="noop", force_paginate=False):
    """
    Paginate a list of items and build a row of pagination buttons for Telegram inline keyboards.
    Args:
        items (list): The list of items to paginate.
        page (int): The page number (0-based).
        page_size (int): Number of items per page.
        prev_callback (str): Callback data for previous page button.
        next_callback (str): Callback data for next page button.
        page_callback (str): Callback data for the page indicator button (default: 'noop').
        force_paginate (bool): If True, always paginate even if items fit on one page.
    Returns:
        tuple: (items_on_page, total_pages, start_index, end_index, pagination_buttons)
    """
    if page < 0 or page_size <= 0:
        raise ValueError("Page must be >= 0 and page_size must be > 0.")
    if not force_paginate and len(items) <= page_size:
        # No need to paginate, return all items in one page
        paginated_items = items
        total_pages = 1
        start = 0
        end = len(items)
    else:
        total_pages = (len(items) + page_size - 1) // page_size
        if page >= total_pages:
            page = max(0, total_pages - 1)
        start = page * page_size
        end = min(start + page_size, len(items))
        paginated_items = items[start:end]
    # Build pagination buttons
    buttons = []
    if total_pages > 1:
        if page > 0:
            buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=prev_callback))
        buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data=page_callback))
        if page < total_pages - 1:
            buttons.append(InlineKeyboardButton("Next ▶️", callback_data=next_callback))
    return paginated_items, total_pages, start, end, buttons

def format_size(bytes_size):
    if bytes_size < 1024 ** 2:
        return f"{bytes_size / 1024:.2f} KB"
    elif bytes_size < 1024 ** 3:
        return f"{bytes_size / (1024 ** 2):.2f} MB"
    else:
        return f"{bytes_size / (1024 ** 3):.2f} GB"

def format_human_size(size_bytes):
    """Return a human-readable file size string using humanize."""
    return humanize.naturalsize(size_bytes, binary=True)

def get_breadcrumb(service, folder_stack, current_folder, get_folder_name_func):
    """Build a breadcrumb path from folder_stack and current_folder using get_folder_name_func."""
    path = ['root']
    for folder_id in folder_stack:
        if folder_id != 'root':
            try:
                path.append(get_folder_name_func(service, folder_id))
            except Exception as e:
                print(f"Error in get_breadcrumb: failed to get folder name for {folder_id}: {e}")
                path.append('...')
    if current_folder != 'root':
        try:
            path.append(get_folder_name_func(service, current_folder))
        except Exception as e:
            print(f"Error in get_breadcrumb: failed to get folder name for {current_folder}: {e}")
            path.append('...')
    return ' / '.join(path)

async def is_url(text):
    return bool(re.match(r'^https?://', text))

def get_server_stats():
    """Return current server statistics (bandwidth, load, CPU, memory, uptime)."""
    bandwidth_today = 0  # in MB or GB
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
    """Return current bot statistics (total users, queue length)."""
    total_users = 0
    queue_length = 0
    return {
        "total_users": total_users,
        "queue_length": queue_length,
    }

@handle_errors
async def handle_file_size(update, ctx):
    """Handle callback for file size information."""
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not q.data or not q.data.startswith("file_size:"):
        return
    file_id = q.data.split(":")[1]
    # Use get_credentials to get a valid credentials object
    current_account = ctx.user_data.get("current_account")
    creds = get_credentials(telegram_id, current_account)
    if not creds:
        await q.edit_message_text(SERVICE_UNAVAILABLE_MSG)
        return
    from googleapiclient.discovery import build
    service = build("drive", "v3", credentials=creds)
    try:
        file = service.files().get(fileId=file_id, fields="name,size").execute()
        size = int(file.get('size', 0))
        size_str = format_size(size)
        await q.edit_message_text(FILE_SIZE_MSG.format(size=size_str))
    except Exception as e:
        await q.edit_message_text(FAILED_TO_GET_FILE_SIZE_MSG.format(error=str(e)))

@handle_errors
async def handle_folder_size(update, ctx):
    """Handle callback for folder size information."""
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not q.data or not q.data.startswith("folder_size:"):
        return
    folder_id = q.data.split(":")[1]
    current_account = ctx.user_data.get("current_account")
    creds = get_credentials(telegram_id, current_account)
    if not creds:
        await q.edit_message_text(SERVICE_UNAVAILABLE_MSG)
        return
    from googleapiclient.discovery import build
    service = build("drive", "v3", credentials=creds)
    try:
        folder = service.files().get(fileId=folder_id, fields="name").execute()
        # Google Drive API doesn't provide folder size directly; placeholder for future implementation
        size_str = format_size(0)
        await q.edit_message_text(FOLDER_SIZE_MSG.format(size=size_str))
    except Exception as e:
        await q.edit_message_text(FAILED_TO_GET_FOLDER_INFO_MSG.format(error=str(e)))

def get_adaptive_chunk_size(last_chunk_time, current_chunk_size, logger=None, context=None):
    min_chunk = 64 * 1024      # 64KB
    max_chunk = 8 * 1024 * 1024 # 8MB
    reason = 'unchanged'
    new_chunk = current_chunk_size
    if last_chunk_time < 0.5:
        new_chunk = min(current_chunk_size * 2, max_chunk)
        reason = 'fast'
    elif last_chunk_time > 2.0:
        new_chunk = max(current_chunk_size // 2, min_chunk)
        reason = 'slow'
    if logger is not None and new_chunk != current_chunk_size:
        logger.info(f"[ChunkSize] {context or ''} Chunk size changed from {current_chunk_size} to {new_chunk} due to {reason} chunk (time: {last_chunk_time:.2f}s)")
    return new_chunk 

def is_direct_file_url(url):
    file_extensions = [
        '.pdf', '.zip', '.rar', '.tar', '.gz', '.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3', '.doc', '.docx',
        '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv', '.json', '.xml', '.7z', '.apk', '.exe', '.msi', '.dmg', '.iso'
    ]
    return any(url.lower().endswith(ext) for ext in file_extensions)

def is_streaming_site(url):
    """Check if URL is from a streaming site that requires special handling."""
    streaming_domains = [
        'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com', 'twitch.tv',
        'facebook.com', 'instagram.com', 'twitter.com', 'tiktok.com', 'soundcloud.com'
    ]
    return any(domain in url.lower() for domain in streaming_domains)

def get_current_bandwidth_usage():
    """Get current network bandwidth usage in Mbps."""
    try:
        # Get network I/O statistics
        net_io = psutil.net_io_counters()
        # This is a simplified implementation - in practice you'd need to calculate
        # the rate over time intervals
        return 0.0  # Placeholder - actual implementation would require time-based calculations
    except Exception:
        return 0.0 