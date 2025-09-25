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

    def resolve_folder_id(self, user: str, display_name: str, token: str = None) -> Optional[str]:
        """
        Find mail folder ID by display name.

        Args:
            user: User email address
            display_name: Folder display name to search for
            token: Access token

        Returns:
            Folder ID if found, None otherwise
        """
        path = f"users/{user}/mailFolders"
        params = {'$top': 100}

        result = self.graph_get(path, params, token)
        if not result or 'value' not in result:
            logger.error(f"Failed to get mail folders for user {user}")
            return None

        # Search for folder with matching display name
        for folder in result['value']:
            if folder.get('displayName', '').lower() == display_name.lower():
                logger.info(f"Found folder '{display_name}' with ID: {folder['id']}")
                return folder['id']

        # Search in child folders if not found at root level
        for folder in result['value']:
            child_path = f"users/{user}/mailFolders/{folder['id']}/childFolders"
            child_result = self.graph_get(child_path, {'$top': 100}, token)

            if child_result and 'value' in child_result:
                for child_folder in child_result['value']:
                    if child_folder.get('displayName', '').lower() == display_name.lower():
                        logger.info(f"Found folder '{display_name}' in child folders with ID: {child_folder['id']}")
                        return child_folder['id']

        logger.warning(f"Folder '{display_name}' not found for user {user}")
        return None

    def fetch_messages(self, user: str, folder_id: str, top: int = None, token: str = None) -> List[Dict[str, Any]]:
        """
        Fetch messages from a mail folder.

        Args:
            user: User email address
            folder_id: Mail folder ID
            top: Maximum number of messages to fetch
            token: Access token

        Returns:
            List of message objects
        """
        if not top:
            top = self.max_newsletters + 10  # Buffer for deduplication

        path = f"users/{user}/mailFolders/{folder_id}/messages"
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

        Args:
            user: User email address
            message_id: Message ID
            token: Access token

        Returns:
            Detailed message object or None if failed
        """
        path = f"users/{user}/messages/{message_id}"
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

        Args:
            user: User email address
            message_id: Message ID
            token: Access token

        Returns:
            List of attachment objects
        """
        path = f"users/{user}/messages/{message_id}/attachments"

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