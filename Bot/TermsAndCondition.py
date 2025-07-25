import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .database import is_admin, is_whitelisted
from .config import DB_PATH
from .Utilities import access_required
from .UserState import UserStateEnum

terms_path = os.path.join(os.path.dirname(__file__), 'TermsAndCondition.md')

@access_required
async def show_terms_and_conditions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    try:
        with open(terms_path, 'r', encoding='utf-8') as f:
            terms_text = f.read()
        if update.message:
            await update.message.reply_text(terms_text, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.edit_message_text(terms_text, parse_mode='Markdown')
    except Exception as e:
        if update.message:
            await update.message.reply_text(FAILED_TO_LOAD_TERMS_MSG)
        elif update.callback_query:
            await update.callback_query.edit_message_text(FAILED_TO_LOAD_TERMS_MSG)
    ctx.user_data["state"] = UserStateEnum.TERMS 