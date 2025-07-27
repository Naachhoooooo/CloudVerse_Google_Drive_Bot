"""
CloudVerse Google Drive Bot - Google Drive Integration Module

This module provides comprehensive integration with Google Drive API, handling
authentication, file operations, and service management for the CloudVerse Bot.
It serves as the primary interface between the Telegram bot and Google Drive,
managing user credentials and providing high-level operations.

Key Features:
- OAuth 2.0 authentication flow management
- Secure credential storage and retrieval
- File upload, download, and management operations
- Folder navigation and organization
- Search functionality across user's Drive
- Multi-account support for users
- Comprehensive error handling and logging

Google Drive Operations Supported:
- File upload (direct and from URLs)
- File download and sharing
- Folder creation and navigation
- File/folder renaming and deletion
- Search across Drive content
- Storage quota management
- Sharing and permission management

Security Features:
- Encrypted credential storage
- Secure token refresh handling
- Proper scope management
- User isolation and access control

Author: CloudVerse Team
License: Open Source
"""

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

from .Logger import drive_logger as logger

# ============================================================================
# CREDENTIAL MANAGEMENT - OAuth 2.0 credential handling for Google Drive
# ============================================================================

def get_credentials(telegram_id, account_email):
    """
    Retrieve stored Google Drive credentials for a specific user and account.
    
    This function fetches encrypted credentials from the database and converts
    them into a Google OAuth2 Credentials object that can be used to access
    the Google Drive API on behalf of the user.
    
    Args:
        telegram_id (str): The user's Telegram ID
        account_email (str): The Google account email address
        
    Returns:
        Credentials: Google OAuth2 credentials object if found and valid
        None: If no credentials exist or retrieval fails
        
    Security:
        - Credentials are stored encrypted in the database
        - Proper scope validation ensures limited access
        - User isolation prevents cross-user credential access
        
    Error Handling:
        - Logs detailed error information for debugging
        - Returns None on any failure to prevent crashes
        - Maintains user privacy in error messages
    """
    logger.debug(f"Getting credentials for user {telegram_id}, email {account_email}")
    try:
        # Retrieve encrypted credentials from database
        creds_dict = get_drive_credentials(telegram_id, account_email)
        if not creds_dict:
            logger.debug(f"No credentials found for user {telegram_id}, email {account_email}")
            return None
        
        # Convert stored credentials to Google Credentials object
        from google.oauth2.credentials import Credentials
        from .config import SCOPES
        credentials = Credentials.from_authorized_user_info(creds_dict, SCOPES)
        logger.debug(f"Successfully retrieved credentials for user {telegram_id}")
        return credentials
    except Exception as e:
        logger.error(f"Failed to get credentials for user {telegram_id}: {str(e)}", exc_info=True)
        return None

def set_credentials(telegram_id, account_email, credentials_dict):
    """
    Store Google Drive credentials for a user in encrypted format.
    
    This function takes OAuth2 credentials and stores them securely in the
    database with encryption. It's called after successful authentication
    to persist the user's access tokens for future use.
    
    Args:
        telegram_id (str): The user's Telegram ID
        account_email (str): The Google account email address
        credentials_dict (dict): Dictionary containing OAuth2 credential data
        
    Raises:
        Exception: If credential storage fails (propagated to caller)
        
    Security:
        - Credentials are encrypted before database storage
        - User isolation ensures credentials can't be accessed by others
        - Proper error handling prevents credential leakage
        
    Database Impact:
        - Creates or updates user credential record
        - Maintains credential history for audit purposes
    """
    logger.info(f"Setting credentials for user {telegram_id}, email {account_email}")
    try:
        # Store encrypted credentials in database
        set_drive_credentials(telegram_id, account_email, credentials_dict)
        logger.info(f"Successfully set credentials for user {telegram_id}")
    except Exception as e:
        logger.error(f"Failed to set credentials for user {telegram_id}: {str(e)}", exc_info=True)
        raise

def remove_credentials(telegram_id, account_email):
    """
    Remove stored Google Drive credentials for a specific user account.
    
    This function deletes the encrypted credentials from the database,
    effectively logging the user out of their Google Drive account.
    
    Args:
        telegram_id (str): The user's Telegram ID
        account_email (str): The Google account email address
        
    Returns:
        bool: True if credentials were removed successfully, False otherwise
        
    Use Cases:
        - User-initiated logout
        - Account switching
        - Security-related credential revocation
        - Admin-initiated access removal
    """
    return remove_drive_credentials(telegram_id, account_email)

# ============================================================================
# GOOGLE DRIVE FILE OPERATIONS - Core file and folder management functions
# ============================================================================

def get_folder_name(service, folder_id):
    """
    Retrieve the display name of a Google Drive folder.
    
    This function fetches the human-readable name of a folder given its ID.
    It handles the special case of the root folder and provides fallback
    for error conditions.
    
    Args:
        service: Authenticated Google Drive service instance
        folder_id (str): The Google Drive folder ID
        
    Returns:
        str: The folder name, "My Drive" for root, or "Unknown" on error
        
    Special Cases:
        - Root folder (ID: "root") returns "My Drive"
        - Invalid or inaccessible folders return "Unknown"
        - Network errors are handled gracefully
    """
    if folder_id == "root":
        return "My Drive"
    try:
        folder = service.files().get(fileId=folder_id, fields="name").execute()
        return folder["name"]
    except Exception as e:
        return "Unknown"

def list_files(service, folder_id="root", page_token=None, page_size=10):
    """
    List files and folders within a specific Google Drive directory.
    
    This function retrieves a paginated list of files and folders from a
    specified parent directory, excluding trashed items. It supports
    pagination for handling large directories efficiently.
    
    Args:
        service: Authenticated Google Drive service instance
        folder_id (str): Parent folder ID (default: "root")
        page_token (str): Token for pagination (optional)
        page_size (int): Number of items per page (default: 10)
        
    Returns:
        tuple: (files_list, next_page_token)
            - files_list: List of file/folder metadata dictionaries
            - next_page_token: Token for next page or None if last page
            
    Raises:
        ValueError: If Google Drive service is not available
        
    File Metadata Included:
        - id: Unique file identifier
        - name: File/folder display name
        - mimeType: MIME type (folders have special Google Apps type)
    """
    if service is None:
        raise ValueError("Google Drive service is not available. Check credentials and login flow.")
    
    # Query for non-trashed files in the specified parent folder
    query = f"'{folder_id}' in parents and trashed=false"
    res = service.files().list(
        q=query, 
        pageToken=page_token, 
        pageSize=page_size,
        fields="nextPageToken, files(id,name,mimeType)"
    ).execute()
    
    return res.get("files", []), res.get("nextPageToken")

def list_trashed_files(service, page_token=None, page_size=10):
    """
    List files and folders in the Google Drive trash/recycle bin.
    
    This function retrieves trashed items that can potentially be restored.
    It supports pagination for efficient handling of large trash contents.
    
    Args:
        service: Authenticated Google Drive service instance
        page_token (str): Token for pagination (optional)
        page_size (int): Number of items per page (default: 10)
        
    Returns:
        tuple: (files_list, next_page_token)
            - files_list: List of trashed file/folder metadata
            - next_page_token: Token for next page or None if last page
    """
    query = "trashed=true"
    res = service.files().list(
        q=query, 
        pageToken=page_token, 
        pageSize=page_size,
        fields="nextPageToken, files(id,name,mimeType)"
    ).execute()
    
    return res.get("files", []), res.get("nextPageToken")

def create_folder(service, name, parent_id=None):
    """
    Create a new folder in Google Drive.
    
    This function creates a new folder with the specified name, optionally
    placing it within a parent directory. If no parent is specified, the
    folder is created in the root directory.
    
    Args:
        service: Authenticated Google Drive service instance
        name (str): Name for the new folder
        parent_id (str): Parent folder ID (optional, defaults to root)
        
    Returns:
        dict: Created folder metadata including the new folder ID
        
    Google Drive Behavior:
        - Folders have the special MIME type 'application/vnd.google-apps.folder'
        - Multiple folders with the same name are allowed
        - Folder names can contain most characters except certain reserved ones
    """
    metadata = {
        "name": name, 
        "mimeType": "application/vnd.google-apps.folder"
    }
    if parent_id:
        metadata["parents"] = [parent_id]
    
    return service.files().create(body=metadata, fields="id").execute()

def rename_file(service, file_id, new_name):
    """
    Rename a file or folder in Google Drive.
    
    This function changes the display name of an existing file or folder
    without affecting its content or location.
    
    Args:
        service: Authenticated Google Drive service instance
        file_id (str): ID of the file/folder to rename
        new_name (str): New name for the file/folder
        
    Returns:
        dict: Updated file metadata including ID and new name
        
    Limitations:
        - Cannot rename files that the user doesn't have edit access to
        - Some special characters may be restricted in names
        - Renaming doesn't change the file's unique ID
    """
    return service.files().update(
        fileId=file_id, 
        body={"name": new_name}, 
        fields="id,name"
    ).execute()

def delete_file(service, file_id):
    """
    Move a file or folder to Google Drive trash.
    
    This function performs a "soft delete" by moving the item to trash
    rather than permanently deleting it. Items can be restored from trash.
    
    Args:
        service: Authenticated Google Drive service instance
        file_id (str): ID of the file/folder to delete
        
    Returns:
        bool: True if deletion was successful
        
    Note:
        - This is a reversible operation (items go to trash)
        - For permanent deletion, use the permanent delete API
        - Deleting a folder also trashes all its contents
    """
    service.files().update(fileId=file_id, body={"trashed": True}).execute()
    return True

def toggle_sharing(service, file_id):
    """
    Toggle public sharing status of a Google Drive file or folder.
    
    This function switches between private and public sharing modes.
    If the item is currently public, it makes it private. If private,
    it makes it publicly readable.
    
    Args:
        service: Authenticated Google Drive service instance
        file_id (str): ID of the file/folder to toggle sharing for
        
    Sharing Behavior:
        - Public: Anyone with the link can view (reader permission)
        - Private: Only explicitly granted users can access
        - Changes affect the entire folder tree for folders
        
    Security Considerations:
        - Public sharing makes content accessible to anyone with the link
        - Users should be aware of the implications before sharing
        - Sensitive content should remain private
    """
    # Get current permissions to check sharing status
    permissions = service.permissions().list(fileId=file_id).execute().get('permissions', [])
    has_public = any(perm['type'] == 'anyone' for perm in permissions)
    
    if has_public:
        # Remove public access (make private)
        for perm in permissions:
            if perm['type'] == 'anyone':
                service.permissions().delete(fileId=file_id, permissionId=perm['id']).execute()
    else:
        # Add public read access
        permissions = {'type': 'anyone', 'role': 'reader'}
        service.permissions().create(fileId=file_id, body=permissions).execute()

def get_file_link(service, file_id):
    """
    Get the web view link for a Google Drive file or folder.
    
    This function retrieves the shareable web URL that can be used to
    view the file in a browser or share with others.
    
    Args:
        service: Authenticated Google Drive service instance
        file_id (str): ID of the file/folder to get link for
        
    Returns:
        str: Web view URL for the file, or empty string if unavailable
        
    Link Types:
        - Files: Direct view/download link
        - Folders: Link to folder contents view
        - Shared files: Link respects sharing permissions
    """
    file = service.files().get(fileId=file_id, fields="webViewLink").execute()
    return file.get("webViewLink", "")

def upload_file(service, local_path, parent_id=None, progress_callback=None):
    """Upload a file to Google Drive"""
    file_name = os.path.basename(local_path)
    logger.info(f"Starting file upload: {file_name} to parent_id: {parent_id}")
    try:
        metadata = {"name": file_name}
        if parent_id:
            metadata["parents"] = [parent_id]
            logger.debug(f"Upload destination: folder {parent_id}")
        
        file_size = os.path.getsize(local_path)
        logger.debug(f"File size: {file_size} bytes")
        
        with open(local_path, "rb") as f:
            media = MediaIoBaseUpload(f, mimetype="application/octet-stream", resumable=True)
            request = service.files().create(body=metadata, media_body=media)
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status and progress_callback:
                    progress_callback(status.resumable_progress, status.total_size)
                    logger.debug(f"Upload progress: {status.resumable_progress}/{status.total_size}")
        
        logger.info(f"Successfully uploaded file: {file_name}, file_id: {response.get('id')}")
        return response
    except Exception as e:
        logger.error(f"Failed to upload file {file_name}: {str(e)}", exc_info=True)
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