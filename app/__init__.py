from flask import Flask
from app.config import Config
from app.extensions import db, login, socketio
from app.models import User

login.login_view = 'auth.login'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login.init_app(app)
    socketio.init_app(app, async_mode='eventlet')
    
    from app.extensions import init_firebase
    init_firebase(app)
    
    from app import events # Register events

    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    with app.app_context():
        # db.create_all()
        pass
    return app

@login.user_loader
def load_user(id):
    return User.query.get(int(id))
