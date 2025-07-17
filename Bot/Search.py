from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
from .drive import get_drive_service, search_files
import asyncio
from .Logger import get_logger
from typing import Any
from .Utilities import paginate_list
DEFAULT_PAGE_SIZE = 10  # Configurable default page size for pagination
logger = get_logger()

async def search_next_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles pagination for search results using paginate_list.
    """
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        if update.callback_query and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
        else:
            return
        service = get_drive_service(telegram_id)
        query = ''
        if update.callback_query and hasattr(update.callback_query, 'message') and update.callback_query.message:
            msg = update.callback_query.message
            from telegram import Message
            if isinstance(msg, Message) and hasattr(msg, 'text') and isinstance(msg.text, str):
                query = msg.text.split('\n', 1)[0].replace("Here are search results for “", "").split("”")[0].strip()
        files, next_token = search_files(service, query, ctx.user_data["search_next_token"])
        ctx.user_data["search_prev_token"] = ctx.user_data["search_next_token"]
        ctx.user_data["search_results"] = files
        ctx.user_data["search_next_token"] = next_token
        # Paginate search results if needed
        page = ctx.user_data.get("search_page", 0)
        paged_files, total_pages, start_idx, end_idx = paginate_list(files, page, DEFAULT_PAGE_SIZE)
        buttons = [
            [InlineKeyboardButton(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}", callback_data=f"search_item:{f['id']}:{f['mimeType']}")]
            for f in paged_files
        ]
        if page > 0:
            buttons.append([InlineKeyboardButton("◀️ Prev", callback_data="search_prev_page")])
        if next_token or page < total_pages - 1:
            buttons.append([InlineKeyboardButton("Next ▶️", callback_data="search_next_page")])
        buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back")])
        result = "\n".join(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}" for f in paged_files) or "No results found."
        await update.callback_query.edit_message_text(f"Here are the search results for '{query}':\n\n{result}", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error in search_next_page for user: {locals().get('telegram_id', 'unknown')}: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text("Failed to load search results. Please try again later.")

async def search_prev_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        if update.callback_query and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
        else:
            return
        service = get_drive_service(telegram_id)
        query = ''
        if update.callback_query and hasattr(update.callback_query, 'message') and update.callback_query.message:
            msg = update.callback_query.message
            from telegram import Message
            if isinstance(msg, Message) and hasattr(msg, 'text') and isinstance(msg.text, str):
                query = msg.text.split('\n', 1)[0].replace("Here are search results for “", "").split("”")[0].strip()
        files, _ = search_files(service, query, ctx.user_data["search_prev_token"])
        ctx.user_data["search_results"] = files
        ctx.user_data["search_next_token"] = ctx.user_data["search_prev_token"]
        ctx.user_data["search_prev_token"] = None
        buttons = [
            [InlineKeyboardButton(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}", callback_data=f"search_item:{f['id']}:{f['mimeType']}")]
            for f in files
        ]
        if ctx.user_data["search_next_token"]:
            buttons.append([InlineKeyboardButton("Next ▶️", callback_data="search_next_page")])
        buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back")])
        result = "\n".join(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}" for f in files) or "No results found."
        if update.callback_query and hasattr(update.callback_query, 'edit_message_text'):
            await update.callback_query.edit_message_text(f"Here are the search results for '{query}':\n\n{result}", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error in search_prev_page for user: {locals().get('telegram_id', 'unknown')}: {e}")
        if update.callback_query and hasattr(update.callback_query, 'edit_message_text'):
            await update.callback_query.edit_message_text("Failed to load previous page of search results. Please try again later.")

async def handle_search_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        q = update.callback_query
        if q and hasattr(q, 'answer'):
            await q.answer()
        if q and hasattr(q, 'data') and isinstance(q.data, str):
            data = q.data
            if data.startswith("search_item:"):
                _, file_id, mime_type = data.split(":", 2)
                is_folder = mime_type == "application/vnd.google-apps.folder"
                buttons = [
                    [InlineKeyboardButton("✏️ Rename", callback_data=f"rename_{'folder' if is_folder else 'file'}:{file_id}")],
                    [InlineKeyboardButton("❎ Delete", callback_data=f"delete_{'folder' if is_folder else 'file'}:{file_id}")],
                    [InlineKeyboardButton("🔗 Copy Link", callback_data=f"copy_link:{file_id}")],
                ]
                if is_folder:
                    buttons.insert(2, [InlineKeyboardButton("🔗 Link Sharing: Toggle", callback_data=f"toggle_sharing:{file_id}")])
                buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back")])
                if q and hasattr(q, 'edit_message_text'):
                    await q.edit_message_text("File Toolkit:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error in handle_search_item for user: {locals().get('telegram_id', 'unknown')}: {e}")
        if q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text("Failed to process search item. Please try again later.")

async def handle_inline_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        inline_query = getattr(update, 'inline_query', None)
        if not inline_query:
            return
        query = getattr(inline_query, 'query', '')
        user = getattr(inline_query, 'from_user', None)
        user_id = getattr(user, 'id', None)
        if not user_id:
            return
        user_state = ctx.user_data.get('state') if ctx.user_data else None
        if user_state != 'SEARCH':
            await inline_query.answer([
                InlineQueryResultArticle(
                    id='not_in_search',
                    title='Inline search unavailable',
                    input_message_content=InputTextMessageContent('Please open the bot and press Search to use inline mode.')
                )
            ], cache_time=1)
            return
        service = get_drive_service(user_id)
        if not service:
            await inline_query.answer([
                InlineQueryResultArticle(
                    id='no_login',
                    title='Please log in to use inline search',
                    input_message_content=InputTextMessageContent('Please log in to the bot to use inline search.')
                )
            ], cache_time=1)
            return
        files, _ = search_files(service, query)
        results = []
        for f in files[:10]:
            file_url = f"https://drive.google.com/file/d/{f['id']}/view"
            results.append(
                InlineQueryResultArticle(
                    id=f["id"],
                    title=f["name"],
                    description=f.get("mimeType", ""),
                    input_message_content=InputTextMessageContent(f"Google Drive file: {f['name']}\n{file_url}")
                )
            )
        if not results:
            results.append(
                InlineQueryResultArticle(
                    id='no_results',
                    title='No files found',
                    input_message_content=InputTextMessageContent('No matching files found in your Google Drive.')
                )
            )
        await inline_query.answer(results, cache_time=1)
    except Exception as e:
        logger.error(f"Error in handle_inline_query for user: {locals().get('user_id', 'unknown')}: {e}")
        inline_query = getattr(update, 'inline_query', None)
        if inline_query:
            await inline_query.answer([
                InlineQueryResultArticle(
                    id='error',
                    title='Error',
                    input_message_content=InputTextMessageContent('Failed to process inline query. Please try again later.')
                )
            ], cache_time=1) 