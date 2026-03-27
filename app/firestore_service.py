"""
Firestore Service for Glossio
Handles heavy lifting operations: DOCX parsing/export with Firestore as source of truth
"""

from firebase_admin import firestore, storage
from datetime import datetime
import uuid
import os


def get_firestore_client():
    """Get Firestore client instance."""
    return firestore.client()


def get_storage_bucket():
    """Get Firebase Storage bucket."""
    return storage.bucket()


# ==========================================
# PROJECT OPERATIONS
# ==========================================

def create_project_in_firestore(owner_uid, filename, source_lang='EN', target_lang='ES'):
    """Create a new project document in Firestore."""
    db = get_firestore_client()
    
    project_id = str(uuid.uuid4())
    project_ref = db.collection('projects').document(project_id)
    
    project_ref.set({
        'owner_id': owner_uid,
        'filename': filename,
        'source_lang': source_lang,
        'target_lang': target_lang,
        'created_at': firestore.SERVER_TIMESTAMP,
        'status': 'processing'
    })
    
    return project_id


def update_project_status(project_id, status):
    """Update project status."""
    db = get_firestore_client()
    db.collection('projects').document(project_id).update({
        'status': status
    })


# ==========================================
# SEGMENT OPERATIONS
# ==========================================

def write_segments_to_firestore(project_id, paragraphs_data):
    """
    Write parsed segments to Firestore.
    
    paragraphs_data: [
        {
            'p_idx': 0,
            'original_text': 'Full paragraph...',
            'segments': [
                {'s_idx': 0, 'source_text': 'Sentence 1.'},
                {'s_idx': 1, 'source_text': 'Sentence 2.'},
            ]
        },
        ...
    ]
    """
    db = get_firestore_client()
    batch = db.batch()
    
    segment_count = 0
    
    for para in paragraphs_data:
        p_idx = para['p_idx']
        
        for seg in para['segments']:
            # Create unique segment ID
            segment_id = f"p{p_idx}_s{seg['s_idx']}"
            seg_ref = db.collection('projects').document(project_id).collection('segments').document(segment_id)
            
            batch.set(seg_ref, {
                'paragraph_idx': p_idx,
                'segment_idx': seg['s_idx'],
                'paragraph_text': para['original_text'],
                'source_text': seg['source_text'],
                'target_text': '',
                'note': '',
                'locked_by': None,
                'locked_by_name': None,
                'locked_at': None,
                'last_modified_by': None,
                'last_modified_by_name': None,
                'last_modified_at': None
            })
            
            segment_count += 1
            
            # Firestore batch limit is 500
            if segment_count % 400 == 0:
                batch.commit()
                batch = db.batch()
    
    # Commit remaining
    batch.commit()
    
    return segment_count


def read_all_segments(project_id):
    """
    Read all segments from a project, ordered by paragraph and segment index.
    Returns list of segment dicts.
    """
    db = get_firestore_client()
    
    segments_ref = db.collection('projects').document(project_id).collection('segments')
    query = segments_ref.order_by('paragraph_idx').order_by('segment_idx')
    
    segments = []
    for doc in query.stream():
        data = doc.to_dict()
        data['id'] = doc.id
        segments.append(data)
    
    return segments


def get_segments_by_paragraph(project_id):
    """
    Get segments grouped by paragraph for DOCX reassembly.
    Returns dict: {p_idx: [segments]}
    """
    segments = read_all_segments(project_id)
    
    paragraphs = {}
    for seg in segments:
        p_idx = seg['paragraph_idx']
        if p_idx not in paragraphs:
            paragraphs[p_idx] = []
        paragraphs[p_idx].append(seg)
    
    return paragraphs


# ==========================================
# FILE STORAGE
# ==========================================

def upload_docx_to_storage(project_id, file_path, filename):
    """Upload original DOCX to Firebase Storage."""
    bucket = get_storage_bucket()
    blob = bucket.blob(f"projects/{project_id}/original/{filename}")
    blob.upload_from_filename(file_path)
    
    return blob.public_url


def upload_final_docx(project_id, file_path, filename):
    """Upload final/exported DOCX to Firebase Storage."""
    bucket = get_storage_bucket()
    blob = bucket.blob(f"projects/{project_id}/exports/{filename}")
    blob.upload_from_filename(file_path)
    
    # Make it downloadable
    blob.make_public()
    
    return blob.public_url


def download_original_docx(project_id, dest_path):
    """Download original DOCX from Storage."""
    db = get_firestore_client()
    project = db.collection('projects').document(project_id).get()
    
    if not project.exists:
        return None
    
    filename = project.to_dict()['filename']
    
    bucket = get_storage_bucket()
    blob = bucket.blob(f"projects/{project_id}/original/{filename}")
    blob.download_to_filename(dest_path)
    
    return dest_path


# ==========================================
# COLLABORATOR MANAGEMENT
# ==========================================

def add_collaborator(project_id, user_uid, role='editor'):
    """Add a collaborator to a project."""
    db = get_firestore_client()
    
    collab_ref = db.collection('projects').document(project_id).collection('collaborators').document(user_uid)
    collab_ref.set({
        'role': role,
        'added_at': firestore.SERVER_TIMESTAMP
    })


def remove_collaborator(project_id, user_uid):
    """Remove a collaborator from a project."""
    db = get_firestore_client()
    
    db.collection('projects').document(project_id).collection('collaborators').document(user_uid).delete()


def get_collaborators(project_id):
    """Get all collaborators for a project."""
    db = get_firestore_client()
    
    collabs = []
    for doc in db.collection('projects').document(project_id).collection('collaborators').stream():
        data = doc.to_dict()
        data['uid'] = doc.id
        collabs.append(data)
    
    return collabs


# ==========================================
# CLEANUP
# ==========================================

def delete_project(project_id):
    """Delete a project and all its data from Firestore and Storage."""
    db = get_firestore_client()
    
    # Delete segments
    segments_ref = db.collection('projects').document(project_id).collection('segments')
    for doc in segments_ref.stream():
        doc.reference.delete()
    
    # Delete collaborators
    collabs_ref = db.collection('projects').document(project_id).collection('collaborators')
    for doc in collabs_ref.stream():
        doc.reference.delete()
    
    # Delete presence
    presence_ref = db.collection('projects').document(project_id).collection('presence')
    for doc in presence_ref.stream():
        doc.reference.delete()
    
    # Delete project doc
    db.collection('projects').document(project_id).delete()
    
    # Delete from Storage
    try:
        bucket = get_storage_bucket()
        blobs = bucket.list_blobs(prefix=f"projects/{project_id}/")
        for blob in blobs:
            blob.delete()
    except Exception as e:
        print(f"Error deleting storage: {e}")
