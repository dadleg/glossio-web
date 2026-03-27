import os
import sys
from dotenv import load_dotenv

# Determine the base path for bundled vs development
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    BASE_PATH = sys._MEIPASS
else:
    # Running in development
    BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_PATH, '.env'))


def _get_firebase_credentials_path():
    """Get Firebase credentials path - check env var, bundle path, then cwd."""
    # Check environment variable first
    env_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
    if env_path and os.path.exists(env_path):
        return env_path
    
    # Check in bundle/base path
    bundle_path = os.path.join(BASE_PATH, 'serviceAccountKey.json')
    if os.path.exists(bundle_path):
        return bundle_path
    
    # Fallback to cwd
    return os.path.join(os.getcwd(), 'serviceAccountKey.json')


def _get_database_path():
    """Get database path - uses ~/.glossio for consistent location."""
    # Check environment variable first (for PostgreSQL in production)
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return db_url
    
    # Use ~/.glossio/catapp.db for consistent path across bundled app and scripts
    data_dir = os.path.join(os.path.expanduser('~'), '.glossio')
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, 'catapp.db')
    return f'sqlite:///{db_path}'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    # Use SQLite in ~/.glossio by default, but allow overriding with DATABASE_URL for PostgreSQL
    SQLALCHEMY_DATABASE_URI = _get_database_path()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.expanduser('~'), '.glossio', 'uploads')
    
    # Feature Flags
    ENABLE_AI_FEATURES = False
    
    # App specific config
    DEEPL_API_KEY = os.environ.get('DEEPL_API_KEY')

    # Firebase Config - computed at import time
    FIREBASE_CREDENTIALS_PATH = _get_firebase_credentials_path()

    # Firebase Client Config
    FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY')
    FIREBASE_AUTH_DOMAIN = os.environ.get('FIREBASE_AUTH_DOMAIN')
    FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID')
    FIREBASE_STORAGE_BUCKET = os.environ.get('FIREBASE_STORAGE_BUCKET')
    FIREBASE_MESSAGING_SENDER_ID = os.environ.get('FIREBASE_MESSAGING_SENDER_ID')
    FIREBASE_APP_ID = os.environ.get('FIREBASE_APP_ID')
    FIREBASE_MEASUREMENT_ID = os.environ.get('FIREBASE_MEASUREMENT_ID')
