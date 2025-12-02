from flask import Flask
from flask_login import LoginManager
from app.config import Config
from app.models import db, User

login = LoginManager()
login.login_view = 'auth.login'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login.init_app(app)

    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    with app.app_context():
#        db.create_all()
        pass
    return app

@login.user_loader
def load_user(id):
    return User.query.get(int(id))
