from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .drive import get_drive_service, get_storage_info
from .database import is_admin, is_whitelisted
from .Logger import get_logger
from .Utilities import access_required
from .Utilities import handle_errors
logger = get_logger()

# Message constants (user-facing)
PLEASE_LOGIN_FIRST_MSG = "Please login first."
STORAGE_DETAILS_TEMPLATE = (
    "📊 **Storage Details**\n\n"
    "Account : {email}\n\n"
    "Used : {used:.2f} GB of {limit:.2f} GB\n"
    "Free : {free:.2f} GB of {limit:.2f} GB\n\n"
    "Trash : {trash:.2f} GB of {limit:.2f} GB\n\n"
    "Storage Used : {used_percent:.0f}%\n"
    "Storage Free : {free_percent:.0f}%"
)
REFRESH_BUTTON = "♻️ Refresh"
BACK_BUTTON = "✳️ Back"
FAILED_TO_LOAD_STORAGE_DETAILS_MSG = "Failed to load storage details. Please try again later."

@handle_errors
@access_required
async def handle_storage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        
        # Get telegram_id from either message or callback_query
        if update.message and update.message.from_user:
            telegram_id = update.message.from_user.id
            is_command = True
        elif update.callback_query and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
            is_command = False
        else:
            return
        
        service = get_drive_service(ctx.user_data.get('telegram_id')) if 'telegram_id' in ctx.user_data else None
        if not service:
            if update.message:
                await update.message.reply_text(PLEASE_LOGIN_FIRST_MSG)
            elif update.callback_query:
                await update.callback_query.edit_message_text(PLEASE_LOGIN_FIRST_MSG)
            return
        
        storage = get_storage_info(service)
        used = int(storage["storageQuota"]["usage"]) / (1024 ** 3)
        limit = int(storage["storageQuota"]["limit"]) / (1024 ** 3)
        free = limit - used
        trash = int(storage["storageQuota"].get("usageInDriveTrash", 0)) / (1024 ** 3)
        used_percent = (used / limit) * 100 if limit > 0 else 0
        free_percent = (free / limit) * 100 if limit > 0 else 0
        user_info = service.about().get(fields='user').execute()
        email = user_info['user']['emailAddress']
        text = STORAGE_DETAILS_TEMPLATE.format(
            email=email,
            used=used,
            limit=limit,
            free=free,
            trash=trash,
            used_percent=used_percent,
            free_percent=free_percent
        )
        buttons = [
            [InlineKeyboardButton(REFRESH_BUTTON, callback_data="refresh_storage")],
            [InlineKeyboardButton(BACK_BUTTON, callback_data="back")]
        ]
        
        try:
            # Handle both command and callback query responses
            if is_command and update.message:
                await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
            elif not is_command and update.callback_query:
                await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            import telegram
            if isinstance(e, telegram.error.BadRequest) and "Message is not modified" in str(e):
                pass
            else:
                logger.error(f"Error handling storage details: {e}")
    except Exception as e:
        logger.error(f"Error in handle_storage: {e}")
        if update.message:
            await update.message.reply_text(FAILED_TO_LOAD_STORAGE_DETAILS_MSG)
        elif update.callback_query:
            await update.callback_query.edit_message_text(FAILED_TO_LOAD_STORAGE_DETAILS_MSG)

async def refresh_storage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await handle_storage(update, ctx)