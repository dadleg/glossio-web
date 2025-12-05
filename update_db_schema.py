from app import create_app, db
from sqlalchemy import text, inspect

def update_schema():
    app = create_app()
    with app.app_context():
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        print(f"Checking database schema for: {db_uri.split('@')[-1] if '@' in db_uri else db_uri}...")
        inspector = inspect(db.engine)
        
        # 1. Check for 'name' and 'firebase_uid' columns in 'user' table
        try:
            columns = [c['name'] for c in inspector.get_columns('user')]
            
            with db.engine.connect() as conn:
                if 'name' not in columns:
                    print("Adding 'name' column to 'user' table...")
                    conn.execute(text("ALTER TABLE \"user\" ADD COLUMN name VARCHAR(100)"))
                    conn.commit()
                
                if 'firebase_uid' not in columns:
                    print("Adding 'firebase_uid' column to 'user' table...")
                    conn.execute(text("ALTER TABLE \"user\" ADD COLUMN firebase_uid VARCHAR(128)"))
                    conn.commit()
                    
            print("User table check complete.")
        except Exception as e:
            print(f"Error checking/updating 'user' table: {e}")

        # 2. Check for 'last_modified_by_id' and 'last_modified_at' in 'segment' table
        try:
            columns = [c['name'] for c in inspector.get_columns('segment')]
            
            with db.engine.connect() as conn:
                if 'last_modified_by_id' not in columns:
                    print("Adding 'last_modified_by_id' column to 'segment' table...")
                    conn.execute(text("ALTER TABLE segment ADD COLUMN last_modified_by_id INTEGER REFERENCES \"user\"(id)"))
                    conn.commit()
                
                if 'last_modified_at' not in columns:
                    print("Adding 'last_modified_at' column to 'segment' table...")
                    conn.execute(text("ALTER TABLE segment ADD COLUMN last_modified_at TIMESTAMP"))
                    conn.commit()

                if 'locked_by_user_id' not in columns:
                    print("Adding 'locked_by_user_id' column to 'segment' table...")
                    conn.execute(text("ALTER TABLE segment ADD COLUMN locked_by_user_id INTEGER REFERENCES \"user\"(id)"))
                    conn.commit()

                if 'locked_at' not in columns:
                    print("Adding 'locked_at' column to 'segment' table...")
                    conn.execute(text("ALTER TABLE segment ADD COLUMN locked_at TIMESTAMP"))
                    conn.commit()
                    
            print("Segment table check complete.")
        except Exception as e:
            print(f"Error checking/updating 'segment' table: {e}")

        # 3. Create 'audit_log' table if not exists
        print("Creating missing tables (e.g. audit_log)...")
        db.create_all()
        print("Done.")

        print("\nSchema update complete. Your data should be safe.")

if __name__ == '__main__':
    update_schema()
