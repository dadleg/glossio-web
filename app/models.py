from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app.extensions import db


# Association table for Project assignments
project_assignments = db.Table('project_assignments',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True),
    db.Column('role', db.String(20), default='reviewer') # e.g., 'reviewer', 'editor'
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100)) # Display name
    password_hash = db.Column(db.String(128))
    
    # Projects owned by user
    owned_projects = db.relationship('Project', backref='owner', lazy='dynamic')
    
    # Projects assigned to user
    assigned_projects = db.relationship('Project', secondary=project_assignments, 
                                      backref=db.backref('assigned_users', lazy='dynamic'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id')) # Owner
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
    
    last_modified_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    last_modified_at = db.Column(db.DateTime)
    
    locked_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)
    
    last_modified_by = db.relationship('User', foreign_keys=[last_modified_by_id])
    locked_by = db.relationship('User', foreign_keys=[locked_by_user_id])
    
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

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    segment_id = db.Column(db.Integer, db.ForeignKey('segment.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False) # 'edit', 'merge', 'join', 'leave'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text) # JSON or text description
    
    user = db.relationship('User', backref='audit_logs')
    project = db.relationship('Project', backref='audit_logs')
