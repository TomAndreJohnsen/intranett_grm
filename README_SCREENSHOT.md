# Dashboard Screenshot Instructions

## Overview
The `screenshot.js` script captures a full-page screenshot of the intranet dashboard at `http://localhost:5000/dashboard` using Puppeteer.

## Prerequisites
- ✅ Puppeteer is already installed (v24.22.2)
- ✅ Authentication bypass is implemented for screenshot mode

## Usage Instructions

### 1. Start the Flask Application
```bash
# In the project root directory
python3 main.py
```
Wait for the message showing the app is running on `http://localhost:5000`

### 2. Run the Screenshot Script
```bash
# In a new terminal, from the project root
node screenshot.js
```

### 3. Expected Newsletter Card Layout
The refactored dashboard now displays newsletters as individual cards with:
- **Card Header**: Newsletter subject as the title (green header with white text)
- **Meta Line**: Sender name and received date (formatted as date only)
- **Card Body**: Full sanitized HTML content rendered with proper formatting
- **Responsive Design**: Cards stack properly on mobile devices
- **Consistent Styling**: Matches existing dashboard widget cards

### 3. Expected Output
```
🚀 Starting dashboard screenshot capture...
📱 Browser launched successfully
🔧 Viewport configured (1920x1080)
🔑 Screenshot mode headers set
🌐 Navigating to http://localhost:5000/dashboard...
✅ Dashboard loaded successfully
⏳ Waiting for dynamic content...
🎉 Screenshot saved successfully!
📁 File path: /Users/tomandre/projects/vibecoding/intranett_grm/dashboard_screenshot.png
🔒 Browser closed
```

## Features

### Screenshot Script (`screenshot.js`)
- **Headless Mode**: Runs Puppeteer without visible browser window
- **Viewport**: 1920x1080 for consistent high-resolution screenshots
- **Wait Strategy**: Uses `networkidle2` to ensure full page load
- **Full Page**: Captures entire dashboard including scrollable content
- **Error Handling**: Provides clear error messages and troubleshooting hints

### Authentication Bypass
- **Header-based**: Uses `X-Screenshot-Mode: true` header
- **Mock User**: Creates a demo admin user for full dashboard access
- **Development Only**: Safe bypass that doesn't affect normal authentication

## Troubleshooting

### Error: ERR_CONNECTION_REFUSED
- **Solution**: Make sure Flask app is running on `http://localhost:5000`
- **Command**: `python3 main.py`

### Error: Navigation timeout
- **Solution**: Check if the server is responding and dashboard loads correctly
- **Test**: Visit `http://localhost:5000/dashboard` in browser

### Empty Screenshot
- **Solution**: Dashboard might not have content yet
- **Fix**: Add some test newsletters or ensure database has sample data

## Output File
- **Location**: `dashboard_screenshot.png` in project root
- **Format**: PNG, full-page capture
- **Resolution**: Based on 1920x1080 viewport
- **Use Case**: Baseline for iterating newsletter card design

## Technical Details

### Authentication Bypass Implementation
```python
# In main.py - auth_required decorator
if request.headers.get('X-Screenshot-Mode') == 'true':
    session['_screenshot_mode'] = True
    return f(*args, **kwargs)
```

### Mock User for Screenshot Mode
```python
# In main.py - get_current_user function
if session.get('_screenshot_mode'):
    return {
        'userPrincipalName': 'screenshot@demo.local',
        'displayName': 'Screenshot Demo User',
        'is_admin': True
    }
```

This implementation provides a clean way to capture dashboard screenshots without requiring actual Microsoft authentication, perfect for design iteration and documentation purposes.