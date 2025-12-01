from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()
    # Check if test user exists
    if not User.query.filter_by(email='test@example.com').first():
        u = User(email='test@example.com')
        u.set_password('password')
        db.session.add(u)
        db.session.commit()
        print("Test user created: test@example.com / password")
    else:
        print("Test user already exists.")
