# Newsletter Image Processing Fixes

## Problem Solved
Newsletter images were not displaying correctly in the intranet dashboard due to:
1. **CID Images**: `<img src="cid:...">` references not being processed properly
2. **SafeLinks**: Microsoft's wrapped URLs preventing external image loading
3. **Processing Order**: HTML sanitization removing image tags before CID processing

## Solution Implemented

### 🔗 **SafeLinks Processing**
- **New Method**: `process_safelinks()` in `newsletter_sanitizer.py`
- **Function**: Detects and unwraps Microsoft SafeLinks URLs
- **Pattern**: `https://*.safelinks.protection.outlook.com/...?url=<encoded_url>`
- **Result**: Extracts original URLs from SafeLinks wrapper

### 🖼️ **Enhanced CID Image Processing**
- **Improved Pattern Matching**: Comprehensive regex patterns for all CID variations
- **Better Filename Generation**: Unique filenames with hash + timestamp
- **Comprehensive Logging**: Detailed debug output for troubleshooting

### 📋 **Fixed Processing Pipeline**
```
OLD (Broken):
HTML Content → Sanitize HTML → Process CID Images
❌ Sanitizer removes/modifies <img> tags before CID processing

NEW (Fixed):
HTML Content → Process SafeLinks → Process CID Images → Sanitize HTML
✅ Images processed before sanitization preserves <img> tags
```

## Technical Implementation

### **Files Modified:**

#### **1. `app/services/newsletter_sanitizer.py`**
- ✅ Added `process_safelinks()` method
- ✅ Enhanced `process_inline_images()` with better pattern matching
- ✅ Improved `_generate_safe_filename()` with hash + timestamp
- ✅ Added `_replace_cid_references()` with comprehensive regex patterns
- ✅ Added URL validation in `_is_safe_url()`

#### **2. `app/services/newsletter_ingest.py`**
- ✅ Reordered processing pipeline in `_validate_newsletter()`
- ✅ Added debug logging for each processing step

### **New Processing Flow:**

```python
# Step 1: Process SafeLinks (before sanitization)
safelinks_processed_html = sanitizer.process_safelinks(html_content)

# Step 2: Process CID images (before sanitization)
images_processed_html, hero_image_path = sanitizer.process_inline_images(
    safelinks_processed_html, attachments, message_id
)

# Step 3: Sanitize HTML (now processes clean img tags with local paths)
sanitized_html = sanitizer.sanitize_html(images_processed_html)
```

### **Enhanced CID Pattern Matching:**
- **Basic patterns**: `cid:image001`, `cid:IMAGE001` (case variations)
- **Quoted patterns**: `"cid:image001"`, `'cid:image001'`
- **Attribute patterns**: `src="cid:image001"`, `src=cid:image001`
- **Regex-based**: Handles whitespace, mixed cases, all quote variations

### **Improved Filename Generation:**
```python
# Format: msg_<msg_id>_<content_hash>_<index>_<timestamp>.<ext>
# Example: msg_abc12345_d4f7a2c8_001_20241225_143022.jpg
```

## Expected Debug Output

### **SafeLinks Processing:**
```
🔗 Processing Microsoft SafeLinks...
   ✅ SafeLink → https://example.com/image.jpg
🔗 SafeLinks processing completed: 2/2 processed
```

### **CID Image Processing:**
```
🖼️  Processing CID images for message ABC123...
   📎 Found 3 CID references: image001, image002, image003
   🔍 Processing CID attachment: image001@company.com
   💾 Saved: msg_abc12345_d4f7a2c8_001_20241225_143022.jpg (45672 bytes)
   ✅ CID image001@company.com → /static/newsletters/msg_abc12345_d4f7a2c8_001_20241225_143022.jpg (2 replacements)
🖼️  CID processing completed: 3/3 images processed
```

## Testing Instructions

### **1. Start Flask Application**
```bash
python3 main.py
```

### **2. Sync Newsletters with Debug Output**
```bash
python3 -m app.services.newsletter_ingest
```

### **3. Capture Screenshot for Visual Verification**
```bash
node screenshot.js
```

### **4. Check Newsletter Images**
- Navigate to `/dashboard` in browser
- Newsletter cards should display all images correctly
- Check browser developer tools for any 404 errors on image URLs

## Security Features

### **URL Validation:**
- ✅ Only allows `http://` and `https://` schemes
- ✅ Blocks dangerous schemes: `javascript:`, `data:`, `file:`
- ✅ Validates URL format and domain structure

### **File Security:**
- ✅ Safe filename generation (no directory traversal)
- ✅ Content-type validation for image attachments
- ✅ Base64 decoding with error handling

### **HTML Sanitization:**
- ✅ Maintains existing bleach security pipeline
- ✅ Processes clean image URLs (local paths) after CID replacement
- ✅ Preserves all existing security measures

## File Structure

```
uploads/newsletters/           # CID images stored here
├── msg_abc12345_d4f7a2c8_001_20241225_143022.jpg
├── msg_abc12345_e7b8c3d9_002_20241225_143023.png
└── ...

static/css/                   # Newsletter card styling
templates/dashboard.html      # Newsletter display

app/services/
├── newsletter_sanitizer.py  # Image processing logic
└── newsletter_ingest.py     # Processing pipeline
```

## Troubleshooting

### **Images Still Not Showing:**
1. Check Flask logs for image processing output
2. Verify `uploads/newsletters/` directory has image files
3. Check browser network tab for 404 errors on `/static/newsletters/` URLs
4. Ensure Flask route `/static/newsletters/<filename>` is working

### **SafeLinks Not Processing:**
1. Look for SafeLinks debug output in logs
2. Verify SafeLinks URLs match expected pattern
3. Check that `process_safelinks()` is called before sanitization

### **CID Images Not Processed:**
1. Check that newsletters have attachments with contentId
2. Verify CID references exist in HTML before processing
3. Look for debug output showing CID pattern matches

## Result
✅ **All newsletter images (both CID and SafeLinks) should now display correctly in the dashboard**
✅ **Comprehensive logging provides visibility into image processing**
✅ **Security measures maintained throughout the pipeline**
✅ **Processing pipeline optimized for maximum compatibility**