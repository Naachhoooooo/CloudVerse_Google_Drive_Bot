from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .config import GROUP_CHAT_ID, MessageDev_TOPIC_ID
import re
from .database import is_admin, is_whitelisted, insert_dev_message, fetch_dev_messages, mark_dev_message_delivered, fetch_dev_message_notified
import asyncio
from .config import DB_PATH
from .UserState import UserStateEnum
from .Utilities import access_required

def has_user_been_notified(user_telegram_id):
    """Check if the user has already been notified about developer message delivery."""
    return fetch_dev_message_notified(user_telegram_id)

def set_user_notified(user_telegram_id):
    """Mark the user as notified about developer message delivery."""
    # Provide all required arguments for insert_dev_message
    insert_dev_message(user_telegram_id, 'system', None, None, 'system', 'notified')

# Message constants (user-facing)
ENTER_DEV_MESSAGE = "Please enter your message for the developer."
DEV_GROUP_NOT_CONFIGURED = "Developer group is not configured."
MESSAGE_TO_DEV_CONFIRMED = "Your message has been sent to the developer."
COULD_NOT_EXTRACT_USER_ID = "Could not extract user ID from the message."
REPLY_FROM_DEVELOPER = "Reply from developer:"
REPLY_FROM_DEVELOPER_UNSUPPORTED = "Reply from developer is not supported for this message type."
UNSUPPORTED_MESSAGE_TYPE = "Unsupported message type."
PLEASE_TYPE_REPLY_TO_USER = "Please type your reply to the user."
PLEASE_TYPE_REPLY_TO_DEVELOPER = "Please type your reply to the developer."
DELIVERED_TO_USER_MSG = "✅ Delivered to user."

# Remove get_access_required and use @access_required directly
@access_required
async def handle_cloudverse_support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Prompt the user to enter a message for the developer and set state."""
    if ctx.user_data is None:
        ctx.user_data = {}
    # Get telegram_id from either message or callback_query
    if update.message and update.message.from_user:
        telegram_id = update.message.from_user.id
        is_command = True
    elif update.callback_query and update.callback_query.from_user:
        telegram_id = update.callback_query.from_user.id
        is_command = False
    else:
        return
    # Handle both command and callback query responses
    if is_command and update.message:
        await update.message.reply_text(ENTER_DEV_MESSAGE)
    elif not is_command and update.callback_query:
        await update.callback_query.edit_message_text(ENTER_DEV_MESSAGE)
    ctx.user_data["state"] = UserStateEnum.CLOUDVERSE_SUPPORT
    ctx.user_data["expecting_dev_message"] = True

async def send_to_developer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Forward the user's message to the developer group and notify the user."""
    if ctx.user_data is None:
        ctx.user_data = {}
    if ctx.user_data.get("expecting_dev_message"):
        if GROUP_CHAT_ID is None or MessageDev_TOPIC_ID is None:
            if update.message and hasattr(update.message, 'reply_text'):
                await update.message.reply_text(DEV_GROUP_NOT_CONFIGURED)
                return
            if update.callback_query and hasattr(update.callback_query, 'edit_message_text'):
                await update.callback_query.edit_message_text(DEV_GROUP_NOT_CONFIGURED)
                return
        try:
            group_chat_id = int(GROUP_CHAT_ID) if GROUP_CHAT_ID is not None else None
            topic_id = int(MessageDev_TOPIC_ID) if MessageDev_TOPIC_ID is not None else None
        except Exception:
            group_chat_id = None
            topic_id = None
        if update.message and hasattr(update.message, 'from_user') and update.message.from_user:
            user = update.message.from_user
            header = (
                f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}\n"
                f"Username: @{getattr(user, 'username', 'N/A')}\n"
                f"ID: {getattr(user, 'id', '')}\n"
            )
            text = update.message.text or ''
            full_message = header + f"\nMessage: {text}"
            print(
                f"Forwarding message to developer:\n{header}Message: {text}",
                extra={
                    "user_id": getattr(user, 'id', ''),
                    "username": getattr(user, 'username', ''),
                    "first_name": getattr(user, 'first_name', ''),
                    "last_name": getattr(user, 'last_name', '')
                }
            )
            # Insert into dev_messages with all required arguments
            msg_id = insert_dev_message(
                user.id,
                'user',
                getattr(user, 'username', None),
                f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}",
                'user',
                text,
                telegram_message_id=update.message.message_id
            )
            # Add reply button for developer
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⤷ Reply", callback_data=f"reply_to_user:{user.id}:{msg_id}")]
            ])
            if group_chat_id is not None and topic_id is not None:
                await ctx.bot.send_message(
                    chat_id=group_chat_id,
                    text=full_message,
                    message_thread_id=topic_id,
                    reply_markup=reply_markup
                )
            print(f"Forwarding message to developer:\n{header}Message: {text}")
            # Notify user only once in lifetime
            if not has_user_been_notified(user.id):
                if update.message and hasattr(update.message, 'reply_text'):
                    await update.message.reply_text(MESSAGE_TO_DEV_CONFIRMED)
                set_user_notified(user.id)
            ctx.user_data["expecting_dev_message"] = False
            from MainMenu import start
            await start(update, ctx)

# Callback handler for developer reply button
async def handle_reply_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle reply button callbacks for developer and user replies."""
    query = update.callback_query
    if not query:
        return
    if ctx.user_data is None:
        ctx.user_data = {}
    data = query.data
    if data.startswith("reply_to_user:"):
        # Developer wants to reply to user
        _, user_id, msg_id = data.split(":")
        ctx.user_data["reply_to_user_id"] = int(user_id)
        ctx.user_data["reply_to_msg_id"] = int(msg_id)
        ctx.user_data["state"] = UserStateEnum.AWAITING_DEV_REPLY
        await query.answer()
        await query.message.reply_text(PLEASE_TYPE_REPLY_TO_USER)
    elif data.startswith("reply_to_dev:"):
        # User wants to reply to developer
        _, dev_group_id, topic_id, msg_id = data.split(":")
        ctx.user_data["reply_to_dev_group_id"] = int(dev_group_id)
        ctx.user_data["reply_to_topic_id"] = int(topic_id)
        ctx.user_data["reply_to_msg_id"] = int(msg_id)
        ctx.user_data["state"] = UserStateEnum.AWAITING_USER_REPLY
        await query.answer()
        await query.message.reply_text(PLEASE_TYPE_REPLY_TO_DEVELOPER)

# Handler for developer sending reply
async def handle_developer_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle developer's reply to a user, forward it, and notify of delivery."""
    if ctx.user_data is None:
        ctx.user_data = {}
    if ctx.user_data.get("state") == UserStateEnum.AWAITING_DEV_REPLY:
        user_id = ctx.user_data.get("reply_to_user_id")
        reply_to_msg_id = ctx.user_data.get("reply_to_msg_id")
        if not user_id:
            return
        text = update.message.text or ''
        # Insert reply into dev_messages with all required arguments
        reply_msg_id = insert_dev_message(
            user_id,
            'developer',
            None,
            None,
            'developer',
            text,
            reply_to_id=reply_to_msg_id,
            telegram_message_id=update.message.message_id
        )
        # Send reply to user with reply button
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⤷ Reply", callback_data=f"reply_to_dev:{GROUP_CHAT_ID}:{MessageDev_TOPIC_ID}:{reply_msg_id}")]
        ])
        await ctx.bot.send_message(
            chat_id=user_id,
            text=f"Reply from Developer :\n{text}",
            reply_markup=reply_markup
        )
        print(f"Reply from Developer :\n{text}")
        # Notify developer of delivery, then delete after 2 seconds
        delivery_msg = await update.message.reply_text(DELIVERED_TO_USER_MSG)
        await asyncio.sleep(2)
        try:
            await delivery_msg.delete()
        except Exception:
            pass
        ctx.user_data["state"] = None
        ctx.user_data.pop("reply_to_user_id", None)
        ctx.user_data.pop("reply_to_msg_id", None)

# Handler for user sending reply to developer
async def handle_user_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle user's reply to the developer, forward it to the developer group."""
    if ctx.user_data is None:
        ctx.user_data = {}
    if ctx.user_data.get("state") == UserStateEnum.AWAITING_USER_REPLY:
        dev_group_id = ctx.user_data.get("reply_to_dev_group_id")
        topic_id = ctx.user_data.get("reply_to_topic_id")
        reply_to_msg_id = ctx.user_data.get("reply_to_msg_id")
        user = update.message.from_user
        text = update.message.text or ''
        # Insert reply into dev_messages with all required arguments
        reply_msg_id = insert_dev_message(
            user.id,
            'user',
            getattr(user, 'username', None),
            f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}",
            'user',
            text,
            reply_to_id=reply_to_msg_id,
            telegram_message_id=update.message.message_id
        )
        # Forward to developer group with reply button
        header = (
            f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}\n"
            f"Username: @{getattr(user, 'username', 'N/A')}\n"
            f"ID: {getattr(user, 'id', '')}\n"
        )
        full_message = header + f"\nMessage: {text}"
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⤷ Reply", callback_data=f"reply_to_user:{user.id}:{reply_msg_id}")]
        ])
        if dev_group_id is None or topic_id is None:
            return
        await ctx.bot.send_message(
            chat_id=dev_group_id,
            text=full_message,
            message_thread_id=topic_id,
            reply_markup=reply_markup
        )
        ctx.user_data["state"] = None
        ctx.user_data.pop("reply_to_dev_group_id", None)
        ctx.user_data.pop("reply_to_topic_id", None)
        ctx.user_data.pop("reply_to_msg_id", None)
        from MainMenu import start
        await start(update, ctx)

# --- Existing fallback for old reply system (for compatibility) ---
async def handle_developer_reply_legacy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not hasattr(update, 'message') or update.message is None:
        return
    if not update.message.reply_to_message:
        return  # Not a reply
    replied_text = update.message.reply_to_message.text or update.message.reply_to_message.caption or ""
    match = re.search(r"ID:\s*(\d+)", replied_text)
    if not match:
        print(f"Could not extract user ID from replied message: {replied_text}")
        print(f"Could not extract user ID from replied message: {replied_text}", context="handle_developer_reply")
        await update.message.reply_text("Could not extract user ID from the message.")
        return
    user_id = int(match.group(1))
    if update.message.text:
        reply_content = f"Reply from Developer :\n{update.message.text}"
        await ctx.bot.send_message(chat_id=user_id, text=reply_content)
        print(f"Reply from Developer :\n{update.message.text}")
        username_match = re.search(r"Username: @([\w_]+)", replied_text)
        username = username_match.group(1) if username_match else 'N/A'
        print(f"Forwarding developer reply to Username : @{username} ID : {user_id} message : {update.message.text}")
    elif update.message.caption or update.message.document or update.message.photo or update.message.video or update.message.audio or update.message.voice:
        media_caption = update.message.caption if hasattr(update.message, 'caption') and update.message.caption else "[Media reply]"
        reply_content = f"Reply from Developer :\n{media_caption}"
        await ctx.bot.send_message(chat_id=user_id, text=REPLY_FROM_DEVELOPER.format(reply=reply_content))
        print(f"Forwarding developer media reply to user {user_id}")
    else:
        await ctx.bot.send_message(chat_id=user_id, text=REPLY_FROM_DEVELOPER_UNSUPPORTED)
        print(f"Developer reply to user {user_id} was unsupported type.")