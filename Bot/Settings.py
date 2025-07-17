from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from .drive import get_drive_service
from .config import SCOPES, CREDENTIALS_PATH
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from .FileManager import handle_file_manager
from .Logger import get_logger
logger = get_logger()

async def handle_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        buttons = [
            [InlineKeyboardButton("❇️ Login", callback_data="login")],
            [InlineKeyboardButton("❎ Logout", callback_data="logout")],
            [InlineKeyboardButton("👤 Switch Account", callback_data="switch_account")],
            [InlineKeyboardButton("📂 Default Upload Location", callback_data="update_def_location")],
            [InlineKeyboardButton("⚡️ Parallel Uploads", callback_data="update_parallel_uploads")],
            [InlineKeyboardButton("✳️ Back", callback_data="back")]
        ]
        if update.callback_query:
            await update.callback_query.edit_message_text("⚙️ Settings:", reply_markup=InlineKeyboardMarkup(buttons))
        elif update.message:
            await update.message.reply_text("⚙️ Settings:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error in handle_settings for user: {getattr(update, 'effective_user', None)}: {e}")
        if update.message:
            await update.message.reply_text("Failed to load settings. Please try again later.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("Failed to load settings. Please try again later.")

async def login(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES, redirect_uri='urn:ietf:wg:oauth:2.0:oob')
    auth_url, _ = flow.authorization_url(prompt='consent')
    msg = f"Please paste this url in your native browser or telegram browser and get the authorisation code and send back in chat.\n\nLink: {auth_url}"
    if update.callback_query:
        await update.callback_query.edit_message_text(msg)
    elif update.message:
        await update.message.reply_text(msg)
    ctx.user_data["flow"] = flow
    ctx.user_data["expecting_code"] = True

async def logout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    if update.callback_query and update.callback_query.from_user:
        telegram_id = update.callback_query.from_user.id
    else:
        return
    # Account management is no longer supported.
    buttons = [
        [InlineKeyboardButton("🔓 Logout Account", callback_data="logout_account")],
        [InlineKeyboardButton("🔐 Logout All", callback_data="logout_all_prompt")],
        [InlineKeyboardButton("✳️ Back", callback_data="back")]
    ]
    await update.callback_query.edit_message_text("Select an option:", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_logout_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    # Defensive fix for q.answer, q.data
    if q and hasattr(q, 'answer'):
        await q.answer()
    data = q.data if q and hasattr(q, 'data') else None
    if update.callback_query and update.callback_query.from_user:
        telegram_id = update.callback_query.from_user.id
    else:
        return
    if data == "logout_account":
        # Account management is no longer supported.
        if q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text("Account management is no longer supported.")
    elif data and isinstance(data, str) and data.startswith("logout_specific:"):
        email = data.split("logout_specific:")[1]
        ctx.user_data["expecting_logout_confirmation"] = f"Logout {email}"
        if q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text(f"Please confirm the logout by typing \"Logout {email}\"")
    elif data == "logout_all_prompt":
        ctx.user_data["expecting_logout_confirmation"] = "Logout All"
        if q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text("Please confirm the logout by typing \"Logout All\"")

async def switch_account_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    if update.callback_query and update.callback_query.from_user:
        telegram_id = update.callback_query.from_user.id
    else:
        return
    # Account management is no longer supported.
    buttons = [[InlineKeyboardButton("✳️ Back", callback_data="back")]]
    await update.callback_query.edit_message_text("Account management is no longer supported.", reply_markup=InlineKeyboardMarkup(buttons))

async def set_primary(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    # Defensive fix for update.callback_query.data.split
    if update.callback_query and hasattr(update.callback_query, 'data') and update.callback_query.data:
        email = update.callback_query.data.split(":", 1)[1]
    else:
        return
    if update.callback_query and update.callback_query.from_user:
        telegram_id = update.callback_query.from_user.id
    else:
        return
    # Account management is no longer supported.
    await update.callback_query.edit_message_text("Account management is no longer supported.")
    await handle_settings(update, ctx)

async def update_def_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    if update.callback_query and update.callback_query.from_user:
        telegram_id = update.callback_query.from_user.id
    else:
        return
    service = get_drive_service(telegram_id)
    ctx.user_data["in_def_location"] = True
    await handle_file_manager(update, ctx)

async def update_parallel_uploads(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    # Defensive fix for update.callback_query.edit_message_text
    if update.callback_query and hasattr(update.callback_query, 'edit_message_text'):
        await update.callback_query.edit_message_text("Enter the limit from 1 to 5 scale:")
    ctx.user_data["next_action"] = "set_parallel_uploads"