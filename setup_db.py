from app import create_app, db
from app.models import User
import os

app = create_app()

def setup():
    with app.app_context():
        # Path to SQLite DB file
        db_path = os.path.join(app.instance_path, 'catapp.db')
        
        print(f"Database path: {db_path}")
        
        # Option 1: Drop all tables using SQLAlchemy
        print("Dropping all tables...")
        db.drop_all()
        
        # Option 2: Force delete file if exists (cleaner for SQLite)
        # if os.path.exists(db_path):
        #     os.remove(db_path)
        #     print("Deleted old database file.")
            
        print("Creating all tables...")
        db.create_all()
        
        # Create Test User
        print("Creating test user...")
        if not User.query.filter_by(email='damian@dadlegloria.org').first():
            u = User(email='damian@dadlegloria.org')
            u.set_password('Dami.0316')
            db.session.add(u)
            db.session.commit()
            print("SUCCESS: Test user created.")
            print("Email: damian@dadlegloria.org")
            print("Password: Dami.0316")
        else:
            print("Test user already exists.")

        print("Creating second test user...")
        if not User.query.filter_by(email='giovanna@dadlegloria.org').first():
            u2 = User(email='giovanna@dadlegloria.org', name='Giovanna')
            u2.set_password('jn0316')
            db.session.add(u2)
            db.session.commit()
            print("SUCCESS: Second test user created.")
            print("Email: giovanna@dadlegloria.org")
            print("Password: jn0316")

if __name__ == '__main__':
    setup()
