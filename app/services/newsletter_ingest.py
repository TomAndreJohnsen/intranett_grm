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

    def _save_newsletter(self, newsletter_data: Dict[str, Any], conn: sqlite3.Connection) -> Dict[str, Any]:
        """Save newsletter to database."""
        try:
            cursor = conn.cursor()

            # Ensure title is set (map from subject with fallback)
            title = newsletter_data.get('subject', '').strip()
            if not title:
                title = "(Untitled newsletter)"

            # Ensure content is set (use sanitized HTML with fallback)
            content = newsletter_data.get('html_sanitized', '').strip()
            if not content:
                content = newsletter_data.get('html_raw', '').strip()
            if not content:
                content = "(No content)"

            print(f"   💾 Saving newsletter with title: '{title}'")
            logger.info(f"Saving newsletter with title: '{title}' (length: {len(content)} chars)")

            # Check if newsletter already exists
            exists = self._newsletter_exists(newsletter_data['message_id'], conn)

            if exists:
                # Update existing newsletter - update both old and new schema fields
                cursor.execute('''
                    UPDATE newsletters SET
                        title = ?, content = ?,
                        subject = ?, sender_name = ?, sender_email = ?, received_at = ?,
                        html_raw = ?, html_sanitized = ?, auth_results = ?,
                        has_attachments = ?, hero_image_path = ?
                    WHERE message_id = ?
                ''', (
                    title,  # For old schema
                    content,  # For old schema
                    newsletter_data['subject'],  # For new schema
                    newsletter_data['sender_name'],
                    newsletter_data['sender_email'],
                    newsletter_data['received_at'],
                    newsletter_data['html_raw'],
                    newsletter_data['html_sanitized'],
                    newsletter_data['auth_results'],
                    newsletter_data['has_attachments'],
                    newsletter_data['hero_image_path'],
                    newsletter_data['message_id']
                ))
                print(f"   ✅ Updated existing newsletter: '{title}'")
                logger.info(f"Updated existing newsletter: {newsletter_data['subject']}")
                action = 'updated'
            else:
                # Insert new newsletter - populate both old and new schema fields
                cursor.execute('''
                    INSERT INTO newsletters (
                        title, content,
                        message_id, subject, sender_name, sender_email, received_at,
                        html_raw, html_sanitized, auth_results, has_attachments, hero_image_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    title,  # For old schema (NOT NULL)
                    content,  # For old schema (NOT NULL)
                    newsletter_data['message_id'],  # For new schema
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
                print(f"   ✅ Inserted new newsletter: '{title}'")
                logger.info(f"Inserted new newsletter: {newsletter_data['subject']}")
                action = 'inserted'

            conn.commit()
            return {'success': True, 'action': action}

        except Exception as e:
            print(f"   ❌ Database save failed: {str(e)}")
            logger.error(f"Error saving newsletter: {e}")
            conn.rollback()
            return {'success': False, 'action': 'error', 'error': str(e)}

    def sync_newsletters(self) -> Dict[str, Any]:
        """
        Synchronize newsletters from Microsoft Graph API.

        Returns:
            Dictionary with sync results and statistics
        """
        print("🚀 Starting newsletter synchronization...")
        logger.info("Starting newsletter synchronization...")

        # Debug: Show environment variables being used
        import os
        newsletter_user = os.getenv('NEWSLETTER_USER', 'NOT_SET')
        newsletter_folder = os.getenv('NEWSLETTER_FOLDER', 'NOT_SET')
        newsletter_folder_id = os.getenv('NEWSLETTER_FOLDER_ID', 'NOT_SET')
        max_newsletters = os.getenv('MAX_NEWSLETTERS', 'NOT_SET')

        print(f"📧 Newsletter User: {newsletter_user}")
        print(f"📁 Newsletter Folder: {newsletter_folder}")
        print(f"🆔 Newsletter Folder ID: {newsletter_folder_id}")
        print(f"📊 Max Newsletters: {max_newsletters}")
        logger.info(f"Environment - User: {newsletter_user}, Folder: {newsletter_folder}, FolderID: {newsletter_folder_id}, Max: {max_newsletters}")

        # Show which resolution method will be used
        if newsletter_folder_id != 'NOT_SET' and newsletter_folder_id.strip():
            print(f"🎯 Will use explicit folder ID: {newsletter_folder_id}")
            logger.info(f"Using explicit folder ID: {newsletter_folder_id}")
        else:
            print(f"🔍 Will resolve folder by name/path: {newsletter_folder}")
            logger.info(f"Will resolve folder by name/path: {newsletter_folder}")

        sync_result = {
            'success': False,
            'processed': 0,
            'saved': 0,
            'updated': 0,
            'errors': 0,
            'messages': []
        }

        try:
            print("📡 Fetching newsletters from Microsoft Graph API...")
            logger.info("Fetching newsletters from Graph API...")

            # Fetch newsletters from Graph API
            raw_newsletters = self.graph_client.sync_newsletters()

            if not raw_newsletters:
                print("❌ No newsletters found in mailbox")
                sync_result['messages'].append("No newsletters found in mailbox")
                logger.info("No newsletters found in mailbox")
                sync_result['success'] = True
                return sync_result

            print(f"📨 Found {len(raw_newsletters)} newsletters to process")
            logger.info(f"Found {len(raw_newsletters)} newsletters to process")

            # Process each newsletter
            with self._get_db_connection() as conn:
                for i, newsletter_data in enumerate(raw_newsletters, 1):
                    try:
                        sync_result['processed'] += 1
                        message_id = newsletter_data.get('message_id', 'unknown')
                        subject = newsletter_data.get('subject', 'No Subject')
                        from_data = newsletter_data.get('from', {})
                        sender_email = from_data.get('emailAddress', {}).get('address', 'unknown')

                        print(f"\n📝 Processing newsletter {i}/{len(raw_newsletters)}")
                        print(f"   📧 Subject: {subject}")
                        print(f"   👤 Sender: {sender_email}")
                        print(f"   🆔 Message ID: {message_id}")
                        logger.info(f"Processing newsletter {i}: '{subject}' from {sender_email}")

                        # Check if newsletter already exists
                        exists = self._newsletter_exists(message_id, conn)
                        if exists:
                            print(f"   ♻️  Newsletter already exists in database")
                            logger.info(f"Newsletter {message_id} already exists")
                        else:
                            print(f"   ✨ New newsletter - will be added to database")
                            logger.info(f"Newsletter {message_id} is new")

                        # Validate newsletter (we'll handle existing vs new in _save_newsletter)
                        print(f"   🔍 Validating newsletter...")
                        validation_result = self._validate_newsletter(newsletter_data)

                        if not validation_result['valid']:
                            sync_result['errors'] += 1
                            error_msg = f"Newsletter {message_id} validation failed: {validation_result['reason']}"
                            print(f"   ❌ Validation failed: {validation_result['reason']}")
                            sync_result['messages'].append(error_msg)
                            logger.warning(error_msg)
                            continue

                        print(f"   ✅ Validation successful")
                        logger.info(f"Newsletter {message_id} validation successful")

                        # Save to database
                        print(f"   💾 Saving to database...")
                        save_result = self._save_newsletter(validation_result['processed_data'], conn)
                        if save_result['success']:
                            if save_result['action'] == 'inserted':
                                sync_result['saved'] += 1
                                print(f"   ✅ Newsletter inserted into database")
                                logger.info(f"Newsletter {message_id} inserted")
                            elif save_result['action'] == 'updated':
                                sync_result['updated'] += 1
                                print(f"   ✅ Newsletter updated in database")
                                logger.info(f"Newsletter {message_id} updated")
                        else:
                            sync_result['errors'] += 1
                            error_msg = f"Failed to save newsletter {message_id}: {save_result.get('error', 'Unknown error')}"
                            print(f"   ❌ Database save failed: {save_result.get('error', 'Unknown error')}")
                            sync_result['messages'].append(error_msg)
                            logger.error(error_msg)

                    except Exception as e:
                        sync_result['errors'] += 1
                        error_msg = f"Error processing newsletter: {str(e)}"
                        print(f"   ❌ Processing error: {str(e)}")
                        sync_result['messages'].append(error_msg)
                        logger.error(error_msg, exc_info=True)

            # Set success status
            sync_result['success'] = True

            summary = f"Newsletter sync completed: {sync_result['saved']} new, {sync_result['updated']} updated, {sync_result['errors']} errors"
            print(f"\n🎉 {summary}")
            sync_result['messages'].append(summary)
            logger.info(summary)

        except Exception as e:
            sync_result['success'] = False
            error_msg = f"Newsletter synchronization failed: {str(e)}"
            print(f"❌ Synchronization failed: {str(e)}")
            sync_result['messages'].append(error_msg)
            logger.error(error_msg, exc_info=True)

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


if __name__ == "__main__":
    """
    Test script for newsletter ingestion.
    Run with: python3 -m app.services.newsletter_ingest
    """
    import os
    import sys
    from pathlib import Path

    # Add project root to path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Environment variables loaded")
    except ImportError:
        print("⚠️  python-dotenv not installed, using system environment")

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🔧 Newsletter Ingest Service Test")
    print("=" * 50)

    # Get database path
    db_path = os.path.join(project_root, 'database.db')
    print(f"📁 Database path: {db_path}")

    if not os.path.exists(db_path):
        print(f"❌ Database file not found at {db_path}")
        sys.exit(1)

    try:
        # Create service instance
        service = NewsletterIngestService(db_path)
        print("✅ Newsletter service initialized")

        # Run synchronization
        result = service.sync_newsletters()

        # Display results
        print("\n📊 Synchronization Results:")
        print(f"   Success: {result['success']}")
        print(f"   Processed: {result['processed']}")
        print(f"   Saved: {result['saved']}")
        print(f"   Updated: {result['updated']}")
        print(f"   Errors: {result['errors']}")

        if result['messages']:
            print("\n💬 Messages:")
            for msg in result['messages']:
                print(f"   • {msg}")

        # Show recent newsletters
        print("\n📰 Recent newsletters in database:")
        recent = service.get_recent_newsletters(limit=5)
        if recent:
            for newsletter in recent:
                print(f"   • {newsletter['subject']} ({newsletter['sender_name']}) - {newsletter.get('received_at_formatted', 'No date')}")
        else:
            print("   No newsletters found in database")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.error("Test execution failed", exc_info=True)
        sys.exit(1)