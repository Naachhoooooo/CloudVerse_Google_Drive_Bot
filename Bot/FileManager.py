from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .drive import get_drive_service, list_files, create_folder, rename_file, delete_file, get_file_link, toggle_sharing
from .Utilities import paginate_list, get_breadcrumb, format_human_size
import humanize
import sqlite3
from .config import DB_PATH
import telegram
from .drive import get_folder_name
from .Logger import get_logger, log_error
from typing import Any
logger = get_logger()

DEFAULT_PAGE_SIZE = 10  # Configurable default page size for pagination

async def handle_file_manager(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the file manager UI, paginating files and folders if their count exceeds DEFAULT_PAGE_SIZE."""
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        q = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
        m = update.message if hasattr(update, 'message') and update.message else None
        telegram_id = None
        if q and q.from_user:
            telegram_id = q.from_user.id
        elif m and m.from_user:
            telegram_id = m.from_user.id
        else:
            logger.warning("handle_file_manager called without user context")
            return
        if "account_data" not in ctx.user_data or ctx.user_data["account_data"] is None:
            ctx.user_data["account_data"] = {}
        current_account = ctx.user_data.get("current_account") or "default_account"
        account_data = ctx.user_data["account_data"].setdefault(current_account, {
            "current_folder": "root", "folder_stack": [], "folder_pages": {}
        })
        if "folder_pages" not in account_data or account_data["folder_pages"] is None:
            account_data["folder_pages"] = {}
        current_folder = account_data["current_folder"]
        service = get_drive_service(telegram_id, current_account)
        files, _ = list_files(service, current_folder)
        folders = [f for f in files if f["mimeType"] == "application/vnd.google-apps.folder"]
        files_list = [f for f in files if f["mimeType"] != "application/vnd.google-apps.folder"]
        # Paginate folders and files if needed
        page = ctx.user_data.get("fm_page", 0)
        all_items = folders + files_list
        paged_items, total_pages, start_idx, end_idx = paginate_list(all_items, page, DEFAULT_PAGE_SIZE)
        paged_folders = [item for item in paged_items if item["mimeType"] == "application/vnd.google-apps.folder"]
        paged_files = [item for item in paged_items if item["mimeType"] != "application/vnd.google-apps.folder"]
        breadcrumb = get_breadcrumb(service, account_data['folder_stack'], current_folder, get_folder_name)
        text = f"File Manager ({current_account})\n{breadcrumb}\n\n"
        buttons = []
        buttons.append([InlineKeyboardButton("Folder Options ⚙️", callback_data=f"folder_options:{current_folder}")])
        buttons.extend([[InlineKeyboardButton(f"📂 {f['name']}", callback_data=f"folder:{f['id']}")] for f in paged_folders])
        buttons.extend([[InlineKeyboardButton(f"📄 {f['name']}", callback_data=f"file:{f['id']}")] for f in paged_files])
        if account_data["folder_stack"]:
            buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back_folder")])
        # Pagination controls
        if total_pages > 1:
            pagination = []
            if page > 0:
                pagination.append(InlineKeyboardButton("◀️ Prev", callback_data="fm_prev_page"))
            pagination.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
            if page < total_pages - 1:
                pagination.append(InlineKeyboardButton("Next ▶️", callback_data="fm_next_page"))
            buttons.append(pagination)
        buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back")])
        if q:
            try:
                await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            except Exception as e:
                import telegram
                if isinstance(e, telegram.error.BadRequest) and "Message is not modified" in str(e):
                    pass
                else:
                    log_error(e, context=f"handle_file_manager user_id={telegram_id}")
                    await q.edit_message_text("Failed to load file manager. Please try again later.")
        elif m:
            try:
                await m.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            except Exception as e:
                log_error(e, context=f"handle_file_manager user_id={telegram_id}")
                await m.reply_text("Failed to load file manager. Please try again later.")
        ctx.user_data["state"] = "FILE_MANAGER"
        ctx.user_data["fm_total_pages"] = total_pages
        ctx.user_data["fm_page"] = page
        logger.info(f"User {telegram_id} loaded file manager successfully. Files: {len(files)}")
    except Exception as e:
        log_error(e, context=f"handle_file_manager user_id={locals().get('telegram_id', 'unknown')}")
        if 'q' in locals() and q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text("Failed to load file manager. Please try again later.")
        elif 'm' in locals() and m:
            await m.reply_text("Failed to load file manager. Please try again later.")

async def handle_folder_navigation(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        q = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
        m = update.message if hasattr(update, 'message') and update.message else None
        if q and q.from_user:
            telegram_id = q.from_user.id
        elif m and m.from_user:
            telegram_id = m.from_user.id
        else:
            return
        if "account_data" not in ctx.user_data or ctx.user_data["account_data"] is None:
            ctx.user_data["account_data"] = {}
        current_account = ctx.user_data.get("current_account") or "default_account"
        account_data = ctx.user_data["account_data"].setdefault(current_account, {"current_folder": "root", "folder_stack": [], "folder_pages": {}})
        if "folder_pages" not in account_data or account_data["folder_pages"] is None:
            account_data["folder_pages"] = {}
        service = get_drive_service(telegram_id, current_account)
        data = q.data if q else (m.text if m else "")
        if not isinstance(data, str):
            return
        if data.startswith("folder:"):
            folder_id = data.split("folder:")[1]
            if ctx.user_data.get("in_def_location"):
                conn = sqlite3.connect(str(DB_PATH))
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET default_folder_id = ? WHERE telegram_id = ? AND account_email = ?", 
                               (folder_id, telegram_id, current_account))
                conn.commit()
                conn.close()
                ctx.user_data.pop("in_def_location")
                if q and hasattr(q, 'edit_message_text'):
                    await q.edit_message_text("Default Upload Location Updated Successfully")
            else:
                account_data["folder_stack"].append(account_data["current_folder"])
                account_data["current_folder"] = folder_id
                account_data["folder_pages"].pop(folder_id, None)
                await handle_file_manager(update, ctx)
        elif data == "back_folder":
            if account_data["folder_stack"]:
                account_data["current_folder"] = account_data["folder_stack"].pop()
                await handle_file_manager(update, ctx)
        elif data.startswith("next_page:"):
            folder_id = data.split("next_page:")[1]
            folder_pages = account_data["folder_pages"].get(folder_id) if account_data["folder_pages"] else None
            if folder_pages and folder_pages["current"] + 1 < len(folder_pages["tokens"]):
                folder_pages["current"] += 1
                await handle_file_manager(update, ctx)
        elif data.startswith("prev_page:"):
            folder_id = data.split("prev_page:")[1]
            folder_pages = account_data["folder_pages"].get(folder_id) if account_data["folder_pages"] else None
            if folder_pages and folder_pages["current"] > 0:
                folder_pages["current"] -= 1
                await handle_file_manager(update, ctx)
        elif data.startswith("switch_account:"):
            new_account = data.split("switch_account:")[1]
            ctx.user_data["current_account"] = new_account
            ctx.user_data["account_data"].setdefault(new_account, {"current_folder": "root", "folder_stack": [], "folder_pages": {}})
            await handle_file_manager(update, ctx)
    except Exception as e:
        log_error(e, context=f"handle_folder_navigation user_id={locals().get('telegram_id', 'unknown')}")
        if 'q' in locals() and q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text("Failed to navigate folders. Please try again later.")
        elif 'm' in locals() and m:
            await m.reply_text("Failed to navigate folders. Please try again later.")

async def handle_file_selection(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        q = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
        m = update.message if hasattr(update, 'message') and update.message else None
        if q and q.from_user:
            telegram_id = q.from_user.id
        elif m and m.from_user:
            telegram_id = m.from_user.id
        else:
            return
        current_account = ctx.user_data.get("current_account")
        service = get_drive_service(telegram_id, current_account)
        data = q.data if q else (m.text if m else "")
        if isinstance(data, str) and data.startswith("file:"):
            file_id = data.split("file:")[1]
            buttons = [
                [InlineKeyboardButton("✏️ Rename", callback_data=f"rename_file:{file_id}"),
                 InlineKeyboardButton("❎ Delete", callback_data=f"delete_file:{file_id}")],
                [InlineKeyboardButton("🔗 Copy Link", callback_data=f"copy_link:{file_id}"),
                 InlineKeyboardButton("💾 Size", callback_data=f"file_size:{file_id}")],
                [InlineKeyboardButton("✳️ Back", callback_data="back_to_folder")]
            ]
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text("File Toolkit:", reply_markup=InlineKeyboardMarkup(buttons))
        elif isinstance(data, str) and data.startswith("folder_options:"):
            folder_id = data.split("folder_options:")[1]
            if not service:
                if q and hasattr(q, 'edit_message_text'):
                    await q.edit_message_text("Please login first.")
                return
            permissions = service.permissions().list(fileId=folder_id).execute().get('permissions', [])
            sharing_status = "ON 🟢" if any(perm['type'] == 'anyone' for perm in permissions) else "OFF 🔴"
            buttons = [
                [InlineKeyboardButton("✏️ Rename", callback_data=f"rename_folder:{folder_id}"),
                 InlineKeyboardButton("❎ Delete", callback_data=f"delete_folder:{folder_id}")],
                [InlineKeyboardButton("📋 Copy Link", callback_data=f"copy_link:{folder_id}"),
                 InlineKeyboardButton(f"🔗 Link Sharing: {sharing_status}", callback_data=f"toggle_sharing:{folder_id}")],
                [InlineKeyboardButton("📁 New Folder", callback_data=f"new_folder:{folder_id}"),
                 InlineKeyboardButton("💾 Size", callback_data=f"folder_size:{folder_id}")],
                [InlineKeyboardButton("✳️ Back", callback_data="back_to_folder")]
            ]
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text("Folder Toolkit:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        log_error(e, context=f"handle_file_selection user_id={locals().get('telegram_id', 'unknown')}")
        if 'q' in locals() and q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text("Failed to select file or folder. Please try again later.")
        elif 'm' in locals() and m:
            await m.reply_text("Failed to select file or folder. Please try again later.")

async def handle_file_actions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handles file actions (rename, delete, etc.) in the file manager."""
    try:
        if ctx.user_data is None:
            ctx.user_data = {}
        q = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
        m = update.message if hasattr(update, 'message') and update.message else None
        if q and q.from_user:
            telegram_id = q.from_user.id
        elif m and m.from_user:
            telegram_id = m.from_user.id
        else:
            return
        current_account = ctx.user_data.get("current_account")
        service = get_drive_service(telegram_id, current_account)
        data = q.data if q else (m.text if m else "")
        if isinstance(data, str) and data.startswith("rename_file:"):
            file_id = data.split("rename_file:")[1]
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text("Enter new file name:")
            ctx.user_data["next_action"] = f"rename_file:{file_id}"
        elif isinstance(data, str) and data.startswith("delete_file:"):
            file_id = data.split("delete_file:")[1]
            buttons = [
                [InlineKeyboardButton("Yes, delete", callback_data=f"confirm_delete_file:{file_id}")],
                [InlineKeyboardButton("No, cancel", callback_data="back_to_folder")]
            ]
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text("Are you sure you want to delete this file? It will move to the Recycle Bin.", reply_markup=InlineKeyboardMarkup(buttons))
        elif isinstance(data, str) and data.startswith("confirm_delete_file:"):
            file_id = data.split("confirm_delete_file:")[1]
            delete_file(service, file_id)
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text("File moved to Recycle Bin.")
        elif isinstance(data, str) and data.startswith("copy_link:"):
            file_id = data.split("copy_link:")[1]
            link = get_file_link(service, file_id)
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text(f"Link: {link}")
        elif isinstance(data, str) and data.startswith("rename_folder:"):
            folder_id = data.split("rename_folder:")[1]
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text("Enter new folder name:")
            ctx.user_data["next_action"] = f"rename_folder:{folder_id}"
        elif isinstance(data, str) and data.startswith("delete_folder:"):
            folder_id = data.split("delete_folder:")[1]
            buttons = [
                [InlineKeyboardButton("Yes, delete", callback_data=f"confirm_delete_folder:{folder_id}")],
                [InlineKeyboardButton("No, cancel", callback_data="back_to_folder")]
            ]
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text("Are you sure you want to delete this folder? It will move to the Recycle Bin.", reply_markup=InlineKeyboardMarkup(buttons))
        elif isinstance(data, str) and data.startswith("confirm_delete_folder:"):
            folder_id = data.split("confirm_delete_folder:")[1]
            delete_file(service, folder_id)
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text("Folder moved to Recycle Bin.")
        elif isinstance(data, str) and data.startswith("toggle_sharing:"):
            file_id = data.split("toggle_sharing:")[1]
            toggle_sharing(service, file_id)
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text("Sharing toggled.")
            await handle_file_selection(update, ctx)  # Refresh to show updated status
        elif isinstance(data, str) and data.startswith("new_folder:"):
            folder_id = data.split("new_folder:")[1]
            if q and hasattr(q, 'edit_message_text'):
                await q.edit_message_text("Enter new folder name:")
            ctx.user_data["next_action"] = f"create_folder:{folder_id}"
        elif isinstance(data, str) and data.startswith("file_size:"):
            file_id = data.split(":")[1]
            # Defensive fix for service.files
            if service and hasattr(service, 'files'):
                file = service.files().get(fileId=file_id, fields="size, name").execute()
                size = int(file.get("size", 0))
                size_str = format_human_size(size)
                msg = f"Size of {file['name']}: {size_str}"
                if q:
                    await q.answer(msg, show_alert=True)
                elif m:
                    await m.reply_text(msg)
        elif isinstance(data, str) and data.startswith("folder_size:"):
            folder_id = data.split(":")[1]
            total_size = 0
            stack = [folder_id]
            while stack:
                current = stack.pop()
                files, _ = list_files(service, current)
                for f in files:
                    if f["mimeType"] == "application/vnd.google-apps.folder":
                        stack.append(f["id"])
                    else:
                        if service and hasattr(service, 'files'):
                            file_meta = service.files().get(fileId=f["id"], fields="size").execute()
                            total_size += int(file_meta.get("size", 0))
            size_str = format_human_size(total_size)
            msg = f"Total size of folder: {size_str}"
            if q:
                await q.answer(msg, show_alert=True)
            elif m:
                await m.reply_text(msg)
        elif isinstance(data, str) and data == "back_to_folder":
            await handle_file_manager(update, ctx)
    except Exception as e:
        log_error(e, context=f"handle_file_actions user_id={locals().get('telegram_id', 'unknown')}")
        if 'q' in locals() and q and hasattr(q, 'edit_message_text'):
            await q.edit_message_text("Failed to perform file action. Please try again later.")
        elif 'm' in locals() and m:
            await m.reply_text("Failed to perform file action. Please try again later.")

# Add handlers for pagination navigation
async def handle_fm_pagination(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles pagination for the file manager.
    """
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    data = q.data
    page = ctx.user_data.get("fm_page", 0)
    total_pages = ctx.user_data.get("fm_total_pages", 1)
    if data == "fm_prev_page":
        ctx.user_data["fm_page"] = max(0, page - 1)
    elif data == "fm_next_page":
        ctx.user_data["fm_page"] = min(total_pages - 1, page + 1)
    await handle_file_manager(update, ctx)