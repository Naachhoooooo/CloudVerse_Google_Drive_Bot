import tempfile
import sqlite3
from .config import SCOPES, DB_PATH, CIPHER, CREDENTIALS_PATH
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from google.auth.transport.requests import Request
import requests
import re
import io
import json
from .database import get_drive_credentials, set_drive_credentials, remove_drive_credentials

def get_credentials(telegram_id, account_email):
    creds_dict = get_drive_credentials(telegram_id, account_email)
    if not creds_dict:
        return None
    from google.oauth2.credentials import Credentials
    from .config import SCOPES
    try:
        return Credentials.from_authorized_user_info(creds_dict, SCOPES)
    except Exception:
        return None

def set_credentials(telegram_id, account_email, credentials_dict):
    set_drive_credentials(telegram_id, account_email, credentials_dict)

def remove_credentials(telegram_id, account_email):
    return remove_drive_credentials(telegram_id, account_email)

def get_folder_name(service, folder_id):
    if folder_id == "root":
        return "My Drive"
    try:
        folder = service.files().get(fileId=folder_id, fields="name").execute()
        return folder["name"]
    except Exception as e:
        return "Unknown"

def list_files(service, folder_id="root", page_token=None, page_size=10):
    if service is None:
        raise ValueError("Google Drive service is not available. Check credentials and login flow.")
    query = f"'{folder_id}' in parents and trashed=false"
    res = service.files().list(q=query, pageToken=page_token, pageSize=page_size,
                              fields="nextPageToken, files(id,name,mimeType)").execute()
    return res.get("files", []), res.get("nextPageToken")

def list_trashed_files(service, page_token=None, page_size=10):
    query = "trashed=true"
    res = service.files().list(q=query, pageToken=page_token, pageSize=page_size,
                              fields="nextPageToken, files(id,name,mimeType)").execute()
    return res.get("files", []), res.get("nextPageToken")

def create_folder(service, name, parent_id=None):
    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    return service.files().create(body=metadata, fields="id").execute()

def rename_file(service, file_id, new_name):
    return service.files().update(fileId=file_id, body={"name": new_name}, fields="id,name").execute()

def delete_file(service, file_id):
    service.files().update(fileId=file_id, body={"trashed": True}).execute()
    return True

def toggle_sharing(service, file_id):
    permissions = service.permissions().list(fileId=file_id).execute().get('permissions', [])
    has_public = any(perm['type'] == 'anyone' for perm in permissions)
    if has_public:
        for perm in permissions:
            if perm['type'] == 'anyone':
                service.permissions().delete(fileId=file_id, permissionId=perm['id']).execute()
    else:
        permissions = {'type': 'anyone', 'role': 'reader'}
        service.permissions().create(fileId=file_id, body=permissions).execute()

def get_file_link(service, file_id):
    file = service.files().get(fileId=file_id, fields="webViewLink").execute()
    return file.get("webViewLink", "")

def upload_file(service, local_path, parent_id=None, progress_callback=None):
    try:
        metadata = {"name": os.path.basename(local_path)}
        if parent_id:
            metadata["parents"] = [parent_id]
        with open(local_path, "rb") as f:
            media = MediaIoBaseUpload(f, mimetype="application/octet-stream", resumable=True)
            request = service.files().create(body=metadata, media_body=media)
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status and progress_callback:
                    progress_callback(status.resumable_progress, status.total_size)
        return response
    except Exception as e:
        raise

def upload_from_url(service, url, parent_id=None, progress_callback=None):
    try:
        metadata = {"name": url.split('/')[-1] or "Untitled"}
        if parent_id:
            metadata["parents"] = [parent_id]
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('Content-Length', 0)) or None
            media = MediaIoBaseUpload(io.BytesIO(r.raw.read()), mimetype="application/octet-stream", resumable=True)
            request = service.files().create(body=metadata, media_body=media)
            response = None
            downloaded = 0
            for chunk in r.iter_content(chunk_size=1024*1024):
                downloaded += len(chunk)
                if progress_callback and total_size:
                    progress_callback(downloaded, total_size)
            while response is None:
                status, response = request.next_chunk()
                if status and progress_callback:
                    progress_callback(status.resumable_progress, status.total_size)
        return response
    except Exception as e:
        raise

def extract_drive_file_id(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else None

def search_files(service, query, page_token=None, page_size=10):
    drive_query = f"name contains '{query}' and trashed=false"
    res = service.files().list(q=drive_query, pageToken=page_token, pageSize=page_size,
                              fields="nextPageToken, files(id,name,mimeType)").execute()
    return res.get("files", []), res.get("nextPageToken")

def get_storage_info(service):
    return service.about().get(fields="storageQuota").execute()

def get_user_info(service):
    return service.about().get(fields="user").execute()

def restore_file(service, file_id):
    return service.files().update(fileId=file_id, body={"trashed": False}, fields="id,name").execute()

def empty_trash(service):
    service.files().emptyTrash().execute()
    return True