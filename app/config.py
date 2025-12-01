import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    # Use SQLite by default, but allow overriding with DATABASE_URL for PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///catapp.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    
    # App specific config
    # Default to None to ensure it's provided via ENV for security
    DEEPL_API_KEY = os.environ.get('DEEPL_API_KEY')
