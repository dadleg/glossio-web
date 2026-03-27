from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import firebase_admin
from firebase_admin import credentials
import os
import sys

db = SQLAlchemy()
login = LoginManager()

# Determine async mode - use threading for PyInstaller bundles (more compatible)
# eventlet can cause issues in bundled environments
def get_async_mode():
    # Check if running as PyInstaller bundle - always use threading
    if getattr(sys, 'frozen', False):
        print("PyInstaller bundle detected - using threading mode")
        return 'threading'
    
    # Try eventlet first, but verify it actually works
    try:
        import eventlet
        import eventlet.wsgi
        # Try to verify eventlet is functional
        eventlet.monkey_patch(socket=False)  # Light test
        print("Eventlet available - using eventlet mode")
        return 'eventlet'
    except Exception as e:
        print(f"Eventlet not available ({e}) - using threading mode")
        return 'threading'

# Create socketio without async_mode - will be set in init_app
socketio = SocketIO(cors_allowed_origins="*")

def init_firebase(app):
    """Initialize Firebase Admin SDK with Firestore and Storage.
    
    Skipped entirely when LOCAL_MODE=true for offline-only usage.
    """
    # Check for local-only mode
    if os.environ.get('LOCAL_MODE', '').lower() == 'true':
        print("LOCAL_MODE enabled - Firebase initialization skipped")
        return
    
    # Check if already initialized
    if firebase_admin._apps:
        return
    
    cred_path = app.config.get('FIREBASE_CREDENTIALS_PATH')
    storage_bucket = app.config.get('FIREBASE_STORAGE_BUCKET')
    
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        
        # Initialize with storage bucket if available
        options = {}
        if storage_bucket:
            options['storageBucket'] = storage_bucket
        
        firebase_admin.initialize_app(cred, options)
        print(f"Firebase initialized with Firestore and Storage: {storage_bucket}")
    else:
        print(f"Warning: FIREBASE_CREDENTIALS_PATH not set or file not found at: {cred_path}. CWD is {os.getcwd()}")
