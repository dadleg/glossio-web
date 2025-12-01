from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    projects = db.relationship('Project', backref='owner', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id')) # Make nullable for backward compat if needed, but ideally enforced
    filename = db.Column(db.String(255), nullable=False)
    source_lang = db.Column(db.String(10), default='EN')
    target_lang = db.Column(db.String(10), default='ES')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to paragraphs
    paragraphs = db.relationship('Paragraph', backref='project', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Project {self.filename}>'

class Paragraph(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    p_idx = db.Column(db.Integer, nullable=False)
    original_text = db.Column(db.Text) # The full paragraph text, for context
    
    # Relationship to segments
    segments = db.relationship('Segment', backref='paragraph', lazy=True, cascade="all, delete-orphan")

class Segment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paragraph_id = db.Column(db.Integer, db.ForeignKey('paragraph.id'), nullable=False)
    s_idx = db.Column(db.Integer, nullable=False)
    source_text = db.Column(db.Text, nullable=False)
    target_text = db.Column(db.Text, default="")
    note = db.Column(db.Text, default="")
    
    # To facilitate sorting within a paragraph
    # Note: s_idx might need to be adjusted when merging.

class TranslationMemory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    source_text = db.Column(db.Text, nullable=False)
    target_text = db.Column(db.Text, nullable=False)
    lang_pair = db.Column(db.String(20)) # e.g. "EN-ES"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Glossary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    source_term = db.Column(db.String(255), nullable=False)
    target_term = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    lang_pair = db.Column(db.String(20)) # e.g. "EN-ES"
