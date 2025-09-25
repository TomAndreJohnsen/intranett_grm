"""
Microsoft Graph API authentication service for newsletter integration.
Handles delegated permissions with device code flow for accessing mailbox data.
"""
import msal
import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class GraphAuthManager:
    """Manages Microsoft Graph API authentication using delegated permissions with device code flow."""

    def __init__(self, token_cache_file: str = "token_cache.json"):
        self.tenant_id = os.environ.get('TENANT_ID')
        self.client_id = os.environ.get('CLIENT_ID')
        self.scope = os.environ.get('GRAPH_SCOPE', 'Mail.Read')
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.token_cache_file = token_cache_file

        self._msal_app = None
        self._token_cache = None
        self._validate_config()

    def _validate_config(self):
        """Validate that all required environment variables are set."""
        required_vars = ['TENANT_ID', 'CLIENT_ID']
        missing_vars = [var for var in required_vars if not getattr(self, var.lower())]

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def _load_token_cache(self) -> msal.SerializableTokenCache:
        """Load token cache from file or create new one."""
        cache = msal.SerializableTokenCache()

        if os.path.exists(self.token_cache_file):
            try:
                with open(self.token_cache_file, 'r') as f:
                    cache.deserialize(f.read())
                logger.info(f"Loaded token cache from {self.token_cache_file}")
            except Exception as e:
                logger.warning(f"Failed to load token cache: {e}")
        else:
            logger.info("No existing token cache found")

        return cache

    def _save_token_cache(self, cache: msal.SerializableTokenCache):
        """Save token cache to file."""
        try:
            with open(self.token_cache_file, 'w') as f:
                f.write(cache.serialize())
            logger.info(f"Saved token cache to {self.token_cache_file}")
        except Exception as e:
            logger.error(f"Failed to save token cache: {e}")

    def _get_msal_app(self) -> msal.PublicClientApplication:
        """Get or create MSAL application instance."""
        if self._msal_app is None:
            try:
                # Load or create token cache
                self._token_cache = self._load_token_cache()

                self._msal_app = msal.PublicClientApplication(
                    self.client_id,
                    authority=self.authority,
                    token_cache=self._token_cache
                )
                logger.info("Initialized MSAL PublicClientApplication")
            except Exception as e:
                logger.error(f"Failed to initialize MSAL app: {e}")
                raise

        return self._msal_app

    def _acquire_token_by_device_flow(self) -> Optional[Dict[str, Any]]:
        """Acquire token using device code flow."""
        try:
            app = self._get_msal_app()

            # Initiate device flow
            flow = app.initiate_device_flow(scopes=[self.scope])

            if "user_code" not in flow:
                logger.error("Failed to create device flow")
                return None

            print("\n" + "="*60)
            print("📱 NEWSLETTER AUTHENTICATION REQUIRED")
            print("="*60)
            print(f"Please visit: {flow['verification_uri']}")
            print(f"And enter code: {flow['user_code']}")
            print("\n⚠️  IMPORTANT: Sign in as: nyhetsbrev@gronvoldmaskin.no")
            print("This is a one-time setup - future runs will be automatic.")
            print("="*60)

            # Wait for user to complete the flow
            result = app.acquire_token_by_device_flow(flow)

            if "access_token" in result:
                logger.info("Successfully acquired token via device code flow")
                # Save the updated cache
                self._save_token_cache(self._token_cache)
                return result
            else:
                error = result.get("error", "Unknown error")
                error_description = result.get("error_description", "No description")
                logger.error(f"Device flow authentication failed: {error} - {error_description}")
                return None

        except Exception as e:
            logger.error(f"Exception during device flow: {e}")
            return None

    def get_token(self) -> Optional[str]:
        """
        Get access token using delegated permissions.

        First tries to get token silently from cache (using refresh token),
        falls back to device code flow if needed.

        Returns:
            Access token string if successful, None otherwise
        """
        try:
            app = self._get_msal_app()

            # Get accounts from cache
            accounts = app.get_accounts()

            if accounts:
                # Try to get token silently using cached refresh token
                logger.info("Attempting silent token acquisition...")
                result = app.acquire_token_silent(
                    scopes=[self.scope],
                    account=accounts[0]  # Use first account
                )

                if result and "access_token" in result:
                    logger.info("Successfully acquired token silently")
                    # Save updated cache (refresh token may have been updated)
                    self._save_token_cache(self._token_cache)
                    return result["access_token"]
                else:
                    logger.info("Silent token acquisition failed, trying device flow")
            else:
                logger.info("No cached accounts found, using device flow")

            # Fall back to device code flow
            result = self._acquire_token_by_device_flow()

            if result and "access_token" in result:
                return result["access_token"]
            else:
                return None

        except Exception as e:
            logger.error(f"Exception during token acquisition: {e}")
            return None

    def clear_cache(self):
        """Clear the token cache (for testing/reset purposes)."""
        try:
            if os.path.exists(self.token_cache_file):
                os.remove(self.token_cache_file)
                logger.info("Token cache cleared")

            # Reset in-memory cache
            self._token_cache = None
            self._msal_app = None

        except Exception as e:
            logger.error(f"Failed to clear token cache: {e}")

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the current token cache."""
        try:
            app = self._get_msal_app()
            accounts = app.get_accounts()

            return {
                "cache_file_exists": os.path.exists(self.token_cache_file),
                "accounts_count": len(accounts),
                "accounts": [
                    {
                        "username": account.get("username"),
                        "local_account_id": account.get("local_account_id")
                    } for account in accounts
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get cache info: {e}")
            return {"error": str(e)}