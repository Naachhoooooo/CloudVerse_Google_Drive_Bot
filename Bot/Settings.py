from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from .drive import get_drive_service
from .config import SCOPES, CREDENTIALS_PATH
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from .FileManager import handle_file_manager

buttons = [
    [InlineKeyboardButton("❇️ Login", callback_data="login")],
    [InlineKeyboardButton("❎ Logout", callback_data="logout")],
    [InlineKeyboardButton("👤 Switch Primary Account", callback_data="switch_account")],
    [InlineKeyboardButton("📂 Update Default Upload Location", callback_data="update_def_location")],
    [InlineKeyboardButton("⚡️ Update Parallel Uploads", callback_data="update_parallel_uploads")],
    [InlineKeyboardButton("✳️ Back", callback_data="back")]
]
if update.callback_query:
    await update.callback_query.edit_message_text(SETTINGS_TITLE, reply_markup=InlineKeyboardMarkup(buttons))
elif update.message:
    await update.message.reply_text(SETTINGS_TITLE, reply_markup=InlineKeyboardMarkup(buttons))

flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES, redirect_uri='urn:ietf:wg:oauth:2.0:oob')
auth_url, _ = flow.authorization_url(prompt='consent')
msg = LOGIN_PROMPT_MSG.format(auth_url=auth_url)
if update.callback_query:
    await update.callback_query.edit_message_text(msg)
elif update.message:
    await update.message.reply_text(msg)
ctx.user_data["flow"] = flow
ctx.user_data["expecting_code"] = True

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
await update.callback_query.edit_message_text(LOGOUT_SELECT_OPTION_MSG, reply_markup=InlineKeyboardMarkup(buttons))

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
        await q.edit_message_text(ACCOUNT_MANAGEMENT_NOT_SUPPORTED_MSG)
elif data and isinstance(data, str) and data.startswith("logout_specific:"):
    email = data.split("logout_specific:")[1]
    ctx.user_data["expecting_logout_confirmation"] = f"Logout {email}"
    if q and hasattr(q, 'edit_message_text'):
        await q.edit_message_text(LOGOUT_CONFIRM_MSG.format(email=email))
elif data == "logout_all_prompt":
    ctx.user_data["expecting_logout_confirmation"] = "Logout All"
    if q and hasattr(q, 'edit_message_text'):
        await q.edit_message_text(LOGOUT_ALL_CONFIRM_MSG)

if ctx.user_data is None:
    ctx.user_data = {}
if update.callback_query and update.callback_query.from_user:
    telegram_id = update.callback_query.from_user.id
else:
    return
accounts, primary, _ = get_user_accounts_and_primary(telegram_id)
buttons = []
if accounts:
    for email in accounts:
        label = f"{'⭐ ' if email == primary else ''}{email}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"set_primary:{email}")])
else:
    await update.callback_query.edit_message_text(NO_LINKED_ACCOUNTS_MSG, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✳️ Back", callback_data="back")]]))
    return
buttons.append([InlineKeyboardButton("✳️ Back", callback_data="back")])
await update.callback_query.edit_message_text(
    SELECT_PRIMARY_ACCOUNT_MSG,
    reply_markup=InlineKeyboardMarkup(buttons)
)

if ctx.user_data is None:
    ctx.user_data = {}
if update.callback_query and hasattr(update.callback_query, 'data') and update.callback_query.data:
    email = update.callback_query.data.split(":", 1)[1]
else:
    return
if update.callback_query and update.callback_query.from_user:
    telegram_id = update.callback_query.from_user.id
else:
    return
accounts, _, table = get_user_accounts_and_primary(telegram_id)
if not accounts or email not in accounts or not table:
    await update.callback_query.edit_message_text(INVALID_ACCOUNT_SELECTION_MSG)
    return
success = set_primary_account(telegram_id, email, table)
if success:
    ctx.user_data["current_account"] = email
    await update.callback_query.edit_message_text(PRIMARY_ACCOUNT_SET_MSG.format(email=email))
else:
    await update.callback_query.edit_message_text(FAILED_TO_SET_PRIMARY_MSG)
await handle_settings(update, ctx)

if ctx.user_data is None:
    ctx.user_data = {}
if update.callback_query and update.callback_query.from_user:
    telegram_id = update.callback_query.from_user.id
else:
    return
service = get_drive_service(telegram_id)
ctx.user_data["in_def_location"] = True
await handle_file_manager(update, ctx)

if ctx.user_data is None:
    ctx.user_data = {}
# Defensive fix for update.callback_query.edit_message_text
if update.callback_query and hasattr(update.callback_query, 'edit_message_text'):
    await update.callback_query.edit_message_text(ENTER_PARALLEL_UPLOAD_LIMIT_MSG)
ctx.user_data["next_action"] = "set_parallel_uploads"