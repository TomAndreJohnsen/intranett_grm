#!/usr/bin/env python3
"""
Start script for the intranet application.
This avoids module conflicts with the app/ directory.
"""

from main import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)