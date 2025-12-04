import sqlite3
from app import create_app, db
from app.models import User, Segment, AuditLog
from sqlalchemy import text

def update_schema():
    app = create_app()
    with app.app_context():
        print("Checking database schema...")
        
        # 1. Check for 'name' column in 'user' table
        try:
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(user)")).fetchall()
                columns = [row[1] for row in result]
                
                if 'name' not in columns:
                    print("Adding 'name' column to 'user' table...")
                    conn.execute(text("ALTER TABLE user ADD COLUMN name VARCHAR(100)"))
                    print("Done.")
                else:
                    print("'name' column already exists in 'user' table.")
        except Exception as e:
            print(f"Error checking/updating 'user' table: {e}")

        # 2. Check for 'last_modified_by_id' and 'last_modified_at' in 'segment' table
        try:
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(segment)")).fetchall()
                columns = [row[1] for row in result]
                
                if 'last_modified_by_id' not in columns:
                    print("Adding 'last_modified_by_id' column to 'segment' table...")
                    conn.execute(text("ALTER TABLE segment ADD COLUMN last_modified_by_id INTEGER REFERENCES user(id)"))
                
                if 'last_modified_at' not in columns:
                    print("Adding 'last_modified_at' column to 'segment' table...")
                    conn.execute(text("ALTER TABLE segment ADD COLUMN last_modified_at DATETIME"))
                    
                print("Segment table check complete.")
        except Exception as e:
            print(f"Error checking/updating 'segment' table: {e}")

        # 3. Create 'audit_log' table if not exists
        # We can use db.create_all() but it only creates tables that don't exist.
        # It won't update existing tables (which is why we did steps 1 & 2 manually).
        print("Creating missing tables (e.g. audit_log)...")
        db.create_all()
        print("Done.")

        print("\nSchema update complete. Your data should be safe.")

if __name__ == '__main__':
    update_schema()
