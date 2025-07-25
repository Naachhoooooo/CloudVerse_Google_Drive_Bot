import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .config import GROUP_CHAT_ID, TeamCloudverse_TOPIC_ID, DB_PATH
from datetime import datetime
from .Utilities import handle_errors
from .database import update_pending_user_group_message, get_pending_user_group_message, clear_pending_user_group_message

BOT_NAME_LINE = "Bot : CloudVerse Google Drive Bot"
NAME_LINE = "Name: {first_name} {last_name}"
USERNAME_LINE = "Username: @{username}"
ID_LINE = "ID: {telegram_id}"
REQUEST_STATUS_APPROVED = "Request Status : Approved"
REQUEST_STATUS_REJECTED = "Request Status : Rejected"
REQUEST_STATUS_LIMITED = "Request Status : Limited Access ({hours} hours)"
REQUEST_STATUS_UPDATED = "Request Status : {status}"
TIMESTAMP_LINE = "Timestamp: {timestamp}"
APPROVED_BY_BUTTON = "✅ Approved by @{admin_username}"
REJECTED_BY_BUTTON = "❌ Rejected by @{admin_username}"
LIMITED_BY_BUTTON = "⏳ Limited by @{admin_username}"
UPDATED_BY_BUTTON = "Updated by @{admin_username}"
BAN_STATUS_LINE = "Ban Status : {ban_status}"
BAN_TYPE_LINE = "Ban Type : {ban_type}"
BANNED_BY_BUTTON = "⛔️ Banned by @{admin_username}"
BAN_CANCELLED_BY_BUTTON = "❎ Ban Cancelled by @{admin_username}"
BROADCAST_REQUEST_TITLE = "🎙️ **Broadcast Request**\n\n"
APPROVE_BROADCAST_BUTTON = "🟢 Approve"
REJECT_BROADCAST_BUTTON = "🔴 Reject (Super Admin Only)"

def get_group_ids():
    """Return the group and topic IDs for TeamCloudverse group chat. Raises if not configured."""
    if GROUP_CHAT_ID is None or TeamCloudverse_TOPIC_ID is None:
        raise ValueError("Group chat or topic ID not configured.")
    return int(GROUP_CHAT_ID), int(TeamCloudverse_TOPIC_ID)

@handle_errors
async def handle_access_request(ctx, action, data):
    """Unified handler for access requests in the TeamCloudverse group (request, approve, reject, limit, update)."""
    chat_id, topic_id = get_group_ids()
    telegram_id = data.get('telegram_id')
    username = data.get('username')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    admin_username = data.get('admin_username')
    hours = data.get('hours')
    status = data.get('status')
    message = data.get('message')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if action == 'request':
        user_info = (
            BOT_NAME_LINE + "\n"
            + NAME_LINE.format(first_name=first_name, last_name=last_name) + "\n"
            + USERNAME_LINE.format(username=username or 'N/A') + "\n"
            + ID_LINE.format(telegram_id=telegram_id)
        )
        # Add custom message (e.g., expired user note)
        if message:
            user_info += f"\n{message}"
        buttons = [
            [InlineKeyboardButton("⏰ Limited Access", callback_data=f"access_limit:{telegram_id}"),
             InlineKeyboardButton("✅ Approve", callback_data=f"access_approve:{telegram_id}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"access_reject:{telegram_id}")]
        ]
        try:
            msg = await ctx.bot.send_message(
                chat_id=chat_id,
                text=user_info,
                message_thread_id=topic_id,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            # Store mapping in DB
            update_pending_user_group_message(telegram_id, msg.message_id)
        except Exception as e:
            pass
    elif action in ('approve', 'reject', 'limit', 'update'):
        # Update group message after action
        row = get_pending_user_group_message(telegram_id)
        if row and GROUP_CHAT_ID is not None and row is not None:
            message_id = row
            try:
                details = (
                    NAME_LINE.format(first_name=first_name, last_name=last_name) + "\n"
                    + USERNAME_LINE.format(username=username or 'N/A') + "\n"
                    + ID_LINE.format(telegram_id=telegram_id) + "\n\n"
                    + BOT_NAME_LINE + "\n"
                )
                if action == 'approve':
                    details += REQUEST_STATUS_APPROVED + "\n"
                    details += TIMESTAMP_LINE.format(timestamp=timestamp)
                    status_button = [[InlineKeyboardButton(APPROVED_BY_BUTTON.format(admin_username=admin_username), callback_data="noop")]]
                elif action == 'reject':
                    details += REQUEST_STATUS_REJECTED + "\n"
                    details += TIMESTAMP_LINE.format(timestamp=timestamp)
                    status_button = [[InlineKeyboardButton(REJECTED_BY_BUTTON.format(admin_username=admin_username), callback_data="noop")]]
                elif action == 'limit':
                    details += REQUEST_STATUS_LIMITED.format(hours=hours) + "\n"
                    details += TIMESTAMP_LINE.format(timestamp=timestamp)
                    status_button = [[InlineKeyboardButton(LIMITED_BY_BUTTON.format(admin_username=admin_username), callback_data="noop")]]
                else:
                    details += REQUEST_STATUS_UPDATED.format(status=status or 'Updated') + "\n"
                    details += TIMESTAMP_LINE.format(timestamp=timestamp)
                    status_button = [[InlineKeyboardButton(UPDATED_BY_BUTTON.format(admin_username=admin_username), callback_data="noop")]]
                await ctx.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=details,
                    reply_markup=InlineKeyboardMarkup(status_button)
                )
            except Exception as e:
                pass
            # Remove the mapping after handling
            clear_pending_user_group_message(telegram_id)

@handle_errors
async def handle_ban_request(ctx, action, data):
    """Unified handler for ban requests in the TeamCloudverse group (request, ban, cancel, update)."""
    chat_id, topic_id = get_group_ids()
    telegram_id = data.get('telegram_id')
    username = data.get('username')
    name = data.get('name')
    admin_username = data.get('admin_username')
    ban_status = data.get('ban_status')
    ban_type = data.get('ban_type')
    duration = data.get('duration')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if action == 'request':
        user_info = (
            BOT_NAME_LINE + "\n"
            + NAME_LINE.format(first_name=name, last_name="") + "\n"
            + USERNAME_LINE.format(username=username or 'N/A') + "\n"
            + ID_LINE.format(telegram_id=telegram_id)
        )
        buttons = [
            [InlineKeyboardButton("🚫Ban user", callback_data=f"ban_user_menu:{telegram_id}")]
        ]
        try:
            msg = await ctx.bot.send_message(
                chat_id=chat_id,
                text=user_info,
                message_thread_id=topic_id,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode='Markdown'
            )
            # Store mapping in DB
            update_pending_user_group_message(telegram_id, msg.message_id)
        except Exception as e:
            pass
    elif action in ('ban', 'cancel', 'update'):
        # Update group message after ban action
        row = get_pending_user_group_message(telegram_id)
        if row and GROUP_CHAT_ID is not None and row is not None:
            message_id = row
            try:
                details = (
                    NAME_LINE.format(first_name=name, last_name="") + "\n"
                    + USERNAME_LINE.format(username=username or 'N/A') + "\n"
                    + ID_LINE.format(telegram_id=telegram_id) + "\n\n"
                    + BOT_NAME_LINE + "\n"
                    + BAN_STATUS_LINE.format(ban_status=ban_status) + "\n"
                )
                if ban_status != "Cancelled" and ban_type:
                    details += BAN_TYPE_LINE.format(ban_type=ban_type) + "\n"
                details += TIMESTAMP_LINE.format(timestamp=timestamp)
                if action == 'ban':
                    status_button = [[InlineKeyboardButton(BANNED_BY_BUTTON.format(admin_username=admin_username), callback_data="noop")]]
                elif action == 'cancel':
                    status_button = [[InlineKeyboardButton(BAN_CANCELLED_BY_BUTTON.format(admin_username=admin_username), callback_data="noop")]]
                else:
                    status_button = [[InlineKeyboardButton(UPDATED_BY_BUTTON.format(admin_username=admin_username), callback_data="noop")]]
                await ctx.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=details,
                    reply_markup=InlineKeyboardMarkup(status_button)
                )
            except Exception as e:
                pass
            # Remove the mapping after handling
            clear_pending_user_group_message(telegram_id)

@handle_errors
async def handle_broadcast_request(ctx, action, data):
    """Unified handler for broadcast requests in the TeamCloudverse group (request, approve, reject, update)."""
    chat_id, topic_id = get_group_ids()
    request_id = data.get('request_id')
    message = data.get('message')
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    user_count = data.get('user_count')
    admin_username = data.get('admin_username')
    status = data.get('status')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if action == 'request':
        group_text = BROADCAST_REQUEST_TITLE + message
        buttons = [
            [InlineKeyboardButton(APPROVE_BROADCAST_BUTTON, callback_data=f"approve_broadcast:{request_id}"),
             InlineKeyboardButton(REJECT_BROADCAST_BUTTON, callback_data=f"reject_broadcast:{request_id}")]
        ]
        try:
            if media_type == "text" or not media_type:
                msg = await ctx.bot.send_message(
                    chat_id=chat_id,
                    text=group_text,
                    message_thread_id=topic_id,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode='Markdown'
                )
            elif media_type == "photo":
                msg = await ctx.bot.send_photo(
                    chat_id=chat_id,
                    photo=media_file_id,
                    caption=group_text,
                    message_thread_id=topic_id,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            elif media_type == "video":
                msg = await ctx.bot.send_video(
                    chat_id=chat_id,
                    video=media_file_id,
                    caption=group_text,
                    message_thread_id=topic_id,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            elif media_type == "document":
                msg = await ctx.bot.send_document(
                    chat_id=chat_id,
                    document=media_file_id,
                    caption=group_text,
                    message_thread_id=topic_id,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            elif media_type == "audio":
                msg = await ctx.bot.send_audio(
                    chat_id=chat_id,
                    audio=media_file_id,
                    caption=group_text,
                    message_thread_id=topic_id,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            elif media_type == "voice":
                msg = await ctx.bot.send_voice(
                    chat_id=chat_id,
                    voice=media_file_id,
                    caption=group_text,
                    message_thread_id=topic_id,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            # Store mapping in DB
            if request_id:
                update_pending_user_group_message(request_id, msg.message_id)
        except Exception as e:
            pass
    elif action in ('approve', 'reject', 'update'):
        # Update group message after action
        row = get_pending_user_group_message(request_id)
        if row and GROUP_CHAT_ID is not None and row is not None:
            message_id = row
            try:
                details = (
                    f"Broadcast Request\n\n"
                    f"Message: {message}\n"
                    f"Status: {status or action.capitalize()}\n"
                    f"Timestamp: {timestamp}"
                )
                if action == 'approve':
                    status_button = [[InlineKeyboardButton(f"✅ Approved by @{admin_username}", callback_data="noop")]]
                elif action == 'reject':
                    status_button = [[InlineKeyboardButton(f"❌ Rejected by @{admin_username}", callback_data="noop")]]
                else:
                    status_button = [[InlineKeyboardButton(f"Updated by @{admin_username}", callback_data="noop")]]
                await ctx.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=details,
                    reply_markup=InlineKeyboardMarkup(status_button)
                )
            except Exception as e:
                pass
            # Remove the mapping after handling
            clear_pending_user_group_message(request_id)

# --- Reports remain as is ---
@handle_errors
async def post_report(ctx, pdf_path, report_type, username):
    chat_id, topic_id = get_group_ids()
    try:
        with open(pdf_path, 'rb') as pdf_file:
            await ctx.bot.send_document(
                chat_id=chat_id,
                document=pdf_file,
                caption=f"📊 {report_type} Analytics Report\n\nGenerated by @{username}\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                message_thread_id=topic_id
            )
    except Exception as e:
        pass

# --- Deprecated wrappers for backward compatibility ---
@handle_errors
async def post_access_request(ctx, telegram_id, username, first_name, last_name):
    await handle_access_request(ctx, 'request', {
        'telegram_id': telegram_id,
        'username': username,
        'first_name': first_name,
        'last_name': last_name
    })

@handle_errors
async def post_ban_request(ctx, telegram_id, username, name):
    await handle_ban_request(ctx, 'request', {
        'telegram_id': telegram_id,
        'username': username,
        'name': name
    })

@handle_errors
async def post_broadcast(ctx, text, media_type=None, media_file_id=None, request_id=None, user_count=None):
    await handle_broadcast_request(ctx, 'request', {
        'request_id': request_id,
        'message': text,
        'media_type': media_type,
        'media_file_id': media_file_id,
        'user_count': user_count
    })

@handle_errors
async def update_group_ban_message_status(telegram_id, name, username, ban_status, ban_type, admin_username, ctx, status_button=None):
    await handle_ban_request(ctx, 'ban', {
        'telegram_id': telegram_id,
        'name': name,
        'username': username,
        'ban_status': ban_status,
        'ban_type': ban_type,
        'admin_username': admin_username
    }) 