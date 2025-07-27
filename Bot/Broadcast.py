from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .database import (
    is_admin, is_super_admin, create_broadcast_request, get_broadcast_request, update_broadcast_status, store_broadcast_group_message, get_broadcast_group_message,
    update_broadcast_approvers, get_whitelisted_users_except_admins
)
from .config import TeamCloudverse_TOPIC_ID, GROUP_CHAT_ID
import uuid
from datetime import datetime
from .TeamCloudverse import handle_broadcast_request
from .Utilities import handle_errors, admin_required

from .Logger import admin_logger as logger

NO_PERMISSION_ADMIN_CONTROLS_MSG = "You don't have permission to access Admin Controls."
BROADCAST_TITLE = "🎙️ Broadcast Message\n\n"
BROADCAST_TARGET_MSG = "📊 This message will be sent to {user_count} users (whitelisted users excluding admins).\n\n"
BROADCAST_SEND_PROMPT = "📝 Please send your broadcast message (text, photo, video, document, or audio).\n"
BROADCAST_APPROVAL_REQUIRED = "⚠️ This action requires approval before sending."
UNSUPPORTED_MEDIA_TYPE_MSG = "❌ Unsupported media type. Please send text, photo, video, document, or audio."
FAILED_TO_CREATE_BROADCAST_REQUEST_MSG = "Failed to create broadcast request."
SUPER_ADMIN_BROADCAST_APPROVAL_TITLE = "👑 **Super Admin Broadcast Approval**\n\n"
SUPER_ADMIN_BROADCAST_APPROVAL_TARGET = "📊 Target: {user_count} users\n"
SUPER_ADMIN_BROADCAST_APPROVAL_MESSAGE = "📝 Message: {message}\n"
SUPER_ADMIN_BROADCAST_APPROVAL_MEDIA = "📎 Media: {media_type}\n"
SUPER_ADMIN_BROADCAST_APPROVAL_NOTE = "\n⚠️ As Super Admin, you can approve this broadcast directly."
APPROVE_AND_SEND_BUTTON = "✅ Approve & Send"
CANCEL_BUTTON = "❌ Cancel"
GROUP_CHAT_NOT_CONFIGURED_MSG = "❌ Group chat or topic not configured for broadcast approval."
BROADCAST_SENT_TO_GROUP_MSG = "Broadcast sent to group."
FAILED_TO_SEND_BROADCAST_REQUEST_MSG = "Failed to send broadcast request to group: {error}"
FAILED_TO_SEND_BROADCAST_MSG = "Failed to send broadcast."
NO_PERMISSION_APPROVE_BROADCAST_MSG = "You don't have permission to approve broadcasts."
ONLY_SUPER_ADMIN_REJECT_MSG = "❌ Only Super Admin can reject broadcasts."
BROADCAST_REQUEST_NOT_FOUND_MSG = "❌ Broadcast request not found."
BROADCAST_APPROVED_BY_SUPER_ADMIN_MSG = "✅ **Broadcast Approved by Super Admin**\n\n"
BROADCAST_APPROVED_BY_MSG = "👑 Approved by: @{approver_username}\n"
BROADCAST_APPROVED_TARGET_MSG = "📊 Target: {target_count} users\n"
BROADCAST_APPROVED_MESSAGE_MSG = "📝 Message: {message}\n"
BROADCAST_SENT_SUCCESS_MSG = "\n✅ **Broadcast sent successfully!**"
BROADCASTED_BY_SUPER_ADMIN_BUTTON = "Broadcasted by Super Admin"

@handle_errors
async def handle_broadcast_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Initiate the broadcast message flow for admins, prompting for message content and approval."""
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.edit_message_text(NO_PERMISSION_ADMIN_CONTROLS_MSG)
        return
    whitelisted_users = get_whitelisted_users_except_admins()
    user_count = len(whitelisted_users)
    text = BROADCAST_TITLE
    text += BROADCAST_TARGET_MSG.format(user_count=user_count)
    text += BROADCAST_SEND_PROMPT
    text += BROADCAST_APPROVAL_REQUIRED
    buttons = [[InlineKeyboardButton(CANCEL_BUTTON, callback_data="admin_control")]]
    ctx.user_data["awaiting_broadcast_message"] = True
    ctx.user_data["broadcast_users"] = whitelisted_users
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@handle_errors
async def handle_broadcast_media_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle incoming media or text for broadcast, create a broadcast request, and route for approval."""
    if ctx.user_data is None:
        ctx.user_data = {}
    if not ctx.user_data.get("awaiting_broadcast_message"):
        return
    if not update.message or not update.message.from_user:
        return
    telegram_id = update.message.from_user.id
    username = update.message.from_user.username
    if not is_admin(telegram_id):
        return
    request_id = str(uuid.uuid4())
    broadcast_users = ctx.user_data.get("broadcast_users", [])
    user_count = len(broadcast_users)
    message_text = ""
    media_type = None
    media_file_id = None
    if update.message.text:
        message_text = update.message.text
        media_type = "text"
    elif update.message.photo:
        message_text = update.message.caption or ""
        media_type = "photo"
        media_file_id = update.message.photo[-1].file_id
    elif update.message.video:
        message_text = update.message.caption or ""
        media_type = "video"
        media_file_id = update.message.video.file_id
    elif update.message.document:
        message_text = update.message.caption or ""
        media_type = "document"
        media_file_id = update.message.document.file_id
    elif update.message.audio:
        message_text = update.message.caption or ""
        media_type = "audio"
        media_file_id = update.message.audio.file_id
    elif update.message.voice:
        message_text = update.message.caption or ""
        media_type = "voice"
        media_file_id = update.message.voice.file_id
    else:
        await update.message.reply_text(UNSUPPORTED_MEDIA_TYPE_MSG)
        return
    success = create_broadcast_request(request_id, telegram_id, username, message_text, media_type, media_file_id, user_count)
    if not success:
        await update.message.reply_text(FAILED_TO_CREATE_BROADCAST_REQUEST_MSG)
        return
    if is_super_admin(telegram_id):
        await handle_super_admin_broadcast_approval(update, ctx)
    else:
        await handle_regular_admin_broadcast_approval(update, ctx)
    ctx.user_data.pop("awaiting_broadcast_message", None)
    ctx.user_data.pop("broadcast_users", None)

@handle_errors
async def handle_super_admin_broadcast_approval(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handles both the initial approval UI and callback for super admin broadcast approval."""
    q = update.callback_query
    if q and q.data:
        data = q.data
        if data.startswith("super_approve_broadcast:"):
            request_id = data.split(":")[1]
            request = get_broadcast_request(request_id)
            if not request:
                await q.edit_message_text(BROADCAST_REQUEST_NOT_FOUND_MSG)
                return
            approver_username = q.from_user.username or "Super Admin"
            update_broadcast_status(request_id, "approved")
            await send_broadcast_message(ctx, request)
            text = BROADCAST_APPROVED_BY_SUPER_ADMIN_MSG
            text += BROADCAST_APPROVED_BY_MSG.format(approver_username=approver_username)
            text += BROADCAST_APPROVED_TARGET_MSG.format(target_count=request['target_count'])
            text += BROADCAST_APPROVED_MESSAGE_MSG.format(message=request['message_text'][:100] + ('...' if len(request['message_text']) > 100 else ''))
            text += BROADCAST_SENT_SUCCESS_MSG
            await q.edit_message_text(text)
            if GROUP_CHAT_ID is not None and TeamCloudverse_TOPIC_ID is not None:
                forward_text = f"📢 **Broadcast by Super Admin**\n\n"
                forward_text += f"📝 Message: {request['message_text']}\n"
                forward_text += f"📊 Target: {request['target_count']} users\n"
                forward_buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton(BROADCASTED_BY_SUPER_ADMIN_BUTTON, callback_data="noop")]
                ])
                try:
                    if request['media_type'] == "text":
                        await ctx.bot.send_message(
                            chat_id=int(GROUP_CHAT_ID),
                            text=forward_text,
                            message_thread_id=int(TeamCloudverse_TOPIC_ID),
                            reply_markup=forward_buttons
                        )
                    elif request['media_type'] == "photo":
                        await ctx.bot.send_photo(
                            chat_id=int(GROUP_CHAT_ID),
                            photo=request['media_file_id'],
                            caption=forward_text,
                            message_thread_id=int(TeamCloudverse_TOPIC_ID),
                            reply_markup=forward_buttons
                        )
                    elif request['media_type'] == "video":
                        await ctx.bot.send_video(
                            chat_id=int(GROUP_CHAT_ID),
                            video=request['media_file_id'],
                            caption=forward_text,
                            message_thread_id=int(TeamCloudverse_TOPIC_ID),
                            reply_markup=forward_buttons
                        )
                    elif request['media_type'] == "document":
                        await ctx.bot.send_document(
                            chat_id=int(GROUP_CHAT_ID),
                            document=request['media_file_id'],
                            caption=forward_text,
                            message_thread_id=int(TeamCloudverse_TOPIC_ID),
                            reply_markup=forward_buttons
                        )
                    elif request['media_type'] == "audio":
                        await ctx.bot.send_audio(
                            chat_id=int(GROUP_CHAT_ID),
                            audio=request['media_file_id'],
                            caption=forward_text,
                            message_thread_id=int(TeamCloudverse_TOPIC_ID),
                            reply_markup=forward_buttons
                        )
                    elif request['media_type'] == "voice":
                        await ctx.bot.send_voice(
                            chat_id=int(GROUP_CHAT_ID),
                            voice=request['media_file_id'],
                            caption=forward_text,
                            message_thread_id=int(TeamCloudverse_TOPIC_ID),
                            reply_markup=forward_buttons
                        )
                except Exception:
                    pass
            return
        elif data.startswith("reject_broadcast:"):
            if not is_super_admin(q.from_user.id):
                await q.answer(ONLY_SUPER_ADMIN_REJECT_MSG)
                return
            request_id = data.split(":")[1]
            update_broadcast_status(request_id, "rejected")
            rejector_username = q.from_user.username or "Unknown"
            text = f"❌ **Broadcast Rejected by Super Admin**\n\n"
            text += f"👑 **Rejected by:** @{rejector_username} (Super Admin)\n"
            text += f"⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            text += f"🔒 **Reason:** Super Admin decision"
            await q.edit_message_text(text)
            return
    if ctx.user_data is None:
        ctx.user_data = {}
    if not ctx.user_data.get("awaiting_broadcast_message"):
        return
    if not update.message or not update.message.from_user:
        return
    telegram_id = update.message.from_user.id
    if not is_admin(telegram_id):
        return
    request_id = str(uuid.uuid4())
    broadcast_users = get_whitelisted_users_except_admins()
    user_count = len(broadcast_users)
    text = BROADCAST_TITLE
    text += BROADCAST_TARGET_MSG.format(user_count=user_count)
    text += BROADCAST_SEND_PROMPT
    text += BROADCAST_APPROVAL_REQUIRED
    buttons = [[InlineKeyboardButton(CANCEL_BUTTON, callback_data="admin_control")]]
    ctx.user_data["awaiting_broadcast_message"] = True
    ctx.user_data["broadcast_users"] = broadcast_users
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@handle_errors
async def handle_regular_admin_broadcast_approval(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handles both the initial approval UI and callback for regular admin broadcast approval with two approval buttons."""
    q = update.callback_query
    if q and q.data:
        data = q.data
        if data.startswith("approve_broadcast:"):
            request_id = data.split(":")[1]
            approver_id = str(q.from_user.id)
            approver_username = q.from_user.username or "Unknown"
            request = get_broadcast_request(request_id)
            if not request:
                await q.edit_message_text(BROADCAST_REQUEST_NOT_FOUND_MSG)
                return
            approvers = request.get('approvers', [])
            if not any(a['id'] == approver_id for a in approvers) and len(approvers) < 2:
                approvers.append({'id': approver_id, 'username': approver_username})
                update_broadcast_approvers(request_id, approvers)
            if len(approvers) == 2:
                update_broadcast_status(request_id, "approved")
                await send_broadcast_message(ctx, request)
                group_message_id = get_broadcast_group_message(request_id)
                if group_message_id and GROUP_CHAT_ID:
                    approver_names = [f"@{approval['username']}" for approval in approvers]
                    text = f"✅ **Broadcast Approved**\n\n"
                    text += f"👤 **Requester:** @{request['requester_username']}\n"
                    text += f"📊 **Target:** {request['target_count']} users\n"
                    text += f"📝 **Message:** {request['message_text'][:100]}{'...' if len(request['message_text']) > 100 else ''}\n"
                    text += f"✅ **Approved by:** {', '.join(approver_names)}\n"
                    text += f"⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    text += f"\n✅ **Broadcast sent successfully!**"
                    try:
                        await ctx.bot.edit_message_text(
                            chat_id=int(GROUP_CHAT_ID),
                            message_id=int(group_message_id),
                            text=text
                        )
                    except Exception:
                        pass
                return
            group_message_id = get_broadcast_group_message(request_id)
            if group_message_id and GROUP_CHAT_ID:
                button_labels = []
                for i in range(2):
                    if i < len(approvers):
                        button_labels.append(f"Approved by @{approvers[i]['username']}")
                    else:
                        button_labels.append("Approval Needed")
                buttons = [
                    [
                        InlineKeyboardButton(button_labels[0], callback_data=f"approve_broadcast:{request_id}"),
                        InlineKeyboardButton(button_labels[1], callback_data=f"approve_broadcast:{request_id}")
                    ],
                    [
                        InlineKeyboardButton("🔴 Reject (Super Admin Only)", callback_data=f"reject_broadcast:{request_id}")
                    ]
                ]
                approver_names = [f"@{approval['username']}" for approval in approvers]
                text = f"🎙️ **Broadcast Request**\n\n"
                text += f"👤 **Requester:** @{request['requester_username']}\n"
                text += f"📊 **Target:** {request['target_count']} users\n"
                text += f"📝 **Message:** {request['message_text']}\n"
                if request['media_type'] != "text":
                    text += f"📎 **Media:** {request['media_type'].upper()}\n"
                text += f"\n✅ **Approvals ({len(approvers)}/2):** {', '.join(approver_names)}\n"
                text += f"❌ **Only Super Admin can reject**"
                try:
                    await ctx.bot.edit_message_text(
                        chat_id=int(GROUP_CHAT_ID),
                        message_id=int(group_message_id),
                        text=text,
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                except Exception:
                    pass
            return
    if ctx.user_data is None:
        ctx.user_data = {}
    if not ctx.user_data.get("awaiting_broadcast_message"):
        return
    if not update.message or not update.message.from_user:
        return
    telegram_id = update.message.from_user.id
    if not is_admin(telegram_id):
        return
    request_id = str(uuid.uuid4())
    broadcast_users = get_whitelisted_users_except_admins()
    user_count = len(broadcast_users)
    text = BROADCAST_TITLE
    text += BROADCAST_TARGET_MSG.format(user_count=user_count)
    text += BROADCAST_SEND_PROMPT
    text += BROADCAST_APPROVAL_REQUIRED
    buttons = [[InlineKeyboardButton(CANCEL_BUTTON, callback_data="admin_control")]]
    ctx.user_data["awaiting_broadcast_message"] = True
    ctx.user_data["broadcast_users"] = broadcast_users
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@handle_errors
async def send_broadcast_message(ctx, request):
    """Send the approved broadcast message to all whitelisted users."""
    whitelisted_users = get_whitelisted_users_except_admins()
    success_count = 0
    failed_count = 0
    for user in whitelisted_users:
        if isinstance(user, dict) and 'telegram_id' in user:
            user_id = user['telegram_id']
        elif isinstance(user, (str, int)):
            user_id = user
        else:
            continue
        try:
            if not user_id:
                continue
            if request['media_type'] == "text":
                await ctx.bot.send_message(
                    chat_id=int(user_id),
                    text=f"📢 **Broadcast Message**\n\n{request['message_text']}\n\n_From: Admin Team_"
                )
            elif request['media_type'] == "photo":
                await ctx.bot.send_photo(
                    chat_id=int(user_id),
                    photo=request['media_file_id'],
                    caption=f"📢 **Broadcast Message**\n\n{request['message_text']}\n\n_From: Admin Team_"
                )
            elif request['media_type'] == "video":
                await ctx.bot.send_video(
                    chat_id=int(user_id),
                    video=request['media_file_id'],
                    caption=f"📢 **Broadcast Message**\n\n{request['message_text']}\n\n_From: Admin Team_"
                )
            elif request['media_type'] == "document":
                await ctx.bot.send_document(
                    chat_id=int(user_id),
                    document=request['media_file_id'],
                    caption=f"📢 **Broadcast Message**\n\n{request['message_text']}\n\n_From: Admin Team_"
                )
            elif request['media_type'] == "audio":
                await ctx.bot.send_audio(
                    chat_id=int(user_id),
                    audio=request['media_file_id'],
                    caption=f"📢 **Broadcast Message**\n\n{request['message_text']}\n\n_From: Admin Team_"
                )
            elif request['media_type'] == "voice":
                await ctx.bot.send_voice(
                    chat_id=int(user_id),
                    voice=request['media_file_id'],
                    caption=f"📢 **Broadcast Message**\n\n{request['message_text']}\n\n_From: Admin Team_"
                )
            success_count += 1
        except Exception as e:
            failed_count += 1