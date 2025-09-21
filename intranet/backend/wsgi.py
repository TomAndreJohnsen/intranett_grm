"""
WSGI entry point for production deployment.
Use this file with WSGI servers like Gunicorn or uWSGI.
"""
from app import app

if __name__ == "__main__":
    app.run()