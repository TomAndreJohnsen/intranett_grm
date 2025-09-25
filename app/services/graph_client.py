"""
Microsoft Graph API client for newsletter integration.
Provides helper functions for making Graph API requests.
"""
import requests
import os
import logging
from typing import Optional, Dict, List, Any
from urllib.parse import urlencode
from .graph_auth import GraphAuthManager

logger = logging.getLogger(__name__)


class GraphClient:
    """Client for making Microsoft Graph API requests."""

    def __init__(self):
        self.base_url = os.environ.get('GRAPH_BASE', 'https://graph.microsoft.com/v1.0')
        self.newsletter_user = os.environ.get('NEWSLETTER_USER', 'nyhetsbrev@gronvoldmaskin.no')
        self.newsletter_folder = os.environ.get('NEWSLETTER_FOLDER', 'Godkjent')
        self.max_newsletters = int(os.environ.get('MAX_NEWSLETTERS', '10'))

        self.auth_manager = GraphAuthManager()

    def _get_headers(self, token: str) -> Dict[str, str]:
        """Get HTTP headers with authorization token."""
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def graph_get(self, path: str, params: Dict[str, Any] = None, token: str = None) -> Optional[Dict[str, Any]]:
        """
        Make GET request to Microsoft Graph API.

        Args:
            path: API endpoint path (without base URL)
            params: Query parameters
            token: Access token (if None, will acquire new token)

        Returns:
            JSON response data or None if failed
        """
        if not token:
            token = self.auth_manager.get_token()
            if not token:
                logger.error("Failed to acquire access token")
                return None

        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            url += f"?{urlencode(params, safe='$,')}"

        try:
            headers = self._get_headers(token)
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Graph API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Error details: {error_detail}")
                except:
                    logger.error(f"Response content: {e.response.text}")
            return None

    def resolve_folder_id(self, user: str, display_name_or_path: str, token: str = None) -> Optional[str]:
        """
        Find mail folder ID by display name or folder path.

        Supports two modes:
        1. If NEWSLETTER_FOLDER_ID env var is set, use it directly
        2. Otherwise, resolve by display name or path traversal

        For delegated permissions, we use /me/ endpoint since token is scoped to specific user.

        Args:
            user: User email address (ignored for delegated permissions)
            display_name_or_path: Folder display name or path (e.g., "Inbox/Subfolder")
            token: Access token

        Returns:
            Folder ID if found, None otherwise
        """
        # Check if explicit folder ID is provided in environment
        explicit_folder_id = os.environ.get('NEWSLETTER_FOLDER_ID', '').strip()
        if explicit_folder_id:
            logger.info(f"Using explicit folder ID from NEWSLETTER_FOLDER_ID: {explicit_folder_id}")
            print(f"📁 Using explicit folder ID: {explicit_folder_id}")
            return explicit_folder_id

        logger.info(f"Resolving folder path: '{display_name_or_path}'")
        print(f"📁 Resolving folder by name/path: '{display_name_or_path}'")

        # Check if it's a path (contains "/")
        if "/" in display_name_or_path:
            return self._resolve_folder_by_path(display_name_or_path, token)
        else:
            return self._resolve_folder_by_name(display_name_or_path, token)

    def _resolve_folder_by_name(self, display_name: str, token: str = None) -> Optional[str]:
        """
        Find mail folder ID by display name, searching root and child folders.
        """
        logger.info(f"Searching for folder by name: '{display_name}'")
        print(f"🔍 Searching for folder by name: '{display_name}'")

        # For delegated permissions, use /me/ endpoint
        path = "me/mailFolders"
        params = {'$top': 100}

        result = self.graph_get(path, params, token)
        if not result or 'value' not in result:
            logger.error("Failed to get root mail folders")
            print("❌ Failed to get root mail folders")
            return None

        logger.info(f"Found {len(result['value'])} root folders to search")
        print(f"📂 Found {len(result['value'])} root folders to search")

        # Search for folder with matching display name in root
        for folder in result['value']:
            folder_name = folder.get('displayName', '')
            folder_id = folder.get('id', '')

            if folder_name.lower() == display_name.lower():
                logger.info(f"✅ Found folder '{display_name}' at root level with ID: {folder_id}")
                print(f"✅ Found folder '{display_name}' at root level")
                print(f"   ID: {folder_id}")
                return folder_id

        # Search in child folders if not found at root level
        logger.info("Folder not found at root level, searching child folders...")
        print("🔍 Folder not found at root level, searching child folders...")

        for folder in result['value']:
            parent_name = folder.get('displayName', 'Unknown')
            parent_id = folder.get('id', '')

            logger.info(f"Searching in parent folder: '{parent_name}'")
            print(f"📁 Searching in parent folder: '{parent_name}'")

            child_path = f"me/mailFolders/{parent_id}/childFolders"
            child_result = self.graph_get(child_path, {'$top': 100}, token)

            if child_result and 'value' in child_result:
                logger.info(f"Found {len(child_result['value'])} child folders in '{parent_name}'")
                print(f"   📂 Found {len(child_result['value'])} child folders")

                for child_folder in child_result['value']:
                    child_name = child_folder.get('displayName', '')
                    child_id = child_folder.get('id', '')

                    logger.info(f"   Checking child folder: '{child_name}' (ID: {child_id})")
                    print(f"   - {child_name}")

                    if child_name.lower() == display_name.lower():
                        logger.info(f"✅ Found folder '{display_name}' in '{parent_name}' with ID: {child_id}")
                        print(f"✅ Found folder '{display_name}' in '{parent_name}'")
                        print(f"   ID: {child_id}")
                        return child_id

        logger.warning(f"❌ Folder '{display_name}' not found")
        print(f"❌ Folder '{display_name}' not found")
        return None

    def _resolve_folder_by_path(self, folder_path: str, token: str = None) -> Optional[str]:
        """
        Find mail folder ID by traversing a path (e.g., "Inbox/Subfolder/Target").
        Starts from well-known 'Inbox' folder.
        """
        logger.info(f"Resolving folder by path: '{folder_path}'")
        print(f"🗂️  Resolving folder by path: '{folder_path}'")

        path_parts = [part.strip() for part in folder_path.split('/') if part.strip()]
        if not path_parts:
            logger.error("Empty folder path provided")
            print("❌ Empty folder path provided")
            return None

        logger.info(f"Path parts to traverse: {path_parts}")
        print(f"📋 Path parts to traverse: {' → '.join(path_parts)}")

        # Start from inbox if first part is not a well-known folder
        current_folder_id = None
        start_index = 0

        # Try to find the first folder in root folders
        path = "me/mailFolders"
        params = {'$top': 100}
        result = self.graph_get(path, params, token)

        if not result or 'value' not in result:
            logger.error("Failed to get root mail folders for path traversal")
            print("❌ Failed to get root mail folders for path traversal")
            return None

        # Look for the first path part in root folders
        first_part = path_parts[0]
        for folder in result['value']:
            if folder.get('displayName', '').lower() == first_part.lower():
                current_folder_id = folder['id']
                start_index = 1
                logger.info(f"✅ Found root folder '{first_part}' with ID: {current_folder_id}")
                print(f"✅ Found root folder '{first_part}'")
                break

        # If first part not found in root, start from Inbox
        if current_folder_id is None:
            for folder in result['value']:
                if folder.get('displayName', '').lower() == 'inbox':
                    current_folder_id = folder['id']
                    logger.info(f"Starting traversal from Inbox (ID: {current_folder_id})")
                    print(f"📥 Starting traversal from Inbox")
                    break

        if current_folder_id is None:
            logger.error("Could not find Inbox or starting folder")
            print("❌ Could not find Inbox or starting folder")
            return None

        # Traverse the remaining path parts
        for i, part in enumerate(path_parts[start_index:], start_index):
            logger.info(f"Looking for folder '{part}' in current folder")
            print(f"🔍 Step {i+1}: Looking for '{part}'")

            child_path = f"me/mailFolders/{current_folder_id}/childFolders"
            child_result = self.graph_get(child_path, {'$top': 100}, token)

            if not child_result or 'value' not in child_result:
                logger.error(f"Failed to get child folders at step {i+1}")
                print(f"❌ Failed to get child folders at step {i+1}")
                return None

            found = False
            for child_folder in child_result['value']:
                child_name = child_folder.get('displayName', '')
                child_id = child_folder.get('id', '')

                logger.info(f"   Checking child folder: '{child_name}'")
                print(f"   - {child_name}")

                if child_name.lower() == part.lower():
                    current_folder_id = child_id
                    found = True
                    logger.info(f"✅ Found '{part}' with ID: {child_id}")
                    print(f"✅ Found '{part}'")
                    break

            if not found:
                logger.error(f"❌ Folder '{part}' not found in path traversal")
                print(f"❌ Folder '{part}' not found in path traversal")
                return None

        logger.info(f"✅ Successfully resolved path '{folder_path}' to ID: {current_folder_id}")
        print(f"✅ Successfully resolved path to final folder")
        print(f"   Final ID: {current_folder_id}")
        return current_folder_id

    def fetch_messages(self, user: str, folder_id: str, top: int = None, token: str = None) -> List[Dict[str, Any]]:
        """
        Fetch messages from a mail folder.

        For delegated permissions, we use /me/ endpoint since token is scoped to specific user.

        Args:
            user: User email address (ignored for delegated permissions)
            folder_id: Mail folder ID
            top: Maximum number of messages to fetch
            token: Access token

        Returns:
            List of message objects
        """
        if not top:
            top = self.max_newsletters + 10  # Buffer for deduplication

        path = f"me/mailFolders/{folder_id}/messages"
        params = {
            '$top': top,
            '$orderby': 'receivedDateTime desc',
            '$select': 'id,subject,from,receivedDateTime,hasAttachments,bodyPreview'
        }

        result = self.graph_get(path, params, token)
        if not result or 'value' not in result:
            logger.error(f"Failed to fetch messages from folder {folder_id}")
            return []

        logger.info(f"Found {len(result['value'])} messages in folder")
        return result['value']

    def get_message_details(self, user: str, message_id: str, token: str = None) -> Optional[Dict[str, Any]]:
        """
        Get detailed message information including body and headers.

        For delegated permissions, we use /me/ endpoint since token is scoped to specific user.

        Args:
            user: User email address (ignored for delegated permissions)
            message_id: Message ID
            token: Access token

        Returns:
            Detailed message object or None if failed
        """
        path = f"me/messages/{message_id}"
        params = {
            '$select': 'internetMessageHeaders,subject,from,receivedDateTime,body,hasAttachments'
        }

        result = self.graph_get(path, params, token)
        if not result:
            logger.error(f"Failed to get message details for {message_id}")
            return None

        return result

    def get_message_attachments(self, user: str, message_id: str, token: str = None) -> List[Dict[str, Any]]:
        """
        Get message attachments.

        For delegated permissions, we use /me/ endpoint since token is scoped to specific user.

        Args:
            user: User email address (ignored for delegated permissions)
            message_id: Message ID
            token: Access token

        Returns:
            List of attachment objects
        """
        path = f"me/messages/{message_id}/attachments"

        result = self.graph_get(path, token=token)
        if not result or 'value' not in result:
            logger.warning(f"No attachments found for message {message_id}")
            return []

        return result['value']

    def sync_newsletters(self) -> List[Dict[str, Any]]:
        """
        Synchronize newsletters from the configured mailbox and folder.

        Returns:
            List of processed newsletter data
        """
        logger.info("Starting newsletter synchronization...")

        try:
            # Get access token
            token = self.auth_manager.get_token()
            if not token:
                raise Exception("Failed to acquire access token")

            # Resolve folder ID
            folder_id = self.resolve_folder_id(self.newsletter_user, self.newsletter_folder, token)
            if not folder_id:
                raise Exception(f"Folder '{self.newsletter_folder}' not found for user {self.newsletter_user}")

            # Fetch messages
            messages = self.fetch_messages(self.newsletter_user, folder_id, self.max_newsletters + 10, token)
            if not messages:
                logger.info("No messages found in newsletter folder")
                return []

            newsletters = []
            for message in messages:
                try:
                    # Get detailed message info
                    details = self.get_message_details(self.newsletter_user, message['id'], token)
                    if not details:
                        continue

                    # Get attachments if present
                    attachments = []
                    if message.get('hasAttachments'):
                        attachments = self.get_message_attachments(self.newsletter_user, message['id'], token)

                    # Create newsletter data object
                    newsletter_data = {
                        'message_id': message['id'],
                        'subject': details.get('subject', ''),
                        'from': details.get('from', {}),
                        'received_at': details.get('receivedDateTime', ''),
                        'body': details.get('body', {}),
                        'headers': details.get('internetMessageHeaders', []),
                        'attachments': attachments,
                        'has_attachments': bool(attachments)
                    }

                    newsletters.append(newsletter_data)

                except Exception as e:
                    logger.error(f"Error processing message {message.get('id')}: {e}")
                    continue

            logger.info(f"Successfully processed {len(newsletters)} newsletters")
            return newsletters

        except Exception as e:
            logger.error(f"Newsletter synchronization failed: {e}")
            return []