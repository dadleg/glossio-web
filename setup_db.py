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
        if not User.query.filter_by(email='test@example.com').first():
            u = User(email='test@example.com')
            u.set_password('password')
            db.session.add(u)
            db.session.commit()
            print("SUCCESS: Test user created.")
            print("Email: test@example.com")
            print("Password: password")
        else:
            print("Test user already exists.")

if __name__ == '__main__':
    setup()
