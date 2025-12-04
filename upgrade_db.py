from app import create_app, db
import os

app = create_app()

def upgrade():
    with app.app_context():
        print("Checking for new tables...")
        # create_all() only creates tables that don't exist
        db.create_all()
        print("Database schema updated. Missing tables created.")

if __name__ == '__main__':
    upgrade()
