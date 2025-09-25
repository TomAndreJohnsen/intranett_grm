"""
HTML sanitization and processing for newsletter content.
Handles cleaning HTML and processing inline images/attachments.
"""
import bleach
import base64
import os
import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class NewsletterSanitizer:
    """Sanitizes HTML content and processes inline images for newsletters."""

    # Allowed HTML tags with their permitted attributes
    ALLOWED_TAGS = [
        'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'div', 'span', 'blockquote', 'pre', 'code',
        'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'hr', 'small', 'sub', 'sup'
    ]

    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title', 'width', 'height', 'style'],
        'div': ['style'],
        'span': ['style'],
        'p': ['style'],
        'table': ['style', 'border', 'cellpadding', 'cellspacing'],
        'th': ['style', 'colspan', 'rowspan'],
        'td': ['style', 'colspan', 'rowspan'],
        '*': ['class']  # Allow class attribute on all elements
    }

    # Allowed CSS properties (whitelist approach)
    ALLOWED_STYLES = [
        'color', 'background-color', 'font-size', 'font-weight', 'font-family',
        'text-align', 'text-decoration', 'margin', 'padding', 'border',
        'border-color', 'border-width', 'border-style',
        'width', 'height', 'max-width', 'max-height',
        'display', 'float', 'clear'
    ]

    # Allowed URL schemes
    ALLOWED_PROTOCOLS = ['http', 'https', 'mailto', 'data']

    def __init__(self, uploads_dir: str = 'uploads/newsletters'):
        self.uploads_dir = uploads_dir
        self.ensure_uploads_directory()

    def ensure_uploads_directory(self):
        """Ensure the uploads directory exists."""
        try:
            os.makedirs(self.uploads_dir, exist_ok=True)
            logger.info(f"Uploads directory ensured: {self.uploads_dir}")
        except Exception as e:
            logger.error(f"Failed to create uploads directory: {e}")

    def _css_sanitizer(self, tag: str, name: str, value: str) -> bool:
        """
        Custom CSS sanitizer to allow only safe styles.

        Args:
            tag: HTML tag name
            name: CSS property name
            value: CSS property value

        Returns:
            True if style is allowed, False otherwise
        """
        if name.lower() not in [style.lower() for style in self.ALLOWED_STYLES]:
            return False

        # Additional checks for specific properties
        if name.lower() in ['background-color', 'color']:
            # Allow named colors, hex, rgb, rgba
            if not re.match(r'^(#[0-9a-fA-F]{3,6}|rgb\([^)]+\)|rgba\([^)]+\)|[a-zA-Z]+)$', value.strip()):
                return False

        # Block potentially dangerous values
        dangerous_patterns = [
            r'javascript:', r'expression\(', r'@import', r'url\(',
            r'behavior:', r'binding:', r'mozbinding:'
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False

        return True

    def sanitize_html(self, html_content: str) -> str:
        """
        Sanitize HTML content using bleach with custom filters.

        Args:
            html_content: Raw HTML content

        Returns:
            Sanitized HTML content
        """
        if not html_content:
            return ""

        try:
            print("🧹 Starting HTML sanitization...")
            logger.info("Starting HTML sanitization")

            # Clean HTML with bleach (bleach>=5.0 compatible)
            clean_html = bleach.clean(
                html_content,
                tags=self.ALLOWED_TAGS,
                attributes=self.ALLOWED_ATTRIBUTES,
                protocols=self.ALLOWED_PROTOCOLS,
                strip=True,
                strip_comments=True,
            )

            # Additional custom sanitization for CSS styles
            clean_html = self._remove_dangerous_attributes(clean_html)
            clean_html = self._sanitize_inline_styles(clean_html)

            print("✅ HTML sanitization completed successfully")
            logger.info("HTML sanitization completed successfully")
            return clean_html

        except Exception as e:
            print(f"❌ HTML sanitization failed: {e}")
            logger.error(f"HTML sanitization failed: {e}")
            # Return plain text as fallback
            return bleach.clean(html_content, tags=[], attributes={}, strip=True)

    def _remove_dangerous_attributes(self, html: str) -> str:
        """Remove potentially dangerous attributes that might have slipped through."""
        # Remove event handlers
        html = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)

        # Remove javascript: URLs
        html = re.sub(r'javascript:[^"\'>\s]*', '', html, flags=re.IGNORECASE)

        return html

    def _sanitize_inline_styles(self, html: str) -> str:
        """Additional sanitization of inline styles."""
        def clean_style_attribute(match):
            style_content = match.group(1)
            clean_styles = []

            # Parse CSS properties
            for style_rule in style_content.split(';'):
                if ':' in style_rule:
                    prop, value = style_rule.split(':', 1)
                    prop = prop.strip()
                    value = value.strip()

                    if self._css_sanitizer('', prop, value):
                        clean_styles.append(f"{prop}: {value}")

            if clean_styles:
                return f'style="{"; ".join(clean_styles)}"'
            else:
                return ''

        # Clean inline styles
        return re.sub(r'style\s*=\s*["\']([^"\']*)["\']', clean_style_attribute, html, flags=re.IGNORECASE)

    def process_inline_images(self, html_content: str, attachments: List[Dict[str, Any]], message_id: str) -> Tuple[str, Optional[str]]:
        """
        Process inline images and rewrite CID references to local URLs.

        Args:
            html_content: HTML content with potential CID references
            attachments: List of attachment objects from Graph API
            message_id: Unique message identifier

        Returns:
            Tuple of (processed_html, hero_image_path)
        """
        if not attachments:
            return html_content, None

        processed_html = html_content
        hero_image_path = None
        processed_count = 0

        try:
            # Process each attachment
            for attachment in attachments:
                # Only process inline image attachments
                if (attachment.get('@odata.type') == '#microsoft.graph.fileAttachment' and
                    attachment.get('contentType', '').startswith('image/') and
                    attachment.get('contentId')):

                    content_id = attachment.get('contentId', '').strip('<>')
                    content_bytes = attachment.get('contentBytes')

                    if not content_bytes:
                        logger.warning(f"No content bytes for attachment {content_id}")
                        continue

                    # Save attachment to local file
                    local_path = self._save_attachment_locally(
                        content_bytes,
                        attachment.get('name', f"{content_id}.jpg"),
                        message_id,
                        processed_count
                    )

                    if local_path:
                        # Replace CID references with local URL
                        cid_patterns = [
                            f'cid:{content_id}',
                            f'src="cid:{content_id}"',
                            f"src='cid:{content_id}'",
                            f'src=cid:{content_id}'
                        ]

                        for pattern in cid_patterns:
                            processed_html = processed_html.replace(pattern, f'src="/static/newsletters/{local_path}"')

                        # Set first processed image as hero image
                        if hero_image_path is None:
                            hero_image_path = local_path

                        processed_count += 1
                        logger.info(f"Processed inline image: {content_id} -> {local_path}")

            logger.info(f"Processed {processed_count} inline images for message {message_id}")
            return processed_html, hero_image_path

        except Exception as e:
            logger.error(f"Error processing inline images: {e}")
            return html_content, None

    def _save_attachment_locally(self, content_bytes: str, filename: str, message_id: str, index: int) -> Optional[str]:
        """
        Save attachment content to local file system.

        Args:
            content_bytes: Base64 encoded attachment content
            filename: Original filename
            message_id: Message identifier
            index: Attachment index

        Returns:
            Local filename if successful, None otherwise
        """
        try:
            # Decode base64 content
            file_data = base64.b64decode(content_bytes)

            # Generate safe filename
            safe_filename = self._generate_safe_filename(filename, message_id, index)
            file_path = os.path.join(self.uploads_dir, safe_filename)

            # Write file
            with open(file_path, 'wb') as f:
                f.write(file_data)

            logger.info(f"Saved attachment: {safe_filename}")
            return safe_filename

        except Exception as e:
            logger.error(f"Failed to save attachment {filename}: {e}")
            return None

    def _generate_safe_filename(self, original_filename: str, message_id: str, index: int) -> str:
        """Generate a safe filename for storing attachments."""
        # Get file extension
        _, ext = os.path.splitext(original_filename)
        if not ext:
            ext = '.jpg'  # Default for images

        # Create safe filename with message ID and index
        safe_name = f"{message_id[:8]}_{index}{ext}"

        # Remove any remaining unsafe characters
        safe_name = re.sub(r'[^\w\-_\.]', '_', safe_name)

        return safe_name

    def validate_sender_domain(self, from_address: Dict[str, Any], required_domain: str = '@gronvoldmaskin.no') -> bool:
        """
        Validate that the email sender is from the required domain.

        Args:
            from_address: From address object from Graph API
            required_domain: Required email domain

        Returns:
            True if sender is from required domain
        """
        try:
            email_address = from_address.get('emailAddress', {}).get('address', '')
            if email_address:
                return email_address.lower().endswith(required_domain.lower())
        except Exception as e:
            logger.error(f"Error validating sender domain: {e}")

        return False

    def parse_authentication_results(self, headers: List[Dict[str, str]]) -> Dict[str, str]:
        """
        Parse Authentication-Results headers to extract SPF, DKIM, DMARC results.

        Args:
            headers: List of message headers

        Returns:
            Dictionary with authentication results
        """
        auth_results = {
            'spf': 'not_found',
            'dkim': 'not_found',
            'dmarc': 'not_found',
            'overall': 'unknown'
        }

        try:
            for header in headers:
                if header.get('name', '').lower() == 'authentication-results':
                    auth_value = header.get('value', '').lower()

                    # Parse SPF
                    spf_match = re.search(r'spf=([^\s;]+)', auth_value)
                    if spf_match:
                        auth_results['spf'] = spf_match.group(1)

                    # Parse DKIM
                    dkim_match = re.search(r'dkim=([^\s;]+)', auth_value)
                    if dkim_match:
                        auth_results['dkim'] = dkim_match.group(1)

                    # Parse DMARC
                    dmarc_match = re.search(r'dmarc=([^\s;]+)', auth_value)
                    if dmarc_match:
                        auth_results['dmarc'] = dmarc_match.group(1)

            # Determine overall result
            if all(result in ['pass', 'none'] for result in [auth_results['spf'], auth_results['dkim'], auth_results['dmarc']] if result != 'not_found'):
                auth_results['overall'] = 'pass'
            elif any(result == 'fail' for result in [auth_results['spf'], auth_results['dkim'], auth_results['dmarc']]):
                auth_results['overall'] = 'fail'
            else:
                auth_results['overall'] = 'partial'

            logger.info(f"Authentication results parsed: {auth_results}")

        except Exception as e:
            logger.error(f"Error parsing authentication results: {e}")

        return auth_results