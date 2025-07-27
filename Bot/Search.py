from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
from .drive import search_files
import asyncio
from typing import Any
from .Utilities import pagination, handle_errors

from .Logger import get_logger
logger = get_logger(__name__)
DEFAULT_PAGE_SIZE = 10  # Configurable default page size for pagination

# Message constants (user-facing)
PREV_PAGE_BUTTON = "◀️ Prev"
NEXT_PAGE_BUTTON = "Next ▶️"
BACK_BUTTON = "✳️ Back"
NO_RESULTS_FOUND_MSG = "No results found."
SEARCH_RESULTS_TITLE = "Here are the search results for '{query}':\n\n{result}"
FAILED_TO_LOAD_SEARCH_RESULTS_MSG = "Failed to load search results. Please try again later."
FAILED_TO_LOAD_PREV_PAGE_MSG = "Failed to load previous page of search results. Please try again later."
FILE_TOOLKIT_TITLE = "File Toolkit:"
FAILED_TO_PROCESS_SEARCH_ITEM_MSG = "Failed to process search item. Please try again later."
INLINE_SEARCH_UNAVAILABLE_TITLE = "Inline search unavailable"
INLINE_SEARCH_UNAVAILABLE_MSG = "Please open the bot and press Search to use inline mode."
INLINE_SEARCH_NO_LOGIN_TITLE = "Please log in to use inline search"
INLINE_SEARCH_NO_LOGIN_MSG = "Please log in to the bot to use inline search."
NO_FILES_FOUND_TITLE = "No files found"
NO_MATCHING_FILES_MSG = "No matching files found in your Google Drive."
INLINE_QUERY_ERROR_TITLE = "Error"
INLINE_QUERY_ERROR_MSG = "Failed to process inline query. Please try again later."

@handle_errors
async def search_next_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination for search results, displaying the next page."""
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        if update.callback_query and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
        else:
            return
        # Use get_credentials if Drive API access is needed
        service = None # Placeholder, actual service initialization would go here
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
        paged_files, total_pages, start_idx, end_idx, pagination_buttons = pagination(files, page, DEFAULT_PAGE_SIZE, "search_prev_page", "search_next_page", page_callback="noop")
        buttons = [
            [InlineKeyboardButton(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}", callback_data=f"search_item:{f['id']}:{f['mimeType']}")]
            for f in paged_files
        ]
        # Add pagination controls to the buttons list
        if pagination_buttons:
            buttons.append(pagination_buttons)
        buttons.append([InlineKeyboardButton(BACK_BUTTON, callback_data="back")])
        result = "\n".join(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}" for f in paged_files) or NO_RESULTS_FOUND_MSG
        await update.callback_query.edit_message_text(SEARCH_RESULTS_TITLE.format(query=query, result=result), reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        if update.callback_query:
            await update.callback_query.edit_message_text(FAILED_TO_LOAD_SEARCH_RESULTS_MSG)

@handle_errors
async def search_prev_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle pagination for search results, displaying the previous page."""
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        if update.callback_query and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
        else:
            return
        # Use get_credentials if Drive API access is needed
        service = None # Placeholder, actual service initialization would go here
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
        page = ctx.user_data.get("search_page", 0)
        paged_files, total_pages, start_idx, end_idx, pagination_buttons = pagination(files, page, DEFAULT_PAGE_SIZE, "search_prev_page", "search_next_page", page_callback="noop")
        buttons = [
            [InlineKeyboardButton(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}", callback_data=f"search_item:{f['id']}:{f['mimeType']}")]
            for f in paged_files
        ]
        # Add pagination controls to the buttons list
        if pagination_buttons:
            buttons.append(pagination_buttons)
        buttons.append([InlineKeyboardButton(BACK_BUTTON, callback_data="back")])
        result = "\n".join(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}" for f in paged_files) or NO_RESULTS_FOUND_MSG
        if update.callback_query and hasattr(update.callback_query, 'edit_message_text'):
            await update.callback_query.edit_message_text(SEARCH_RESULTS_TITLE.format(query=query, result=result), reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        if update.callback_query and hasattr(update.callback_query, 'edit_message_text'):
            await update.callback_query.edit_message_text(FAILED_TO_LOAD_PREV_PAGE_MSG)

@handle_errors
async def handle_search_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Display file/folder toolkit options for a selected search result item."""
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
                buttons.append([InlineKeyboardButton(BACK_BUTTON, callback_data="back")])
                if q and hasattr(q, 'edit_message_text'):
                    await q.edit_message_text(FILE_TOOLKIT_TITLE, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        if q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text(FAILED_TO_PROCESS_SEARCH_ITEM_MSG)

@handle_errors
async def handle_inline_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle inline search queries, returning Google Drive file results or error messages."""
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
                    title=INLINE_SEARCH_UNAVAILABLE_TITLE,
                    input_message_content=InputTextMessageContent(INLINE_SEARCH_UNAVAILABLE_MSG)
                )
            ], cache_time=1)
            return
        # Use get_credentials if Drive API access is needed
        service = None # Placeholder, actual service initialization would go here
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
                    title=NO_FILES_FOUND_TITLE,
                    input_message_content=InputTextMessageContent(NO_MATCHING_FILES_MSG)
                )
            )
        await inline_query.answer(results, cache_time=1)
    except Exception as e:
        inline_query = getattr(update, 'inline_query', None)
        if inline_query:
            await inline_query.answer([
                InlineQueryResultArticle(
                    id='error',
                    title=INLINE_QUERY_ERROR_TITLE,
                    input_message_content=InputTextMessageContent(INLINE_QUERY_ERROR_MSG)
                )
            ], cache_time=1) 