from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .drive import get_drive_service, list_trashed_files, empty_trash, restore_file
from .Logger import get_logger
from typing import Any
from .Utilities import paginate_list
DEFAULT_PAGE_SIZE = 10  # Configurable default page size for pagination
logger = get_logger()

async def handle_bin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the recycle bin UI, paginating trashed files if their count exceeds DEFAULT_PAGE_SIZE.
    """
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        if update.message and update.message.from_user:
            telegram_id = update.message.from_user.id
            is_command = True
        elif update.callback_query and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
            is_command = False
        else:
            return
        service = get_drive_service(telegram_id)
        if not service:
            if is_command and update.message:
                await update.message.reply_text("Please login first.")
            elif not is_command and update.callback_query:
                await update.callback_query.edit_message_text("Please login first.")
            return
        files, next_token = list_trashed_files(service, ctx.user_data.get("bin_page_token") if isinstance(ctx.user_data, dict) else None)
        # Paginate trashed files if needed
        page = ctx.user_data.get("bin_page", 0)
        paged_files, total_pages, start_idx, end_idx = paginate_list(files, page, DEFAULT_PAGE_SIZE)
        ctx.user_data["current_bin_files"] = paged_files
        ctx.user_data["bin_next_token"] = next_token
        text = "🗑️ Recycle Bin:\n" + "\n".join(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}" for f in paged_files) or "Bin is empty."
        buttons = [[InlineKeyboardButton(f"{'📂' if f['mimeType'] == 'application/vnd.google-apps.folder' else '📄'} {f['name']}", callback_data=f"bin_item:{f['id']}")] for f in paged_files]
        # Pagination controls
        if total_pages > 1:
            pagination = []
            if page > 0:
                pagination.append(InlineKeyboardButton("◀️ Prev", callback_data="bin_prev_page"))
            pagination.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
            if page < total_pages - 1:
                pagination.append(InlineKeyboardButton("Next ▶️", callback_data="bin_next_page"))
            buttons.append(pagination)
        buttons.append([InlineKeyboardButton("🗑️ Empty Bin", callback_data="empty_bin")])
        buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back")])
        if is_command and update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        elif not is_command and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error in handle_bin for user: {locals().get('telegram_id', 'unknown')}: {e}")
        if update.message:
            await update.message.reply_text("Failed to load recycle bin. Please try again later.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("Failed to load recycle bin. Please try again later.")

async def handle_bin_navigation(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        q = update.callback_query
        if q and hasattr(q, 'answer'):
            await q.answer()
        data = q.data if q and hasattr(q, 'data') else ''
        if q and hasattr(q, 'from_user') and q.from_user:
            telegram_id = q.from_user.id
        else:
            return
        service = get_drive_service(telegram_id)
        if not service:
            await q.edit_message_text("Please login first.")
            return
        if ctx.user_data is None:
            ctx.user_data = {}
        if data == "bin_next_page":
            if isinstance(ctx.user_data, dict):
                ctx.user_data["bin_page_token"] = ctx.user_data.get("bin_next_token")
            await handle_bin(update, ctx)
        elif data == "bin_prev_page":
            if isinstance(ctx.user_data, dict):
                ctx.user_data["bin_page_token"] = None
            await handle_bin(update, ctx)
        elif isinstance(data, str) and data.startswith("bin_item:"):
            if isinstance(ctx.user_data, dict) and "current_bin_files" in ctx.user_data:
                file_id = data.split(":", 1)[1]
                file = next((f for f in ctx.user_data["current_bin_files"] if isinstance(f, dict) and f.get("id") == file_id), None)
                if file:
                    ctx.user_data["selected_bin_item"] = file
                    is_folder = file.get("mimeType") == "application/vnd.google-apps.folder"
                    buttons = [
                        [InlineKeyboardButton("✅ Restore", callback_data=f"restore:{file_id}")],
                        [InlineKeyboardButton("❎ Permanent Delete", callback_data=f"perm_delete:{file_id}")],
                        [InlineKeyboardButton("✳️ Back", callback_data="back_to_bin")]
                    ]
                    if q and hasattr(q, 'edit_message_text'):
                        await q.edit_message_text(f"{'Folder' if is_folder else 'File'} Toolkit:", reply_markup=InlineKeyboardMarkup(buttons))
        elif isinstance(data, str) and data.startswith("restore:"):
            if isinstance(ctx.user_data, dict):
                file = ctx.user_data.get("selected_bin_item")
                if file:
                    restore_file(service, file.get("id"))
                    if q and hasattr(q, 'edit_message_text'):
                        await q.edit_message_text(f"{'Folder' if file.get('mimeType') == 'application/vnd.google-apps.folder' else 'File'} : {file.get('name')} successfully restored")
        elif isinstance(data, str) and data.startswith("perm_delete:"):
            if isinstance(ctx.user_data, dict):
                file = ctx.user_data.get("selected_bin_item")
                if file:
                    is_folder = file.get("mimeType") == "application/vnd.google-apps.folder"
                    if q and hasattr(q, 'edit_message_text'):
                        await q.edit_message_text(f"“Are you sure want to delete the {'folder' if is_folder else 'file'}\nConfirmation Needed Enter “Delete””")
                    ctx.user_data["expecting_delete_confirmation"] = file
        elif data == "empty_bin":
            buttons = [
                [InlineKeyboardButton("Yes, empty", callback_data="confirm_empty_bin")],
                [InlineKeyboardButton("No, cancel", callback_data="back_to_bin")]
            ]
            await q.edit_message_text("Are you sure you want to empty the recycle bin? This action cannot be undone.", reply_markup=InlineKeyboardMarkup(buttons))
        elif data == "confirm_empty_bin":
            empty_trash(service)
            await q.edit_message_text("Trash emptied.")
        elif data == "back_to_bin":
            await handle_bin(update, ctx)
    except Exception as e:
        logger.error(f"Error in handle_bin_navigation for user: {locals().get('telegram_id', 'unknown')}: {e}")
        if q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text("Failed to process recycle bin navigation. Please try again later.")