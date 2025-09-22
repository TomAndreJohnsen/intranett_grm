import logging
import os
from flask import Flask
from flask_session import Session

logger = logging.getLogger(__name__)

def create_app(config_name='default'):
    """Create and configure Flask application"""
    logger.info(f"Creating app with config: {config_name}")
    app = Flask(__name__)

    # Load config from config.py
    from config import config
    app.config.from_object(config[config_name])
    logger.info(f"Configuration loaded: {config_name}")

    # Initialize extensions
    Session(app)
    logger.info("Session initialized")

    # Initialize database
    from .models.db import init_db, close_db
    with app.app_context():
        init_db()

    # Register close_db function for cleanup
    app.teardown_appcontext(close_db)
    logger.info("Database initialized")

    # Create upload directories
    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    for folder in ['salg', 'verksted', 'hr', 'it']:
        os.makedirs(os.path.join(upload_folder, folder), exist_ok=True)
    logger.info("Upload directories created")

    # Register blueprints
    from .routes import auth, dashboard, documents, calendar, tasks
    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(documents.bp)
    app.register_blueprint(calendar.bp)
    app.register_blueprint(tasks.bp)
    logger.info("Blueprints registered")

    # All main blueprints now implemented

    logger.info("App created successfully")
    return app