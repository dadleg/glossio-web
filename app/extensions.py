from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import firebase_admin
from firebase_admin import credentials
import os

db = SQLAlchemy()
login = LoginManager()
socketio = SocketIO(cors_allowed_origins="*")

def init_firebase(app):
    cred_path = app.config.get('FIREBASE_CREDENTIALS_PATH')
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print(f"Firebase initialized successfully with credentials from: {cred_path}")
    else:
        print(f"Warning: FIREBASE_CREDENTIALS_PATH not set or file not found at: {cred_path}. CWD is {os.getcwd()}")
