import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .database import is_admin, is_whitelisted
from .config import DB_PATH
from .main import access_required

logger = logging.getLogger(__name__)

@access_required
async def show_terms_and_conditions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    try:
        terms_path = os.path.join(os.path.dirname(__file__), 'TermsAndCondition.md')
        with open(terms_path, 'r', encoding='utf-8') as f:
            terms_text = f.read()
        if update.message:
            await update.message.reply_text(terms_text)
        elif update.callback_query:
            await update.callback_query.edit_message_text(terms_text)
    except Exception as e:
        logger.error(f"Error in show_terms_and_conditions: {e}")
        if update.message:
            await update.message.reply_text("Failed to load Terms and Conditions. Please try again later.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("Failed to load Terms and Conditions. Please try again later.")
    ctx.user_data["state"] = "TERMS" 