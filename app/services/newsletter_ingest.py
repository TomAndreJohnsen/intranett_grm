"""
Newsletter ingestion service that processes emails from Microsoft Graph API.
Handles fetching, validation, sanitization, and database storage.
"""
import json
import logging
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
import pytz
from .graph_client import GraphClient
from .newsletter_sanitizer import NewsletterSanitizer

logger = logging.getLogger(__name__)


class NewsletterIngestService:
    """Service for ingesting newsletters from Microsoft Graph API."""

    def __init__(self, db_path: str, uploads_dir: str = 'uploads/newsletters'):
        self.db_path = db_path
        self.graph_client = GraphClient()
        self.sanitizer = NewsletterSanitizer(uploads_dir)
        self.oslo_tz = pytz.timezone('Europe/Oslo')

    def _get_db_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _convert_to_oslo_time(self, iso_datetime: str) -> datetime:
        """Convert ISO datetime string to Oslo timezone."""
        try:
            # Parse the ISO datetime (Graph API returns UTC)
            dt = datetime.fromisoformat(iso_datetime.replace('Z', '+00:00'))

            # Convert to Oslo timezone
            oslo_dt = dt.astimezone(self.oslo_tz)

            return oslo_dt.replace(tzinfo=None)  # Remove timezone info for SQLite storage
        except Exception as e:
            logger.error(f"Error converting datetime {iso_datetime}: {e}")
            return datetime.now()

    def _newsletter_exists(self, message_id: str, conn: sqlite3.Connection) -> bool:
        """Check if newsletter already exists in database."""
        cursor = conn.execute(
            'SELECT COUNT(*) FROM newsletters WHERE message_id = ?',
            (message_id,)
        )
        return cursor.fetchone()[0] > 0

    def _validate_newsletter(self, newsletter_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and process a single newsletter.

        Args:
            newsletter_data: Raw newsletter data from Graph API

        Returns:
            Dictionary with validation results and processed data
        """
        result = {
            'valid': False,
            'reason': '',
            'processed_data': None
        }

        try:
            # Extract basic fields
            message_id = newsletter_data.get('message_id', '')
            subject = newsletter_data.get('subject', '').strip()
            from_data = newsletter_data.get('from', {})
            received_at = newsletter_data.get('received_at', '')
            body_data = newsletter_data.get('body', {})
            headers = newsletter_data.get('headers', [])
            attachments = newsletter_data.get('attachments', [])

            # Validate required fields
            if not message_id:
                result['reason'] = 'Missing message ID'
                return result

            if not subject:
                result['reason'] = 'Missing subject'
                return result

            # Validate sender domain
            if not self.sanitizer.validate_sender_domain(from_data):
                result['reason'] = 'Invalid sender domain - must be from @gronvoldmaskin.no'
                logger.warning(f"Rejected newsletter {message_id}: invalid sender domain")
                return result

            # Parse authentication results
            auth_results = self.sanitizer.parse_authentication_results(headers)
            if auth_results.get('overall') == 'fail':
                result['reason'] = 'Failed email authentication (SPF/DKIM/DMARC)'
                logger.warning(f"Rejected newsletter {message_id}: failed authentication")
                return result

            # Extract and validate HTML content
            html_content = ''
            if body_data.get('contentType') == 'html':
                html_content = body_data.get('content', '')
            elif body_data.get('contentType') == 'text':
                # Convert plain text to basic HTML
                text_content = body_data.get('content', '')
                html_content = f'<div>{text_content.replace(chr(10), "<br>")}</div>'

            if not html_content:
                result['reason'] = 'No content found'
                return result

            # Sanitize HTML
            sanitized_html = self.sanitizer.sanitize_html(html_content)
            if not sanitized_html:
                result['reason'] = 'HTML sanitization failed'
                return result

            # Process inline images
            processed_html, hero_image_path = self.sanitizer.process_inline_images(
                sanitized_html, attachments, message_id
            )

            # Convert received datetime to Oslo timezone
            received_at_oslo = self._convert_to_oslo_time(received_at)

            # Extract sender information
            sender_email = from_data.get('emailAddress', {}).get('address', '')
            sender_name = from_data.get('emailAddress', {}).get('name', sender_email)

            # Create processed data
            processed_data = {
                'message_id': message_id,
                'subject': subject,
                'sender_name': sender_name,
                'sender_email': sender_email,
                'received_at': received_at_oslo,
                'html_raw': html_content,
                'html_sanitized': processed_html,
                'auth_results': json.dumps(auth_results),
                'has_attachments': len(attachments) > 0,
                'hero_image_path': hero_image_path
            }

            result['valid'] = True
            result['processed_data'] = processed_data
            logger.info(f"Successfully validated newsletter: {subject}")

        except Exception as e:
            result['reason'] = f'Validation error: {str(e)}'
            logger.error(f"Error validating newsletter: {e}")

        return result

    def _save_newsletter(self, newsletter_data: Dict[str, Any], conn: sqlite3.Connection) -> bool:
        """Save newsletter to database."""
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO newsletters (
                    message_id, subject, sender_name, sender_email, received_at,
                    html_raw, html_sanitized, auth_results, has_attachments, hero_image_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                newsletter_data['message_id'],
                newsletter_data['subject'],
                newsletter_data['sender_name'],
                newsletter_data['sender_email'],
                newsletter_data['received_at'],
                newsletter_data['html_raw'],
                newsletter_data['html_sanitized'],
                newsletter_data['auth_results'],
                newsletter_data['has_attachments'],
                newsletter_data['hero_image_path']
            ))

            conn.commit()
            logger.info(f"Saved newsletter: {newsletter_data['subject']}")
            return True

        except Exception as e:
            logger.error(f"Error saving newsletter: {e}")
            conn.rollback()
            return False

    def sync_newsletters(self) -> Dict[str, Any]:
        """
        Synchronize newsletters from Microsoft Graph API.

        Returns:
            Dictionary with sync results and statistics
        """
        logger.info("Starting newsletter synchronization...")

        sync_result = {
            'success': False,
            'processed': 0,
            'saved': 0,
            'skipped': 0,
            'errors': 0,
            'messages': []
        }

        try:
            # Fetch newsletters from Graph API
            raw_newsletters = self.graph_client.sync_newsletters()

            if not raw_newsletters:
                sync_result['messages'].append("No newsletters found in mailbox")
                logger.info("No newsletters found in mailbox")
                sync_result['success'] = True
                return sync_result

            # Process each newsletter
            with self._get_db_connection() as conn:
                for newsletter_data in raw_newsletters:
                    try:
                        sync_result['processed'] += 1
                        message_id = newsletter_data.get('message_id', 'unknown')

                        # Check if already exists
                        if self._newsletter_exists(message_id, conn):
                            sync_result['skipped'] += 1
                            logger.info(f"Newsletter {message_id} already exists, skipping")
                            continue

                        # Validate newsletter
                        validation_result = self._validate_newsletter(newsletter_data)

                        if not validation_result['valid']:
                            sync_result['errors'] += 1
                            error_msg = f"Newsletter {message_id} validation failed: {validation_result['reason']}"
                            sync_result['messages'].append(error_msg)
                            logger.warning(error_msg)
                            continue

                        # Save to database
                        if self._save_newsletter(validation_result['processed_data'], conn):
                            sync_result['saved'] += 1
                        else:
                            sync_result['errors'] += 1
                            sync_result['messages'].append(f"Failed to save newsletter {message_id}")

                    except Exception as e:
                        sync_result['errors'] += 1
                        error_msg = f"Error processing newsletter: {str(e)}"
                        sync_result['messages'].append(error_msg)
                        logger.error(error_msg)

            # Set success status
            sync_result['success'] = True

            summary = f"Newsletter sync completed: {sync_result['saved']} saved, {sync_result['skipped']} skipped, {sync_result['errors']} errors"
            sync_result['messages'].append(summary)
            logger.info(summary)

        except Exception as e:
            sync_result['success'] = False
            error_msg = f"Newsletter synchronization failed: {str(e)}"
            sync_result['messages'].append(error_msg)
            logger.error(error_msg)

        return sync_result

    def get_recent_newsletters(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent newsletters from database.

        Args:
            limit: Maximum number of newsletters to return

        Returns:
            List of newsletter dictionaries
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT id, message_id, subject, sender_name, sender_email,
                           received_at, html_sanitized, has_attachments, hero_image_path
                    FROM newsletters
                    ORDER BY received_at DESC
                    LIMIT ?
                ''', (limit,))

                newsletters = []
                for row in cursor.fetchall():
                    newsletter = dict(row)
                    # Format received_at for display
                    if newsletter['received_at']:
                        newsletter['received_at_formatted'] = datetime.fromisoformat(
                            newsletter['received_at']
                        ).strftime('%d.%m.%Y %H:%M')
                    newsletters.append(newsletter)

                return newsletters

        except Exception as e:
            logger.error(f"Error fetching recent newsletters: {e}")
            return []

    def get_newsletter_by_id(self, newsletter_id: int) -> Optional[Dict[str, Any]]:
        """
        Get newsletter by ID.

        Args:
            newsletter_id: Database ID of the newsletter

        Returns:
            Newsletter dictionary or None if not found
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM newsletters WHERE id = ?
                ''', (newsletter_id,))

                row = cursor.fetchone()
                if row:
                    newsletter = dict(row)
                    # Format received_at for display
                    if newsletter['received_at']:
                        newsletter['received_at_formatted'] = datetime.fromisoformat(
                            newsletter['received_at']
                        ).strftime('%d.%m.%Y %H:%M')
                    return newsletter

        except Exception as e:
            logger.error(f"Error fetching newsletter {newsletter_id}: {e}")

        return None