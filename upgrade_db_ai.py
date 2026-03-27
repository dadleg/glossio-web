"""
Database migration script to add AI Translation tables.
"""
from app import create_app, db
from app.models import AITranslationJob, AISuggestion
import sqlite3
import os

def upgrade():
    app = create_app()
    with app.app_context():
        # Get database path
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
            # If relative path, make absolute
            if not os.path.isabs(db_path):
                db_path = os.path.join(app.root_path, '..', db_path)
                
            print(f"Migrating SQLite database at: {db_path}")
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create AITranslationJob table
            print("Creating AITranslationJob table...")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_translation_job (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status VARCHAR(20),
                total_segments INTEGER,
                completed_segments INTEGER,
                started_at DATETIME,
                completed_at DATETIME,
                avg_time_per_segment FLOAT,
                error_message TEXT,
                created_at DATETIME,
                FOREIGN KEY(project_id) REFERENCES project(id),
                FOREIGN KEY(user_id) REFERENCES user(id)
            )
            ''')
            
            # Create AISuggestion table
            print("Creating AISuggestion table...")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_suggestion (
                id INTEGER PRIMARY KEY,
                segment_id INTEGER NOT NULL,
                job_id INTEGER,
                suggested_text TEXT NOT NULL,
                status VARCHAR(20),
                translation_time_ms INTEGER,
                created_at DATETIME,
                reviewed_at DATETIME,
                FOREIGN KEY(segment_id) REFERENCES segment(id),
                FOREIGN KEY(job_id) REFERENCES ai_translation_job(id)
            )
            ''')
            
            conn.commit()
            conn.close()
            print("Migration complete!")
        else:
            print("Not using SQLite, using SQLAlchemy to create all tables (safe if exist)")
            db.create_all()
            print("Migration complete via SQLAlchemy!")

if __name__ == '__main__':
    upgrade()
