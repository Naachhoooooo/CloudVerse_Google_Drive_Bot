from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .drive import get_drive_service, get_storage_info
from .database import is_admin, is_whitelisted
from .Logger import get_logger
from .main import access_required
logger = get_logger()

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
                await update.message.reply_text("Please login first.")
            elif update.callback_query:
                await update.callback_query.edit_message_text("Please login first.")
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
        text = (
            f"📊 **Storage Details**\n\n"
            f"Account : {email}\n\n"
            f"Used : {used:.2f} GB of {limit:.2f} GB\n"
            f"Free : {free:.2f} GB of {limit:.2f} GB\n\n"
            f"Trash : {trash:.2f} GB of {limit:.2f} GB\n\n"
            f"Storage Used : {used_percent:.0f}%\n"
            f"Storage Free : {free_percent:.0f}%"
        )
        buttons = [
            [InlineKeyboardButton("♻️ Refresh", callback_data="refresh_storage")],
            [InlineKeyboardButton("✳️ Back", callback_data="back")]
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
            await update.message.reply_text("Failed to load storage details. Please try again later.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("Failed to load storage details. Please try again later.")

async def refresh_storage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await handle_storage(update, ctx)