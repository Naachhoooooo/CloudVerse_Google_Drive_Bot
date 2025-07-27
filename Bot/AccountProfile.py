from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from .drive import get_drive_service, get_user_info, get_folder_name
from .database import get_user_default_folder_id, get_user_monthly_bandwidth, get_user_total_bandwidth, get_user_credentials, get_user_quota_info, is_admin
from datetime import datetime, timedelta
from .MainMenu import BACK_BUTTON
from .Utilities import handle_errors, format_size

from .Logger import get_logger
logger = get_logger(__name__)

# Message constants (user-facing)
FAILED_TO_LOAD_PROFILE_MSG = "Failed to load profile. Please try again later."

def generate_progress_bar(used, total, length=10):
    """Generate a visual progress bar using squares"""
    if total == 0:
        percentage = 0
    else:
        percentage = (used / total) * 100
    
    filled_squares = int((used / total) * length) if total > 0 else 0
    empty_squares = length - filled_squares
    
    progress_bar = "⬛" * filled_squares + "⬜" * empty_squares
    return progress_bar, percentage

def calculate_time_until_reset():
    """Calculate time until next day (quota reset)"""
    now = datetime.now()
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    time_diff = tomorrow - now
    
    hours = time_diff.seconds // 3600
    minutes = (time_diff.seconds % 3600) // 60
    seconds = time_diff.seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def format_quota_info(quota_info, is_user_admin=False):
    """Format quota information for display"""
    if is_user_admin:
        return (
            f"📊 <b>Daily Upload Quota</b>\n"
            f"Used quota: ∞ of ∞, balance: ∞\n"
            f"⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛ (∞%)\n"
            f"<i>Unlimited uploads for admins</i>\n"
        )
    
    used = quota_info['daily_used']
    total = quota_info['daily_limit']
    
    # Handle unlimited quota (0 means unlimited)
    if total == 0:
        return (
            f"📊 <b>Daily Upload Quota</b>\n"
            f"Used quota: {used} of ∞, balance: ∞\n"
            f"⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛ (∞%)\n"
            f"<i>Unlimited uploads granted</i>\n"
        )
    
    balance = total - used
    progress_bar, percentage = generate_progress_bar(used, total)
    time_until_reset = calculate_time_until_reset()
    
    return (
        f"📊 <b>Daily Upload Quota</b>\n"
        f"Used quota {used} of {total}, balance {balance}\n"
        f"{progress_bar} ({percentage:.1f}%)\n"
        f"Your quota will reset in {time_until_reset}.\n"
    )

# Define a local account_profile function to format the profile text

def account_profile(user_info, username, telegram_id, email, default_folder_name, parallel_uploads, monthly_bandwidth_bytes, overall_bandwidth_bytes, quota_info_text):
    # Format bandwidth using format_size for user-friendly display
    monthly_bandwidth_str = format_size(monthly_bandwidth_bytes) if monthly_bandwidth_bytes > 0 else "0 B"
    overall_bandwidth_str = format_size(overall_bandwidth_bytes) if overall_bandwidth_bytes > 0 else "0 B"
    
    return (
        f"👤 <b>Profile</b>\n"
        f"Username: @{username}\n"
        f"Telegram ID: <code>{telegram_id}</code>\n"
        f"Email: <code>{email}</code>\n"
        f"Default Upload Location: <code>{default_folder_name}</code>\n"
        f"Parallel Uploads: <code>{parallel_uploads}</code>\n"
        f"Monthly Bandwidth: <code>{monthly_bandwidth_str}</code>\n"
        f"Overall Bandwidth: <code>{overall_bandwidth_str}</code>\n\n"
        f"{quota_info_text}"
    )

@handle_errors
async def handle_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        if update.callback_query and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
            username = update.callback_query.from_user.username or 'N/A'
        elif update.message and update.message.from_user:
            telegram_id = update.message.from_user.id
            username = update.message.from_user.username or 'N/A'
        else:
            return
        
        # Get Google Drive service and user info
        service = get_drive_service(telegram_id)
        if not service:
            error_msg = "Please login to Google Drive first using /login"
            if update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            elif update.message:
                await update.message.reply_text(error_msg)
            return
        
        # Get user info from Google Drive API
        google_user_info = get_user_info(service)["user"]
        email = google_user_info.get("emailAddress", "N/A")
        
        # Get user settings from database
        user_creds = get_user_credentials(telegram_id)
        if user_creds:
            default_folder_id = user_creds.get("default_folder_id", "root")
            parallel_uploads = user_creds.get("parallel_uploads", 1)
        else:
            default_folder_id = "root"
            parallel_uploads = 1
        
        # Get folder name
        default_folder_name = get_folder_name(service, default_folder_id)
        
        # Get bandwidth data
        current_month = datetime.now().strftime("%Y-%m")
        monthly_bandwidth_bytes = get_user_monthly_bandwidth(telegram_id, current_month)
        overall_bandwidth_bytes = get_user_total_bandwidth(telegram_id)
        
        # Get quota information
        quota_info = get_user_quota_info(telegram_id)
        is_user_admin = is_admin(telegram_id)
        quota_info_text = format_quota_info(quota_info, is_user_admin)
        
        # Pass raw bytes to account_profile function for proper formatting
        text = account_profile(
            google_user_info,
            username,
            telegram_id,
            email,
            default_folder_name,
            parallel_uploads,
            monthly_bandwidth_bytes or 0,
            overall_bandwidth_bytes or 0,
            quota_info_text
        )
        
        buttons = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_profile")],
            [InlineKeyboardButton(BACK_BUTTON, callback_data="back")]
        ]
        markup = InlineKeyboardMarkup(buttons)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode='HTML')
        elif update.message:
            await update.message.reply_text(text, reply_markup=markup, parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"Error in handle_profile for user: {locals().get('telegram_id', 'unknown')}: {e}")
        error_msg = FAILED_TO_LOAD_PROFILE_MSG
        if update.message:
            await update.message.reply_text(error_msg)
        elif update.callback_query:
            await update.callback_query.edit_message_text(error_msg)

@handle_errors
async def handle_refresh_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle refresh button for profile page"""
    if update.callback_query:
        await update.callback_query.answer("Refreshing profile...")
        # Simply call handle_profile again to refresh the data
        await handle_profile(update, ctx)