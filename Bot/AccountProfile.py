from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from .drive import get_drive_service, get_user_info, get_folder_name
from datetime import datetime
from .MainMenu import BACK_BUTTON
from .Logger import get_logger
logger = get_logger()

# Define a local account_profile function to format the profile text

def account_profile(user_info, username, telegram_id, email, default_folder_name, parallel_uploads, monthly_bandwidth, overall_bandwidth):
    return (
        f"👤 <b>Profile</b>\n"
        f"Username: @{username}\n"
        f"Telegram ID: <code>{telegram_id}</code>\n"
        f"Email: <code>{email}</code>\n"
        f"Default Folder: <code>{default_folder_name}</code>\n"
        f"Parallel Uploads: <code>{parallel_uploads}</code>\n"
        f"Monthly Bandwidth: <code>{monthly_bandwidth} MB</code>\n"
        f"Overall Bandwidth: <code>{overall_bandwidth} MB</code>\n"
    )

async def handle_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        if update.callback_query and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
        elif update.message and update.message.from_user:
            telegram_id = update.message.from_user.id
        else:
            return
        user_info = get_user_info(get_drive_service(telegram_id))["user"]
        default_folder_id = user_info["default_folder_id"]
        default_folder_name = get_folder_name(get_drive_service(telegram_id), default_folder_id)
        # Calculate monthly and overall bandwidth
        current_month = datetime.now().strftime("%Y-%m")
        if update.callback_query and update.callback_query.from_user:
            username = update.callback_query.from_user.username or 'N/A'
        elif update.message and update.message.from_user:
            username = update.message.from_user.username or 'N/A'
        else:
            username = 'N/A'
        text = account_profile(
            user_info,
            username,
            telegram_id,
            user_info['email'],
            default_folder_name,
            user_info['parallel_uploads'],
            user_info['monthly_bandwidth'],
            user_info['overall_bandwidth']
        )
        buttons = [[InlineKeyboardButton(BACK_BUTTON, callback_data="back")]]
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        elif update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error in handle_profile for user: {locals().get('telegram_id', 'unknown')}: {e}")
        if update.message:
            await update.message.reply_text("Failed to load profile. Please try again later.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("Failed to load profile. Please try again later.")