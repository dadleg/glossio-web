from flask import request
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio, db
from app.models import AuditLog, Segment, User, Project
from datetime import datetime
import json

# Simple in-memory storage for active users: {project_id: {user_id: user_info}}
project_users = {}

@socketio.on('join')
def on_join(data):
    project_id = data['project_id']
    room = f"project_{project_id}"
    join_room(room)
    
    # Broadcast user joined
    emit('user_joined', {
        'user_id': current_user.id,
        'name': current_user.name or current_user.email.split('@')[0],
        'email': current_user.email
    }, room=room)
    
    # Log action
    log = AuditLog(
        project_id=project_id,
        user_id=current_user.id,
        action='join',
        details=f"User {current_user.email} joined the session."
    )
    db.session.add(log)
    db.session.commit()
    
    # Update active users list
    if project_id not in project_users:
        project_users[project_id] = {}
    
    user_info = {
        'user_id': current_user.id,
        'name': current_user.name or current_user.email.split('@')[0],
        'email': current_user.email
    }
    project_users[project_id][current_user.id] = user_info
    
    # Send list of current users to the joining user
    emit('current_users', list(project_users[project_id].values()))

@socketio.on('leave')
def on_leave(data):
    project_id = data['project_id']
    room = f"project_{project_id}"
    leave_room(room)
    room = f"project_{project_id}"
    leave_room(room)
    
    # Remove from active list
    if project_id in project_users and current_user.id in project_users[project_id]:
        del project_users[project_id][current_user.id]
        
    emit('user_left', {'user_id': current_user.id}, room=room)

@socketio.on('update_segment')
def on_update_segment(data):
    project_id = data['project_id']
    segment_id = data['segment_id']
    target_text = data['target_text']
    note = data.get('note', '')
    
    room = f"project_{project_id}"
    
    # Save to DB
    segment = Segment.query.get(segment_id)
    if segment:
        segment.target_text = target_text
        segment.note = note
        # Ensure last_modified is updated here too, to match REST API
        segment.last_modified_by_id = current_user.id
        segment.last_modified_at = datetime.utcnow()
        db.session.commit()
        
        # Log
        log = AuditLog(
            project_id=project_id,
            user_id=current_user.id,
            segment_id=segment_id,
            action='edit',
            details=f"Updated segment {segment.s_idx}"
        )
        db.session.add(log)
        db.session.commit()
        
        # Broadcast to others (include user_id so sender can ignore if needed, but usually we want to confirm)
        emit('segment_updated', {
            'segment_id': segment_id,
            'target_text': target_text,
            'note': note,
            'user_id': current_user.id,
            'user_name': current_user.name or current_user.email,
            'last_modified_by_name': current_user.name or current_user.email,
            'last_modified_at': datetime.utcnow().isoformat()
        }, room=room, include_self=False)

@socketio.on('typing')
def on_typing(data):
    project_id = data['project_id']
    room = f"project_{project_id}"
    emit('user_typing', {
        'user_id': current_user.id,
        'name': current_user.name or current_user.email,
        'segment_id': data.get('segment_id')
    }, room=room, include_self=False)
