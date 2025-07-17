import os
import tempfile
import asyncio
import aiohttp
import requests
from datetime import datetime
from googleapiclient.http import MediaFileUpload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from .Utilities import format_size, is_url
from .Logger import log_upload, log_bandwidth, log_error, get_logger
from .drive import get_drive_service, get_storage_info
from mimetypes import guess_extension
from telegram.ext import ContextTypes
import json
import websockets
import math
from telethon import TelegramClient
from telethon.tl.types import InputDocument
from .config import TELETHON_API_ID, TELETHON_API_HASH
from .database import insert_upload, get_upload_by_file_id
import subprocess
import shlex

logger = get_logger()

class ProgressWebSocketClient:
    def __init__(self, url):
        self.url = url
        self.ws = None
        self.lock = asyncio.Lock()
        self.connected = False
        self.connecting = False

    async def connect(self):
        if self.connected or self.connecting:
            return
        self.connecting = True
        try:
            self.ws = await websockets.connect(self.url)
            self.connected = True
        except Exception:
            self.ws = None
            self.connected = False
        finally:
            self.connecting = False

    async def send(self, data):
        async with self.lock:
            if not self.connected:
                await self.connect()
            if self.ws and self.connected:
                try:
                    await self.ws.send(json.dumps(data))
                except Exception:
                    self.connected = False
                    self.ws = None

progress_ws_client = ProgressWebSocketClient('ws://localhost:8770')

async def send_progress_update(progress_data):
    await progress_ws_client.send({
        'type': 'upload_progress',
        'upload': progress_data
    })

async def download_file_telethon(telegram_id, file_id, file_size, file_name, update=None):
    if TELETHON_API_ID is None or TELETHON_API_HASH is None:
        raise ValueError("TELETHON_API_ID and TELETHON_API_HASH must be set in the environment.")
    session_name = f"telethon_{telegram_id}"
    client = TelegramClient(session_name, int(TELETHON_API_ID), str(TELETHON_API_HASH))
    await client.start()
    # Fetch upload metadata
    upload = get_upload_by_file_id(file_id)
    if not upload or not upload['message_id'] or not upload['chat_id']:
        if update:
            await update.message.reply_text('❌ Could not find message_id or chat_id for this file. Large file download not possible.')
        await client.disconnect()
        return None
    message_id = upload['message_id']
    chat_id = upload['chat_id']
    import tempfile
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file_path = temp_file.name
    temp_file.close()
    try:
        msg = await client.get_messages(chat_id, ids=message_id)
        if isinstance(msg, list):
            msg = msg[0] if msg else None
        if not msg:
            if update:
                await update.message.reply_text('❌ Could not find the original message for this file. Large file download not possible.')
            await client.disconnect()
            return None
        last_percent = -1
        def progress_callback(current, total):
            percent = int((current / total) * 100) if total else 0
            nonlocal last_percent
            if percent != last_percent and update:
                bar = ''.join('🟢' if i < percent / 10 else '🟡' for i in range(10))
                import asyncio
                asyncio.create_task(update.message.reply_text(f"Downloading large file with Telethon...\nProgress: {percent}% [{bar}]\n{format_size(current)} of {format_size(total)}"))
                last_percent = percent
        await client.download_media(msg, file=temp_file_path, progress_callback=progress_callback)
    except Exception as e:
        if update:
            await update.message.reply_text(f'❌ Telethon download failed: {e}')
        await client.disconnect()
        return None
    await client.disconnect()
    return temp_file_path

def get_adaptive_chunk_size(last_chunk_time, current_chunk_size, logger=None, context=None):
    min_chunk = 64 * 1024      # 64KB
    max_chunk = 8 * 1024 * 1024 # 8MB
    reason = 'unchanged'
    new_chunk = current_chunk_size
    if last_chunk_time < 0.5:
        new_chunk = min(current_chunk_size * 2, max_chunk)
        reason = 'fast'
    elif last_chunk_time > 2.0:
        new_chunk = max(current_chunk_size // 2, min_chunk)
        reason = 'slow'
    if logger is not None and new_chunk != current_chunk_size:
        logger.info(f"[ChunkSize] {context or ''} Chunk size changed from {current_chunk_size} to {new_chunk} due to {reason} chunk (time: {last_chunk_time:.2f}s)")
    return new_chunk

async def handle_file_upload(update, ctx):
    """Handle file upload from user, including error handling and logging."""
    telegram_id = None
    preparing_message = None
    temp_file_path = None
    file_mime_type = None
    file_name_to_use = None
    try:
        if update.message and update.message.from_user:
            telegram_id = update.message.from_user.id
        elif update.callback_query and update.callback_query.from_user:
            telegram_id = update.callback_query.from_user.id
        else:
            logger.warning("handle_file_upload called without user context")
            return
        if update.message and update.message.document:
            file = update.message.document
            file_size_bytes = getattr(file, 'file_size', None)
            message_id = update.message.message_id
            chat_id = update.message.chat_id
        else:
            file_size_bytes = None
            message_id = None
            chat_id = None
        file_size_gb = file_size_bytes / (1024 ** 3) if file_size_bytes else 0
        if ctx.user_data is None:
            ctx.user_data = {}
        if ctx.user_data.get("state") == "FILE_MANAGER" and ctx.user_data.get("current_account"):
            current_account = ctx.user_data["current_account"]
            account_data = ctx.user_data.get("account_data")
            if account_data is None:
                account_data = {}
            account_data = account_data.get(current_account)
            if account_data is None:
                account_data = {}
            parent_id = account_data.get("current_folder", "root")
        else:
            parent_id = "root"
            current_account = "default_account"
        service = get_drive_service(telegram_id, current_account)
        storage = get_storage_info(service)
        limit = int(storage["storageQuota"]["limit"]) if storage and "storageQuota" in storage and "limit" in storage["storageQuota"] else 0
        usage = int(storage["storageQuota"].get("usage", 0)) if storage and "storageQuota" in storage else 0
        free_space = (limit - usage) / (1024 ** 3) if limit > 0 else 0
        if limit > 0:
            percent_free = (free_space / (limit / (1024 ** 3))) * 100
            if percent_free < 10:
                await update.message.reply_text(warning_low_space(free_space, percent_free))
        if file_size_gb > free_space:
            preparing_message = await update.message.reply_text(PREPARING_UPLOAD)
            await preparing_message.edit_text(insufficient_storage(free_space, format_size(file_size_bytes)))
            return
        folder_name = None
        try:
            from .drive import get_folder_name
            service_for_name = get_drive_service(telegram_id, current_account)
            folder_name = get_folder_name(service_for_name, parent_id)
        except Exception:
            folder_name = None
        if folder_name:
            upload_location_str = UPLOADING_TO_FOLDER(folder_name)
            await update.message.reply_text(upload_location_str)
        else:
            upload_location_str = UPLOADING_TO_DEFAULT_LOCATION
            await update.message.reply_text(upload_location_str)
        try:
            if update.message and update.message.document and hasattr(update.message.document, 'file_id'):
                file_obj = await ctx.bot.get_file(update.message.document.file_id)
            else:
                file_obj = None
            if file_obj and hasattr(file_obj, 'file_path') and file_obj.file_path:
                notify_btn_text = '🔕 Don\'t notify completion' if ctx.user_data.get('notify_completion', True) else '🛎️ Notify completion'
                progress_markup = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(notify_btn_text, callback_data='toggle_notify_completion'),
                        InlineKeyboardButton('❎ Cancel', callback_data='cancel_upload')
                    ]
                ])
                preparing_message = await update.message.reply_text(PREPARING_UPLOAD)
                await preparing_message.edit_text(
                    f"Downloading from Telegram...\n{upload_location_str}\nProgress: 0% [🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡]\n0.00 KB of {format_size(file_size_bytes)}\nSpeed: 0.00 MB/sec\nETA: Calculating...\nThank you for using @CloudVerse_GoogleDriveBot",
                    reply_markup=progress_markup
                )
                message = preparing_message
                sem = ctx.user_data.get("upload_semaphore", asyncio.Semaphore(1))
                ctx.user_data["upload_semaphore"] = sem
                ctx.user_data["cancel_upload"] = False
                async with sem:
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file_path = temp_file.name
                        downloaded_bytes = 0
                        start_time = asyncio.get_event_loop().time()
                        last_update = start_time
                        # Chunk size stats
                        chunk_size_stats = {
                            'changes': 0,
                            'total_bytes': 0,
                            'total_time': 0.0,
                            'sum_chunk_size': 0,
                            'num_chunks': 0,
                            'last_chunk_size': 1024 * 1024,
                        }
                        async with aiohttp.ClientSession() as session:
                            async with session.get(file_obj.file_path) as resp:
                                while True:
                                    chunk_size = chunk_size_stats['last_chunk_size']
                                    start_chunk = asyncio.get_event_loop().time()
                                    chunk = await resp.content.read(chunk_size)
                                    end_chunk = asyncio.get_event_loop().time()
                                    elapsed = end_chunk - start_chunk
                                    new_chunk_size = get_adaptive_chunk_size(elapsed, chunk_size, logger=logger, context="download")
                                    if new_chunk_size != chunk_size:
                                        chunk_size_stats['changes'] += 1
                                    chunk_size_stats['last_chunk_size'] = new_chunk_size
                                    chunk_size_stats['total_bytes'] += len(chunk) if chunk else 0
                                    chunk_size_stats['total_time'] += elapsed
                                    chunk_size_stats['sum_chunk_size'] += chunk_size
                                    chunk_size_stats['num_chunks'] += 1
                                    if not chunk or ctx.user_data.get("cancel_upload"):
                                        if ctx.user_data.get("cancel_upload"):
                                            await message.edit_text(CANCELLING_UPLOAD)
                                        os.remove(temp_file_path)
                                        return
                                    temp_file.write(chunk)
                                    downloaded_bytes += len(chunk)
                                    current_time = asyncio.get_event_loop().time()
                                    if current_time - last_update >= 2:
                                        if file_size_bytes is not None:
                                            percent = (downloaded_bytes / file_size_bytes) * 100 if file_size_bytes else 0
                                            speed = downloaded_bytes / (current_time - start_time) / 1024 / 1024 if current_time - start_time > 0 else 0
                                            eta = (file_size_bytes - downloaded_bytes) / (speed * 1024 * 1024) if speed > 0 else 0
                                        else:
                                            percent = 0
                                            eta = 0
                                        bar = ''.join('🟢' if i < percent / 10 else '🟡' for i in range(10))
                                        await message.edit_text(
                                            f"Downloading from Telegram...\n{upload_location_str}\nProgress: {percent:.0f}% [{bar}]\n{format_size(downloaded_bytes)} of {format_size(file_size_bytes)}\nSpeed: {speed:.2f} MB/sec\nETA: {eta:.0f} seconds\nThank you for using @CloudVerse_GoogleDriveBot",
                                            reply_markup=progress_markup
                                        )
                                        last_update = current_time
                        # Log chunk size stats for download
                        if chunk_size_stats['num_chunks'] > 0:
                            avg_chunk = chunk_size_stats['sum_chunk_size'] // chunk_size_stats['num_chunks']
                        else:
                            avg_chunk = 0
                        logger.info(f"[ChunkStats][Download] Chunks: {chunk_size_stats['num_chunks']}, Changes: {chunk_size_stats['changes']}, Total bytes: {chunk_size_stats['total_bytes']}, Total time: {chunk_size_stats['total_time']:.2f}s, Avg chunk size: {avg_chunk}")
                await message.edit_text(f"Finalizing download. Uploading to Google Drive...\n{upload_location_str}", reply_markup=progress_markup)
                with open(temp_file_path, "rb") as f:
                    file_name_to_use = getattr(file, 'file_name', None) or getattr(file, 'file_name', None) or 'UploadedFile'
                    file_mime_type = getattr(file, 'mime_type', None)
                    media = MediaFileUpload(temp_file_path, mimetype=file_mime_type, resumable=True)
                    request = service.files().create(body={"name": file_name_to_use, "parents": [parent_id]}, media_body=media)
                    response = None
                    start_time = asyncio.get_event_loop().time()
                    last_update = start_time
                    chunk_size = 1024 * 1024 # Initial chunk size
                    # Chunk size stats for upload
                    upload_chunk_stats = {
                        'changes': 0,
                        'total_bytes': 0,
                        'total_time': 0.0,
                        'sum_chunk_size': 0,
                        'num_chunks': 0,
                        'last_chunk_size': chunk_size,
                    }
                    while response is None:
                        if ctx.user_data.get("cancel_upload"):
                            await message.edit_text(CANCELLING_UPLOAD)
                            os.remove(temp_file_path)
                            return
                        start_chunk = asyncio.get_event_loop().time()
                        status, response = request.next_chunk()
                        end_chunk = asyncio.get_event_loop().time()
                        elapsed = end_chunk - start_chunk
                        new_chunk_size = get_adaptive_chunk_size(elapsed, chunk_size, logger=logger, context="upload")
                        if new_chunk_size != chunk_size:
                            upload_chunk_stats['changes'] += 1
                        upload_chunk_stats['last_chunk_size'] = new_chunk_size
                        upload_chunk_stats['total_time'] += elapsed
                        if status:
                            upload_chunk_stats['total_bytes'] = status.resumable_progress
                        upload_chunk_stats['sum_chunk_size'] += chunk_size
                        upload_chunk_stats['num_chunks'] += 1
                        chunk_size = new_chunk_size
                        request.media_body._chunksize = chunk_size
                        if status:
                            current_time = asyncio.get_event_loop().time()
                            if current_time - last_update >= 2:
                                if file_size_bytes is not None:
                                    percent = (status.resumable_progress / file_size_bytes) * 100 if file_size_bytes else 0
                                    speed = status.resumable_progress / (current_time - start_time) / 1024 / 1024 if current_time - start_time > 0 else 0
                                    eta = (file_size_bytes - status.resumable_progress) / (speed * 1024 * 1024) if speed > 0 else 0
                                else:
                                    percent = 0
                                    eta = 0
                                bar = ''.join('🟢' if i < percent / 10 else '🟡' for i in range(10))
                                await message.edit_text(
                                    f"Uploading to Google Drive...\n{upload_location_str}\nProgress: {percent:.0f}% [{bar}]\n{format_size(status.resumable_progress)} of {format_size(file_size_bytes)}\nSpeed: {speed:.2f} MB/sec\nETA: {eta:.0f} seconds\nThank you for using @CloudVerse_GoogleDriveBot",
                                    reply_markup=progress_markup
                                )
                                last_update = current_time
                    # Log chunk size stats for upload
                    if upload_chunk_stats['num_chunks'] > 0:
                        avg_chunk = upload_chunk_stats['sum_chunk_size'] // upload_chunk_stats['num_chunks']
                    else:
                        avg_chunk = 0
                    logger.info(f"[ChunkStats][Upload] Chunks: {upload_chunk_stats['num_chunks']}, Changes: {upload_chunk_stats['changes']}, Total bytes: {upload_chunk_stats['total_bytes']}, Total time: {upload_chunk_stats['total_time']:.2f}s, Avg chunk size: {avg_chunk}")
                    uploaded_file = response
                    await message.edit_text(f"Upload complete! {uploaded_file['name']} is now in your Google Drive.\n{upload_location_str}")
                    if ctx.user_data.get('notify_completion', True):
                        await update.message.reply_text(upload_success(uploaded_file['name'], folder_name or 'your Google Drive'))
                    os.remove(temp_file_path)
                    file_type = file_mime_type or (os.path.splitext(file_name_to_use)[1][1:] if file_name_to_use else None)
                    log_upload(telegram_id, uploaded_file['name'], file_size_bytes, file_size_gb)
                    log_bandwidth(telegram_id, file_size_gb, context="file_upload")
                    logger.info(f"User {telegram_id} uploaded file '{uploaded_file['name']}' successfully. Size: {file_size_bytes} bytes.")
                    # After successful upload, log upload with message_id and chat_id
                    insert_upload(telegram_id, getattr(file, 'file_id', None), getattr(file, 'file_name', None), file_size_bytes, getattr(file, 'mime_type', None), message_id, chat_id, status='success', error_message=None)
        except Exception as e:
            log_error(e, context=f"handle_file_upload user_id={telegram_id}")
            if preparing_message:
                await preparing_message.edit_text(ERROR(str(e)))
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            log_error(e, context="file_upload_inner")
    except Exception as e:
        if preparing_message:
            await preparing_message.edit_text(ERROR(str(e)))
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        log_error(e, context="file_upload")
        logger.error(f"Error in handle_file_upload for user: {telegram_id}: {e}", extra={"user_id": telegram_id, "operation": "handle_file_upload"})

def is_streaming_site(url):
    # Basic check for common streaming sites; can be expanded
    streaming_sites = [
        'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com', 'facebook.com', 'twitter.com', 'tiktok.com',
        'soundcloud.com', 'bilibili.com', 'twitch.tv', 'instagram.com', 'reddit.com', 'rumble.com', 'odysee.com'
    ]
    return any(site in url for site in streaming_sites)

def download_with_ytdlp(url, temp_dir=None):
    import tempfile
    if temp_dir is None:
        temp_dir = tempfile.gettempdir()
    # Download best quality video+audio, prefer mp4/mkv
    cmd = f"yt-dlp -f bestvideo+bestaudio/best --merge-output-format mp4 --no-playlist --no-warnings --restrict-filenames -o '{temp_dir}/%(title)s.%(ext)s' {shlex.quote(url)}"
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if proc.returncode != 0:
        raise Exception(f"yt-dlp failed: {proc.stderr}")
    # Find the downloaded file
    import glob
    files = glob.glob(f"{temp_dir}/*")
    if not files:
        raise Exception("yt-dlp did not produce any output file.")
    # Return the most recently modified file
    return max(files, key=os.path.getmtime)

async def handle_url_upload(update, ctx):
    """Handle file upload from URL, including error handling and logging."""
    url = update.message.text if update.message and update.message.text else None
    if not url:
        return
    if update.message and update.message.from_user:
        telegram_id = update.message.from_user.id
    else:
        return
    if ctx.user_data is None:
        ctx.user_data = {}
    if ctx.user_data.get("state") == "FILE_MANAGER" and ctx.user_data.get("current_account"):
        current_account = ctx.user_data["current_account"]
        account_data = ctx.user_data.get("account_data")
        if account_data is None:
            account_data = {}
        account_data = account_data.get(current_account)
        if account_data is None:
            account_data = {}
        parent_id = account_data.get("current_folder", "root")
    else:
        parent_id = "root"
        current_account = "default_account"
    service = get_drive_service(telegram_id, current_account)
    file_size_bytes = None
    temp_file_path = None
    file_name_to_use = None
    try:
        if is_streaming_site(url):
            preparing_message = await update.message.reply_text("Downloading high-quality media with yt-dlp...")
            loop = asyncio.get_event_loop()
            temp_file_path = await loop.run_in_executor(None, download_with_ytdlp, url)
            file_name_to_use = os.path.basename(temp_file_path)
        else:
            preparing_message = await update.message.reply_text(PREPARING_URL_UPLOAD)
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file_path = temp_file.name
                downloaded_bytes = 0
                start_time = asyncio.get_event_loop().time()
                last_update = start_time
                # Chunk size stats
                chunk_size_stats = {
                    'changes': 0,
                    'total_bytes': 0,
                    'total_time': 0.0,
                    'sum_chunk_size': 0,
                    'num_chunks': 0,
                    'last_chunk_size': 1024 * 1024,
                }
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        while True:
                            chunk_size = chunk_size_stats['last_chunk_size']
                            start_chunk = asyncio.get_event_loop().time()
                            chunk = await resp.content.read(chunk_size)
                            end_chunk = asyncio.get_event_loop().time()
                            elapsed = end_chunk - start_chunk
                            new_chunk_size = get_adaptive_chunk_size(elapsed, chunk_size, logger=logger, context="download")
                            if new_chunk_size != chunk_size:
                                chunk_size_stats['changes'] += 1
                            chunk_size_stats['last_chunk_size'] = new_chunk_size
                            chunk_size_stats['total_bytes'] += len(chunk) if chunk else 0
                            chunk_size_stats['total_time'] += elapsed
                            chunk_size_stats['sum_chunk_size'] += chunk_size
                            chunk_size_stats['num_chunks'] += 1
                            if not chunk or ctx.user_data.get("cancel_upload"):
                                if ctx.user_data.get("cancel_upload"):
                                    await preparing_message.edit_text(CANCELLING_UPLOAD)
                                os.remove(temp_file_path)
                                return
                            temp_file.write(chunk)
                            downloaded_bytes += len(chunk)
                            current_time = asyncio.get_event_loop().time()
                            if current_time - last_update >= 2:
                                if file_size_bytes is not None:
                                    percent = (downloaded_bytes / file_size_bytes) * 100 if file_size_bytes else 0
                                    speed = downloaded_bytes / (current_time - start_time) / 1024 / 1024 if current_time - start_time > 0 else 0
                                    eta = (file_size_bytes - downloaded_bytes) / (speed * 1024 * 1024) if speed > 0 and file_size_bytes else 0
                                else:
                                    percent = 0
                                    eta = 0
                                bar = ''.join('🟢' if i < percent / 10 else '🟡' for i in range(10))
                                await preparing_message.edit_text(
                                    f"Downloading from URL...\nProgress: {percent:.0f}% [{bar}]\n{format_size(downloaded_bytes)} of {(format_size(file_size_bytes) if file_size_bytes else 'Unknown')}\nSpeed: {speed:.2f} MB/sec\nETA: {eta:.0f} seconds\nThank you for using @CloudVerse_GoogleDriveBot"
                                )
                                last_update = current_time
                # Log chunk size stats for download
                if chunk_size_stats['num_chunks'] > 0:
                    avg_chunk = chunk_size_stats['sum_chunk_size'] // chunk_size_stats['num_chunks']
                else:
                    avg_chunk = 0
                logger.info(f"[ChunkStats][Download] Chunks: {chunk_size_stats['num_chunks']}, Changes: {chunk_size_stats['changes']}, Total bytes: {chunk_size_stats['total_bytes']}, Total time: {chunk_size_stats['total_time']:.2f}s, Avg chunk size: {avg_chunk}")
            file_name_to_use = os.path.basename(url)
    except Exception as e:
        await update.message.reply_text(f"❌ Download failed: {e}")
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        return
    if not temp_file_path or not os.path.exists(temp_file_path):
        await update.message.reply_text("❌ Download failed or file not found.")
        return
    # Upload to Google Drive
    try:
        media = MediaFileUpload(temp_file_path, mimetype="application/octet-stream", resumable=True)
        request = service.files().create(body={"name": file_name_to_use, "parents": [parent_id]}, media_body=media)
        response = None
        start_time = asyncio.get_event_loop().time()
        last_update = start_time
        file_size_bytes = os.path.getsize(temp_file_path)
        chunk_size = 1024 * 1024 # Initial chunk size
        # Chunk size stats for upload
        upload_chunk_stats = {
            'changes': 0,
            'total_bytes': 0,
            'total_time': 0.0,
            'sum_chunk_size': 0,
            'num_chunks': 0,
            'last_chunk_size': chunk_size,
        }
        while response is None:
            start_chunk = asyncio.get_event_loop().time()
            status, response = request.next_chunk()
            end_chunk = asyncio.get_event_loop().time()
            elapsed = end_chunk - start_chunk
            new_chunk_size = get_adaptive_chunk_size(elapsed, chunk_size, logger=logger, context="upload")
            if new_chunk_size != chunk_size:
                upload_chunk_stats['changes'] += 1
            upload_chunk_stats['last_chunk_size'] = new_chunk_size
            upload_chunk_stats['total_time'] += elapsed
            if status:
                upload_chunk_stats['total_bytes'] = status.resumable_progress
            upload_chunk_stats['sum_chunk_size'] += chunk_size
            upload_chunk_stats['num_chunks'] += 1
            chunk_size = new_chunk_size
            request.media_body._chunksize = chunk_size
            if status:
                current_time = asyncio.get_event_loop().time()
                if current_time - last_update >= 2:
                    percent = (status.resumable_progress / file_size_bytes) * 100 if file_size_bytes else 0
                    speed = status.resumable_progress / (current_time - start_time) / 1024 / 1024 if current_time - start_time > 0 else 0
                    eta = (file_size_bytes - status.resumable_progress) / (speed * 1024 * 1024) if speed > 0 and file_size_bytes else 0
                    bar = ''.join('🟢' if i < percent / 10 else '🟡' for i in range(10))
                    await preparing_message.edit_text(
                        f"Uploading to Google Drive...\nProgress: {percent:.0f}% [{bar}]\n{format_size(status.resumable_progress)} of {format_size(file_size_bytes)}\nSpeed: {speed:.2f} MB/sec\nETA: {eta:.0f} seconds\nThank you for using @CloudVerse_GoogleDriveBot"
                    )
                    last_update = current_time
        # Log chunk size stats for upload
        if upload_chunk_stats['num_chunks'] > 0:
            avg_chunk = upload_chunk_stats['sum_chunk_size'] // upload_chunk_stats['num_chunks']
        else:
            avg_chunk = 0
        logger.info(f"[ChunkStats][Upload] Chunks: {upload_chunk_stats['num_chunks']}, Changes: {upload_chunk_stats['changes']}, Total bytes: {upload_chunk_stats['total_bytes']}, Total time: {upload_chunk_stats['total_time']:.2f}s, Avg chunk size: {avg_chunk}")
        uploaded_file = response
        await preparing_message.edit_text(f"Upload complete! {uploaded_file['name']} is now in your Google Drive.")
        await update.message.reply_text(upload_success(uploaded_file['name'], 'your Google Drive'))
    except Exception as e:
        await update.message.reply_text(f"❌ Upload to Google Drive failed: {e}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
    # --- Pass file type, status, and action_type to bandwidth usage ---
    file_type = os.path.splitext(file_name_to_use)[1][1:] if file_name_to_use else None
    file_size_gb = file_size_bytes / (1024 ** 3) if file_size_bytes else 0
    if 'uploaded_file' in locals() and uploaded_file:
        log_upload(telegram_id, uploaded_file['name'], file_size_bytes, file_size_gb)
        log_bandwidth(telegram_id, file_size_gb, context="url_upload")
        logger.info(f"User {telegram_id} uploaded file '{uploaded_file['name']}' successfully. Size: {file_size_bytes} bytes.")
except Exception as e:
    log_error(e, context=f"handle_url_upload user_id={telegram_id}")
    if preparing_message:
        await preparing_message.edit_text(ERROR(str(e)))
    if 'temp_file_path' in locals() and temp_file_path and os.path.exists(temp_file_path):
        os.remove(temp_file_path)
    # --- Log failed upload ---
    file_type = os.path.splitext(file_name_to_use)[1][1:] if 'file_name_to_use' in locals() else None
    log_error(e, context="url_upload")
    logger.error(f"Error in handle_url_upload for user: {telegram_id}: {e}", extra={"user_id": telegram_id, "operation": "handle_url_upload"})

async def cancel_upload(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data is not None:
        ctx.user_data['cancel_upload'] = True
    if update.callback_query:
        await update.callback_query.answer("Upload cancelled.")
        await update.callback_query.edit_message_text("Upload cancelled.")

# (Add stubs for rename/delete/share actions if not present)
def log_rename_action(telegram_id, file_type=None):
    pass

def log_delete_action(telegram_id, file_type=None):
    pass

def log_share_action(telegram_id, file_type=None):
    pass 