from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .database import is_admin
from .AccessControl import handle_access_control
from .TermsAndCondition import show_terms_and_conditions
import logging
from .UserState import UserStateEnum
from .Utilities import handle_errors

# Message constants (user-facing)
MAIN_MENU_TITLE = "Welcome to the Main Menu"
FAILED_TO_LOAD_MAIN_MENU_MSG = "Failed to load main menu. Please try again later."
SEARCH_MODE_ACTIVATED_MSG = (
    "🔍 <b>Search Mode Activated</b>\n\n"
    "Type your search query in the message bar and select the bot from the inline menu (above the keyboard) to search your Google Drive."
)
BACK_TO_MAIN_MENU_BUTTON = "✳️ Back to Main Menu"
FAILED_TO_PROCESS_MENU_ACTION_MSG = "Failed to process menu action. Please try again later."

BACK_BUTTON = "✳️ Back"

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Display the main menu with navigation buttons for all major bot features."""
    try:
        if update.effective_user and hasattr(update.effective_user, 'id'):
            telegram_id = update.effective_user.id
        else:
            return
        buttons = [
            [InlineKeyboardButton("📁 File Manager", callback_data="FILE_MGR"), InlineKeyboardButton("🔍 Search", callback_data="SEARCH")],
            [InlineKeyboardButton("🕶️Account Profile", callback_data="PROFILE"), InlineKeyboardButton("📊 Storage Details", callback_data="STORAGE")],
            [InlineKeyboardButton("🗑️ Recycle Bin", callback_data="BIN"), InlineKeyboardButton("⚙️ Settings", callback_data="SETTINGS")],
            [InlineKeyboardButton("🛡️ Team CloudVerse", callback_data="TEAM_CLOUDVERSE"), InlineKeyboardButton("📃 Terms of Use", callback_data="TERMS")]
        ]
        # Only add admin buttons for admins, with no hint for non-admins
        if is_admin(telegram_id):
            buttons.append([InlineKeyboardButton("🔑 Access Control", callback_data="ACCESS")])
            buttons.append([InlineKeyboardButton("👑 Admin Control", callback_data="ADMIN_CONTROL")])
        markup = InlineKeyboardMarkup(buttons)
        text = MAIN_MENU_TITLE
        if update.message:
            await update.message.reply_text(text, reply_markup=markup)
        else:
            if update.callback_query and hasattr(update.callback_query, 'edit_message_text'):
                await update.callback_query.edit_message_text(text, reply_markup=markup)
        if ctx.user_data is None:
            ctx.user_data = {}
        ctx.user_data["state"] = UserStateEnum.MENU
    except Exception as e:
        logging.error(f"Error in start menu for user: {locals().get('telegram_id', 'unknown')}: {e}")
        if update.message:
            await update.message.reply_text(FAILED_TO_LOAD_MAIN_MENU_MSG)
        elif update.callback_query and hasattr(update.callback_query, 'edit_message_text'):
            await update.callback_query.edit_message_text(FAILED_TO_LOAD_MAIN_MENU_MSG)

@handle_errors
async def handle_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle main menu button actions and route to the appropriate feature handler."""
    try:
        q = update.callback_query
        if q:
            await q.answer()
        cmd = q.data if q and hasattr(q, 'data') else getattr(update, 'data', None)
        from .FileManager import handle_file_manager
        from .AccountProfile import handle_profile
        from .StorageDetails import handle_storage
        from .RecycleBin import handle_bin
        from .Settings import handle_settings
        from .MessageForDeveloper import handle_cloudverse_support

        async def handle_search(u, c):
            # Activate inline mode with instructions and a back button
            c.user_data["state"] = UserStateEnum.SEARCH
            buttons = [[InlineKeyboardButton(BACK_TO_MAIN_MENU_BUTTON, callback_data="back")]]
            msg = SEARCH_MODE_ACTIVATED_MSG
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
            elif update.message:
                await update.message.reply_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))

        actions = {
            "FILE_MGR": handle_file_manager,
            "SEARCH": handle_search,
            "PROFILE": handle_profile,
            "STORAGE": handle_storage,
            "BIN": handle_bin,
            "SETTINGS": handle_settings,
            "TEAM_CLOUDVERSE": handle_cloudverse_support,
            "TERMS": show_terms_and_conditions,
            "ACCESS": handle_access_control,
            "back": start,
            "cancel": start
        }
        # Defensive fix for actions[cmd]
        if cmd in actions:
            await actions[cmd](update, ctx)
    except Exception as e:
        logging.error(f"Error in handle_menu for user: {locals().get('telegram_id', 'unknown')}: {e}")
        if update.message:
            await update.message.reply_text(FAILED_TO_PROCESS_MENU_ACTION_MSG)
        elif hasattr(update, 'callback_query') and update.callback_query and hasattr(update.callback_query, 'edit_message_text'):
            await update.callback_query.edit_message_text(FAILED_TO_PROCESS_MENU_ACTION_MSG)
