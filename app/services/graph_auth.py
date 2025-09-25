"""
Microsoft Graph API authentication service for newsletter integration.
Handles client credentials flow for accessing mailbox data.
"""
import msal
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GraphAuthManager:
    """Manages Microsoft Graph API authentication using client credentials flow."""

    def __init__(self):
        self.tenant_id = os.environ.get('TENANT_ID')
        self.client_id = os.environ.get('CLIENT_ID')
        self.client_secret = os.environ.get('CLIENT_SECRET')
        self.scope = os.environ.get('GRAPH_SCOPE', 'https://graph.microsoft.com/.default')
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"

        self._msal_app = None
        self._validate_config()

    def _validate_config(self):
        """Validate that all required environment variables are set."""
        required_vars = ['TENANT_ID', 'CLIENT_ID', 'CLIENT_SECRET']
        missing_vars = [var for var in required_vars if not getattr(self, var.lower())]

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def _get_msal_app(self) -> msal.ConfidentialClientApplication:
        """Get or create MSAL application instance."""
        if self._msal_app is None:
            try:
                self._msal_app = msal.ConfidentialClientApplication(
                    self.client_id,
                    authority=self.authority,
                    client_credential=self.client_secret
                )
            except Exception as e:
                logger.error(f"Failed to initialize MSAL app: {e}")
                raise

        return self._msal_app

    def get_token(self) -> Optional[str]:
        """
        Get access token using client credentials flow.

        Returns:
            Access token string if successful, None otherwise
        """
        try:
            app = self._get_msal_app()

            # Try to get token from cache first
            result = app.acquire_token_silent([self.scope], account=None)

            # If no cached token, acquire new token
            if not result:
                logger.info("No cached token found, acquiring new token...")
                result = app.acquire_token_for_client(scopes=[self.scope])

            if "access_token" in result:
                logger.info("Successfully acquired access token")
                return result["access_token"]
            else:
                error = result.get("error", "Unknown error")
                error_description = result.get("error_description", "No description")
                logger.error(f"Token acquisition failed: {error} - {error_description}")
                return None

        except Exception as e:
            logger.error(f"Exception during token acquisition: {e}")
            return None