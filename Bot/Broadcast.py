from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .database import (
    is_admin, is_super_admin, create_broadcast_request, get_broadcast_request, update_broadcast_status, store_broadcast_group_message, get_broadcast_group_message,
    update_broadcast_approvers
)
from .config import TeamCloudverse_TOPIC_ID, GROUP_CHAT_ID
import uuid
from datetime import datetime
from .TeamCloudverse import handle_broadcast_request
from .Logger import get_logger
logger = get_logger()

def get_whitelisted_users_except_admins():
    try:
        return [] # Removed get_whitelisted_users_except_admins_db()
    except Exception as e:
        from .Logger import get_logger
        logger = get_logger()
        logger.error(f"Error in get_whitelisted_users_except_admins: {e}")
        return []

async def handle_broadcast_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is None:
        ctx.user_data = {}
    q = update.callback_query
    if not q or not q.from_user:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.edit_message_text("You don't have permission to access Admin Controls.")
        return
    whitelisted_users = get_whitelisted_users_except_admins()
    user_count = len(whitelisted_users)
    text = f"🎙️ Broadcast Message\n\n"
    text += f"📊 This message will be sent to {user_count} users (whitelisted users excluding admins).\n\n"
    text += f"📝 Please send your broadcast message (text, photo, video, document, or audio).\n"
    text += f"⚠️ This action requires approval before sending."
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_control")]]
    ctx.user_data["awaiting_broadcast_message"] = True
    ctx.user_data["broadcast_users"] = whitelisted_users
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_broadcast_media_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("❌ Unsupported media type. Please send text, photo, video, document, or audio.")
        return
    success = create_broadcast_request(request_id, telegram_id, message_text, media_type, media_file_id, user_count)
    if not success:
        await update.message.reply_text("Failed to create broadcast request.")
        return
    if is_super_admin(telegram_id):
        await handle_super_admin_broadcast_approval(update, ctx, request_id, message_text, media_type, media_file_id, user_count)
    else:
        await handle_regular_admin_broadcast_approval(update, ctx, request_id, message_text, media_type, media_file_id, user_count)
    ctx.user_data.pop("awaiting_broadcast_message", None)
    ctx.user_data.pop("broadcast_users", None)

async def handle_super_admin_broadcast_approval(update: Update, ctx: ContextTypes.DEFAULT_TYPE, request_id, message_text, media_type, media_file_id, user_count):
    text = f"👑 **Super Admin Broadcast Approval**\n\n"
    text += f"📊 Target: {user_count} users\n"
    text += f"📝 Message: {message_text[:100]}{'...' if len(message_text) > 100 else ''}\n"
    if media_type != "text":
        text += f"📎 Media: {media_type.upper()}\n"
    text += f"\n⚠️ As Super Admin, you can approve this broadcast directly."
    buttons = [
        [InlineKeyboardButton("✅ Approve & Send", callback_data=f"super_approve_broadcast:{request_id}" )],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_control")]
    ]
    if update.message and hasattr(update.message, 'reply_text'):
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_regular_admin_broadcast_approval(update: Update, ctx: ContextTypes.DEFAULT_TYPE, request_id, message_text, media_type, media_file_id, user_count):
    if not GROUP_CHAT_ID or not TeamCloudverse_TOPIC_ID:
        if update.message and hasattr(update.message, 'reply_text'):
            await update.message.reply_text("❌ Group chat or topic not configured for broadcast approval.")
        return
    requester_username = "Unknown"
    if update.message and update.message.from_user and hasattr(update.message.from_user, 'username'):
        requester_username = update.message.from_user.username or "Unknown"
    try:
        await handle_broadcast_request(ctx, 'request', {
            'request_id': request_id,
            'message': message_text,
            'media_type': media_type,
            'media_file_id': media_file_id,
            'user_count': user_count,
            'admin_username': requester_username
        })
        if update.message and hasattr(update.message, 'reply_text'):
            await update.message.reply_text("Broadcast sent to group.")
    except Exception as e:
        logger.error(f"Failed to send broadcast request to group: {e}")
        if update.message and hasattr(update.message, 'reply_text'):
            await update.message.reply_text("Failed to send broadcast.")

async def handle_broadcast_approval(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.from_user or not q.data:
        return
    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.answer("You don't have permission to approve broadcasts.")
        return
    data = q.data
    if data.startswith("super_approve_broadcast:"):
        request_id = data.split(":")[1]
        await handle_super_admin_approval_execution(update, ctx, request_id)
    elif data.startswith("approve_broadcast:"):
        request_id = data.split(":")[1]
        await handle_regular_admin_approval(update, ctx, request_id)
    elif data.startswith("reject_broadcast:"):
        if not is_super_admin(telegram_id):
            await q.answer("❌ Only Super Admin can reject broadcasts.")
            return
        request_id = data.split(":")[1]
        await handle_broadcast_rejection(update, ctx, request_id)

async def handle_super_admin_approval_execution(update: Update, ctx: ContextTypes.DEFAULT_TYPE, request_id):
    q = update.callback_query
    if not q:
        return
    request = get_broadcast_request(request_id)
    if not request:
        await q.edit_message_text("❌ Broadcast request not found.")
        return
    approver_username = "Super Admin"
    if q.from_user and hasattr(q.from_user, 'username'):
        approver_username = q.from_user.username or "Super Admin"
    # Removed add_broadcast_approval(request_id, q.from_user.id, approver_username)
    update_broadcast_status(request_id, "approved")
    await send_broadcast_message(ctx, request)
    text = f"✅ **Broadcast Approved by Super Admin**\n\n"
    text += f"👑 Approved by: @{approver_username}\n"
    text += f"📊 Target: {request['target_count']} users\n"
    text += f"📝 Message: {request['message_text'][:100]}{'...' if len(request['message_text']) > 100 else ''}\n"
    text += f"\n✅ **Broadcast sent successfully!**"
    await q.edit_message_text(text)

    # Forward the broadcast to AdminControls group chat thread with a single button
    from .config import GROUP_CHAT_ID, TeamCloudverse_TOPIC_ID
    if GROUP_CHAT_ID is not None and TeamCloudverse_TOPIC_ID is not None:
        forward_text = f"📢 **Broadcast by Super Admin**\n\n"
        forward_text += f"📝 Message: {request['message_text']}\n"
        forward_text += f"📊 Target: {request['target_count']} users\n"
        forward_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Broadcasted by Super Admin", callback_data="noop")]
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
        except Exception as e:
            logger.error(f"Failed to forward super admin broadcast to group: {e}")

async def handle_regular_admin_approval(update: Update, ctx: ContextTypes.DEFAULT_TYPE, request_id):
    q = update.callback_query
    if not q or not q.from_user:
        return
    approver_id = str(q.from_user.id)
    approver_username = q.from_user.username or "Unknown"
    request = get_broadcast_request(request_id)
    if not request:
        await q.edit_message_text("❌ Broadcast request not found.")
        return
    # Add approver if not already present
    approvers = request.get('approvers', [])
    if not any(a['id'] == approver_id for a in approvers):
        approvers.append({'id': approver_id, 'username': approver_username})
        update_broadcast_approvers(request_id, approvers)
    # Only send if at least 2 unique approvers
    if len(approvers) >= 2:
        update_broadcast_status(request_id, "approved")
        await send_broadcast_message(ctx, request)
        await update_group_message_approved(update, ctx, request_id, request)
    else:
        await update_group_message_approval_count(update, ctx, request_id, approvers)

async def handle_broadcast_rejection(update: Update, ctx: ContextTypes.DEFAULT_TYPE, request_id):
    q = update.callback_query
    if not q:
        return
    if not is_super_admin(q.from_user.id):
        await q.answer("❌ Only Super Admin can reject broadcasts.")
        return
    update_broadcast_status(request_id, "rejected")
    rejector_username = "Unknown"
    if q.from_user and hasattr(q.from_user, 'username'):
        rejector_username = q.from_user.username or "Unknown"
    text = f"❌ **Broadcast Rejected by Super Admin**\n\n"
    text += f"👑 **Rejected by:** @{rejector_username} (Super Admin)\n"
    text += f"⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    text += f"🔒 **Reason:** Super Admin decision"
    await q.edit_message_text(text)

async def send_broadcast_message(ctx, request):
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
            logger.error(f"Failed to send broadcast to user {user_id}: {e}")
            failed_count += 1
    logger.info(f"Broadcast completed: {success_count} successful, {failed_count} failed")

async def update_group_message_approval_count(update: Update, ctx: ContextTypes.DEFAULT_TYPE, request_id, approvals):
    request = get_broadcast_request(request_id)
    if not request:
        return
    group_message_id = get_broadcast_group_message(request_id)
    if not group_message_id:
        return
    if not GROUP_CHAT_ID:
        logger.error("GROUP_CHAT_ID not configured")
        return
    approver_names = [f"@{approval['username']}" for approval in approvals]
    text = f"🎙️ **Broadcast Request**\n\n"
    text += f"👤 **Requester:** @{request['requester_id']}\n"
    text += f"📊 **Target:** {request['target_count']} users\n"
    text += f"📝 **Message:** {request['message_text']}\n"
    if request['media_type'] != "text":
        text += f"📎 **Media:** {request['media_type'].upper()}\n"
    text += f"\n✅ **Approvals ({len(approvals)}/2):** {', '.join(approver_names)}\n"
    text += f"❌ **Only Super Admin can reject**"
    buttons = [
        [
            InlineKeyboardButton("🟢 Approve", callback_data=f"approve_broadcast:{request_id}"),
            InlineKeyboardButton("🔴 Reject (Super Admin Only)", callback_data=f"reject_broadcast:{request_id}")
        ]
    ]
    try:
        await ctx.bot.edit_message_text(
            chat_id=int(GROUP_CHAT_ID),
            message_id=int(group_message_id),
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.error(f"Failed to update group message: {e}")

async def update_group_message_approved(update: Update, ctx: ContextTypes.DEFAULT_TYPE, request_id, request):
    group_message_id = get_broadcast_group_message(request_id)
    if not group_message_id:
        return
    if not GROUP_CHAT_ID:
        logger.error("GROUP_CHAT_ID not configured")
        return
    approvals = request.get('approvers', [])
    approver_names = [f"@{approval['username']}" for approval in approvals]
    text = f"✅ **Broadcast Approved**\n\n"
    text += f"👤 **Requester:** @{request['requester_id']}\n"
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
    except Exception as e:
        logger.error(f"Failed to update approved group message: {e}") 