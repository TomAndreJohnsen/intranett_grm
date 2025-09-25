"""
HTML sanitization and processing for newsletter content.
Handles cleaning HTML and processing inline images/attachments.
"""
import bleach
import base64
import os
import re
import logging
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from urllib.parse import urlparse, parse_qs, unquote
from datetime import datetime

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

    def process_safelinks(self, html_content: str) -> str:
        """
        Process Microsoft SafeLinks and extract original URLs.

        SafeLinks wrap external URLs in Microsoft's protection service:
        https://eur05.safelinks.protection.outlook.com/ap/b-59584e83/?url=<encoded_url>&data=...

        Args:
            html_content: HTML content that may contain SafeLinks

        Returns:
            HTML content with SafeLinks replaced by original URLs
        """
        if not html_content:
            return html_content

        print("🔗 Processing Microsoft SafeLinks...")
        logger.info("Starting SafeLinks processing")

        processed_html = html_content
        safelinks_found = 0
        safelinks_processed = 0

        try:
            # Pattern to match SafeLinks URLs
            safelinks_pattern = r'https?://[a-zA-Z0-9\-]+\.safelinks\.protection\.outlook\.com/[^"\'\s>]*'

            def replace_safelink(match):
                nonlocal safelinks_found, safelinks_processed
                safelinks_found += 1

                safelinks_url = match.group(0)
                original_url = self._extract_url_from_safelink(safelinks_url)

                if original_url and original_url != safelinks_url:
                    safelinks_processed += 1
                    print(f"   ✅ SafeLink → {original_url[:60]}{'...' if len(original_url) > 60 else ''}")
                    logger.info(f"Replaced SafeLink: {safelinks_url} → {original_url}")
                    return original_url
                else:
                    print(f"   ❌ Failed to extract URL from SafeLink")
                    logger.warning(f"Failed to extract URL from SafeLink: {safelinks_url}")
                    return safelinks_url

            # Replace all SafeLinks
            processed_html = re.sub(safelinks_pattern, replace_safelink, processed_html, flags=re.IGNORECASE)

            print(f"🔗 SafeLinks processing completed: {safelinks_processed}/{safelinks_found} processed")
            logger.info(f"SafeLinks processing completed: {safelinks_processed}/{safelinks_found} processed")

        except Exception as e:
            print(f"❌ SafeLinks processing failed: {e}")
            logger.error(f"SafeLinks processing failed: {e}")

        return processed_html

    def _extract_url_from_safelink(self, safelinks_url: str) -> Optional[str]:
        """
        Extract original URL from Microsoft SafeLinks URL.

        Args:
            safelinks_url: SafeLinks wrapped URL

        Returns:
            Original URL if extraction successful, None otherwise
        """
        try:
            # Parse the SafeLinks URL
            parsed = urlparse(safelinks_url)
            query_params = parse_qs(parsed.query)

            # Look for the 'url' parameter which contains the encoded original URL
            if 'url' in query_params:
                encoded_url = query_params['url'][0]
                # URL decode the original URL
                original_url = unquote(encoded_url)

                # Validate the extracted URL
                if self._is_safe_url(original_url):
                    return original_url

        except Exception as e:
            logger.warning(f"Error extracting URL from SafeLink: {e}")

        return None

    def _is_safe_url(self, url: str) -> bool:
        """
        Validate that a URL is safe to use.

        Args:
            url: URL to validate

        Returns:
            True if URL is safe, False otherwise
        """
        try:
            parsed = urlparse(url)

            # Block dangerous schemes
            dangerous_schemes = ['javascript', 'data', 'file', 'ftp']
            if parsed.scheme.lower() in dangerous_schemes:
                return False

            # Only allow http/https
            if parsed.scheme.lower() not in ['http', 'https']:
                return False

            # Basic format validation
            if not parsed.netloc:
                return False

            return True

        except Exception:
            return False

    def process_inline_images(self, html_content: str, attachments: List[Dict[str, Any]], message_id: str) -> Tuple[str, Optional[str], bool]:
        """
        Process inline images and rewrite CID references to local URLs.

        Args:
            html_content: HTML content with potential CID references
            attachments: List of attachment objects from Graph API
            message_id: Unique message identifier

        Returns:
            Tuple of (processed_html, hero_image_path, has_inline_attachments)
        """
        if not attachments:
            print("🖼️  No attachments found for CID processing")
            return html_content, None, False

        print(f"🖼️  Processing CID images for message {message_id}...")
        logger.info(f"Starting CID image processing for message {message_id}")

        processed_html = html_content
        hero_image_path = None
        processed_count = 0
        cid_images_found = 0

        try:
            # First, find all CID references in the HTML
            cid_references = set()
            cid_pattern = r'cid:([^"\'\s>]+)'
            matches = re.findall(cid_pattern, html_content, re.IGNORECASE)
            for match in matches:
                cid_references.add(match.strip('<>'))

            if cid_references:
                print(f"   📎 Found {len(cid_references)} CID references: {', '.join(list(cid_references)[:3])}{'...' if len(cid_references) > 3 else ''}")
                logger.info(f"Found CID references: {list(cid_references)}")

            # Process each attachment
            for attachment in attachments:
                # Process inline image attachments (already filtered by graph_client.py)
                if attachment.get('contentId'):

                    cid_images_found += 1
                    content_id = attachment.get('contentId', '').strip('<>')
                    content_bytes = attachment.get('contentBytes')
                    content_type = attachment.get('contentType', 'image/jpeg')
                    attachment_name = attachment.get('name', f"{content_id}")

                    print(f"   🔍 Processing CID attachment: {content_id}")
                    logger.info(f"Processing CID attachment: {content_id} ({content_type})")

                    if not content_bytes:
                        print(f"   ❌ No content bytes for attachment {content_id}")
                        logger.warning(f"No content bytes for attachment {content_id}")
                        continue

                    # Save attachment to local file
                    local_path = self._save_attachment_locally(
                        content_bytes,
                        attachment_name,
                        message_id,
                        content_id,
                        processed_count,
                        content_type
                    )

                    if local_path:
                        # Replace all CID references with local URL using comprehensive regex
                        replacements_made = self._replace_cid_references(processed_html, content_id, local_path)

                        replacements_count, updated_html = replacements_made
                        if replacements_count > 0:
                            processed_html = updated_html  # Get the processed HTML
                            processed_count += 1

                            print(f"   ✅ CID {content_id} → /static/newsletters/{local_path} ({replacements_count} replacements)")
                            logger.info(f"Replaced CID {content_id} with {local_path} ({replacements_count} replacements)")

                            # Set first processed image as hero image
                            if hero_image_path is None:
                                hero_image_path = local_path
                        else:
                            print(f"   ⚠️  CID {content_id} saved but no HTML references found")
                            logger.warning(f"CID {content_id} saved but no HTML references found")

            print(f"🖼️  CID processing completed: {processed_count}/{cid_images_found} images processed")
            logger.info(f"CID processing completed: {processed_count}/{cid_images_found} images processed")

            # Return whether we actually processed any inline attachments
            has_inline_attachments = processed_count > 0
            if has_inline_attachments:
                print(f"   🖼️  Database will be updated: has_attachments=1")
                logger.info(f"Inline attachments processed - has_attachments will be set to 1")

            return processed_html, hero_image_path, has_inline_attachments

        except Exception as e:
            print(f"❌ CID processing failed: {e}")
            logger.error(f"Error processing inline images: {e}")
            return html_content, None, False

    def _replace_cid_references(self, html_content: str, content_id: str, local_path: str) -> Tuple[int, str]:
        """
        Replace CID references with local file path using comprehensive pattern matching.

        Args:
            html_content: HTML content to process
            content_id: Content ID to find and replace
            local_path: Local file path to replace with

        Returns:
            Tuple of (number_of_replacements, processed_html)
        """
        processed_html = html_content
        total_replacements = 0

        # Clean up content_id (remove brackets if present)
        clean_content_id = content_id.strip('<>')
        local_url = f'/static/newsletters/{local_path}'

        # Enhanced comprehensive CID patterns to match all variations
        patterns = [
            # Pattern 1: Basic src attribute patterns with various quote styles
            (rf'src\s*=\s*["\']cid:{re.escape(clean_content_id)}["\']', f'src="{local_url}"'),
            (rf'src\s*=\s*cid:{re.escape(clean_content_id)}(?=\s|>)', f'src="{local_url}"'),

            # Pattern 2: Case variations
            (rf'src\s*=\s*["\']cid:{re.escape(clean_content_id.lower())}["\']', f'src="{local_url}"'),
            (rf'src\s*=\s*["\']cid:{re.escape(clean_content_id.upper())}["\']', f'src="{local_url}"'),

            # Pattern 3: CID with angle brackets (sometimes present)
            (rf'src\s*=\s*["\']cid:<{re.escape(clean_content_id)}>["\']', f'src="{local_url}"'),
            (rf'src\s*=\s*cid:<{re.escape(clean_content_id)}>(?=\s|>)', f'src="{local_url}"'),

            # Pattern 4: Any remaining basic cid: references
            (rf'cid:{re.escape(clean_content_id)}(?=["\'\s>]|$)', local_url),
            (rf'cid:{re.escape(clean_content_id.lower())}(?=["\'\s>]|$)', local_url),
            (rf'cid:{re.escape(clean_content_id.upper())}(?=["\'\s>]|$)', local_url),
        ]

        for pattern, replacement in patterns:
            # Count matches before replacement
            matches = re.finditer(pattern, processed_html, re.IGNORECASE)
            matches_count = len(list(matches))

            if matches_count > 0:
                # Replace the pattern
                new_html = re.sub(pattern, replacement, processed_html, flags=re.IGNORECASE)
                if new_html != processed_html:  # Only count if actual replacement occurred
                    total_replacements += matches_count
                    processed_html = new_html
                    print(f"      ✅ Pattern matched {matches_count} times: {pattern[:50]}...")
                    logger.info(f"CID pattern replaced {matches_count} times: {pattern}")

        # Additional safety check - look for any remaining cid: references to this content_id
        remaining_cid_pattern = rf'cid:{re.escape(clean_content_id)}'
        remaining_matches = len(re.findall(remaining_cid_pattern, processed_html, re.IGNORECASE))
        if remaining_matches > 0:
            print(f"      ⚠️  Warning: {remaining_matches} unprocessed CID references remain")
            logger.warning(f"Unprocessed CID references remain: {remaining_matches} for {clean_content_id}")

        return total_replacements, processed_html

    def _save_attachment_locally(self, content_bytes: str, filename: str, message_id: str, content_id: str, index: int, content_type: str = 'image/jpeg') -> Optional[str]:
        """
        Save attachment content to local file system.

        Args:
            content_bytes: Base64 encoded attachment content
            filename: Original filename
            message_id: Message identifier
            content_id: CID reference ID
            index: Attachment index

        Returns:
            Local filename if successful, None otherwise
        """
        try:
            # Decode base64 content
            file_data = base64.b64decode(content_bytes)

            # Generate safe filename with better uniqueness and proper extension
            safe_filename = self._generate_safe_filename(filename, message_id, content_id, index, content_type)
            file_path = os.path.join(self.uploads_dir, safe_filename)

            # Write file
            with open(file_path, 'wb') as f:
                f.write(file_data)

            print(f"   💾 Saved inline CID image: {content_id} -> /static/newsletters/{safe_filename} ({len(file_data)} bytes)")
            logger.info(f"🖼️ Saved inline CID image: {content_id} -> /static/newsletters/{safe_filename} ({len(file_data)} bytes)")
            return safe_filename

        except Exception as e:
            print(f"   ❌ Failed to save attachment: {e}")
            logger.error(f"Failed to save attachment {filename}: {e}")
            return None

    def _generate_safe_filename(self, original_filename: str, message_id: str, content_id: str, index: int, content_type: str = 'image/jpeg') -> str:
        """Generate a safe filename for storing attachments with improved uniqueness."""
        # Get file extension from original filename first
        _, ext = os.path.splitext(original_filename)

        # If no extension in filename, derive from content type
        if not ext:
            content_type_map = {
                'image/jpeg': '.jpg',
                'image/jpg': '.jpg',
                'image/png': '.png',
                'image/gif': '.gif',
                'image/bmp': '.bmp',
                'image/webp': '.webp',
                'image/tiff': '.tiff',
                'image/svg+xml': '.svg'
            }
            ext = content_type_map.get(content_type.lower(), '.jpg')  # Default to .jpg

        # Create hash from content_id for uniqueness
        content_hash = hashlib.md5(content_id.encode('utf-8')).hexdigest()[:8]

        # Add timestamp component for additional uniqueness
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Create safe filename: msg_<message_id>_<content_hash>_<index>_<timestamp><ext>
        safe_name = f"msg_{message_id[:8]}_{content_hash}_{index:03d}_{timestamp}{ext}"

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