#!/usr/bin/env python3
"""
Import translation progress from exported CSV into local Glossio database.

This script:
1. Creates/gets the offline user
2. Parses UM.docx into the local SQLite database
3. Matches translations from CSV by source_text
4. Updates segments with recovered translations

Usage:
    cd /home/dadleg/glossio_web2
    python scripts/import_translations.py

Options:
    --dry-run    Show match statistics without writing to database
"""

import csv
import os
import sys
import argparse
import re
from pathlib import Path
from datetime import datetime

# Set environment before any imports
os.environ['LOCAL_MODE'] = 'true'

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Flask-SQLAlchemy components directly (avoiding eventlet)
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from docx import Document

# Create minimal Flask app for database access (no socketio/eventlet)
app = Flask(__name__, 
            template_folder=str(Path(__file__).parent.parent / 'app' / 'templates'),
            static_folder=str(Path(__file__).parent.parent / 'app' / 'static'))

# Configure database - use ~/.glossio for consistent location
data_dir = Path.home() / '.glossio'
data_dir.mkdir(exist_ok=True)
db_path = data_dir / 'catapp.db'

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'import-script-key'

db = SQLAlchemy(app)

# Define models inline (matching app/models.py)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    firebase_uid = db.Column(db.String(128), unique=True, nullable=True)
    name = db.Column(db.String(100))
    password_hash = db.Column(db.String(128))

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    filename = db.Column(db.String(255), nullable=False)
    source_lang = db.Column(db.String(10), default='EN')
    target_lang = db.Column(db.String(10), default='ES')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paragraphs = db.relationship('Paragraph', backref='project', lazy=True, cascade="all, delete-orphan")

class Paragraph(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    p_idx = db.Column(db.Integer, nullable=False)
    original_text = db.Column(db.Text)
    segments = db.relationship('Segment', backref='paragraph', lazy=True, cascade="all, delete-orphan")

class Segment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paragraph_id = db.Column(db.Integer, db.ForeignKey('paragraph.id'), nullable=False)
    s_idx = db.Column(db.Integer, nullable=False)
    source_text = db.Column(db.Text, nullable=False)
    target_text = db.Column(db.Text, default="")
    note = db.Column(db.Text, default="")
    last_modified_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    last_modified_at = db.Column(db.DateTime)
    # These were missing - required by the full app
    locked_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)

# Configuration
CSV_PATH = Path(__file__).parent.parent / 'translations.csv'
DOCX_PATH = Path('/home/dadleg/UM.docx')
OFFLINE_EMAIL = 'offline@local.glossio'


def parse_docx_simple(filepath, project_id):
    """Parse DOCX file into paragraphs and segments (simplified, no spaCy)."""
    doc = Document(filepath)
    
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        
        para = Paragraph(project_id=project_id, p_idx=i, original_text=p.text)
        db.session.add(para)
        db.session.flush()
        
        if not text:
            continue
        
        # Simple sentence splitting (period followed by space and capital letter)
        # This is a fallback - the actual app uses spaCy
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            sentences = [text]
        
        for j, s_text in enumerate(sentences):
            seg = Segment(paragraph_id=para.id, s_idx=j, source_text=s_text)
            db.session.add(seg)
    
    db.session.commit()


def get_or_create_offline_user():
    """Get or create the offline user."""
    user = User.query.filter_by(email=OFFLINE_EMAIL).first()
    if not user:
        user = User(
            email=OFFLINE_EMAIL,
            name='Offline User',
            firebase_uid=None
        )
        db.session.add(user)
        db.session.commit()
        print(f"Created offline user: {OFFLINE_EMAIL}")
    else:
        print(f"Using existing offline user: {OFFLINE_EMAIL}")
    return user


def load_csv_translations(csv_path):
    """Load translations from CSV, keyed by normalized source_text."""
    translations = {}
    duplicates = 0
    with_target = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = row['source_text'].strip()
            target = row['target_text'].strip()
            note = row.get('note', '').strip()
            
            if target:  # Only store if there's a translation
                with_target += 1
                if source in translations:
                    duplicates += 1
                    # Keep the one with more content
                    existing = translations[source]
                    if len(target) > len(existing['target']):
                        translations[source] = {'target': target, 'note': note}
                else:
                    translations[source] = {'target': target, 'note': note}
    
    print(f"Loaded {with_target} segments with translations from CSV")
    print(f"  - Unique sources: {len(translations)}")
    print(f"  - Duplicates resolved: {duplicates}")
    return translations


def import_translations(dry_run=False):
    """Main import function."""
    with app.app_context():
        # Ensure tables exist
        db.create_all()
        
        # 1. Get or create offline user
        user = get_or_create_offline_user()
        
        # 2. Check if project already exists
        existing_project = Project.query.filter_by(
            filename='UM.docx',
            user_id=user.id
        ).first()
        
        if existing_project:
            print(f"Project UM.docx already exists (ID: {existing_project.id})")
            project = existing_project
            segment_count = Segment.query.join(Paragraph).filter(
                Paragraph.project_id == project.id
            ).count()
            print(f"  - Contains {segment_count} segments")
        else:
            # 3. Create new project
            if not DOCX_PATH.exists():
                print(f"ERROR: Document not found: {DOCX_PATH}")
                return
            
            project = Project(
                user_id=user.id,
                filename='UM.docx',
                source_lang='EN',
                target_lang='ES'
            )
            db.session.add(project)
            db.session.commit()
            print(f"Created project: UM.docx (ID: {project.id})")
            
            # 4. Parse DOCX
            print(f"Parsing document: {DOCX_PATH}")
            parse_docx_simple(str(DOCX_PATH), project.id)
            
            segment_count = Segment.query.join(Paragraph).filter(
                Paragraph.project_id == project.id
            ).count()
            print(f"  - Created {segment_count} segments")
        
        # 5. Load CSV translations
        if not CSV_PATH.exists():
            print(f"ERROR: CSV not found: {CSV_PATH}")
            return
        
        translations = load_csv_translations(CSV_PATH)
        
        # 6. Match and update segments
        segments = Segment.query.join(Paragraph).filter(
            Paragraph.project_id == project.id
        ).all()
        
        matched = 0
        already_translated = 0
        
        for seg in segments:
            source = seg.source_text.strip()
            
            if source in translations:
                trans = translations[source]
                
                if seg.target_text and seg.target_text.strip():
                    already_translated += 1
                    continue
                
                matched += 1
                if not dry_run:
                    seg.target_text = trans['target']
                    if trans['note']:
                        seg.note = trans['note']
        
        not_found = len(segments) - matched - already_translated
        
        if not dry_run:
            db.session.commit()
            print(f"\n✅ Import complete!")
        else:
            print(f"\n🔍 DRY RUN - No changes made")
        
        print(f"\nResults:")
        print(f"  - Total segments in project: {len(segments)}")
        print(f"  - Matched & imported: {matched}")
        print(f"  - Already had translations: {already_translated}")
        print(f"  - No match in CSV: {not_found}")
        
        if matched > 0:
            pct = (matched / len(segments)) * 100
            print(f"\n  Translation coverage: {pct:.1f}%")


def main():
    parser = argparse.ArgumentParser(description='Import translations from CSV')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show statistics without writing to database')
    args = parser.parse_args()
    
    print("=" * 60)
    print("  Glossio Translation Import Tool")
    print("=" * 60)
    print()
    
    import_translations(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
