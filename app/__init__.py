import os
from flask import Flask
from app.config import Config
from app.extensions import db, login, socketio, get_async_mode
from app.models import User

login.login_view = 'auth.login'
login.login_message = '' # Remove "Please log in to access this page" message

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    print(f"DEBUG: SQLALCHEMY_DATABASE_URI = {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    print(f"DEBUG: Current Working Directory = {os.getcwd()}")


    db.init_app(app)
    login.init_app(app)
    socketio.init_app(app, async_mode=get_async_mode())
    
    from app.extensions import init_firebase
    init_firebase(app)
    
    from app import events # Register events

    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    with app.app_context():
        print(f"DEBUG: Initializing database at {app.config['SQLALCHEMY_DATABASE_URI']}")
        try:
            db.create_all()  # Create tables if they don't exist
            print("DEBUG: db.create_all() call completed.")
            
            # Verify table existence
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"DEBUG: Existing tables: {tables}")
            
            # Verify User table access
            user_count = User.query.count()
            print(f"DEBUG: User table count: {user_count}")
            
        except Exception as e:
            print(f"DEBUG: Database initialization error: {e}")
            import traceback
            traceback.print_exc()
            
    @app.context_processor
    def inject_config():
        return dict(ENABLE_AI_FEATURES=app.config.get('ENABLE_AI_FEATURES', False))

    return app

@login.user_loader
def load_user(id):
    return User.query.get(int(id))
