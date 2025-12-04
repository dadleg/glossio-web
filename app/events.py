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

@socketio.on('disconnect')
def on_disconnect():
    # Find which project/room the user was in
    # Since socketio doesn't easily give us the room on disconnect without tracking,
    # we iterate our project_users tracker.
    user_id = current_user.id
    
    for pid, users in project_users.items():
        if user_id in users:
            del users[user_id]
            room = f"project_{pid}"
            emit('user_left', {'user_id': user_id}, room=room)
            
            # Unlock all segments locked by this user
            try:
                # We need an app context if not already present, but socketio handlers usually have one.
                # However, disconnect might be tricky.
                locked_segments = Segment.query.filter_by(locked_by_user_id=user_id).all()
                for seg in locked_segments:
                    seg.locked_by_user_id = None
                    seg.locked_at = None
                    emit('segment_unlocked', {'segment_id': seg.id}, room=room)
                db.session.commit()
            except Exception as e:
                print(f"Error unlocking segments on disconnect: {e}")
            
            break

@socketio.on('leave')
def on_leave(data):
    project_id = data['project_id']
    room = f"project_{project_id}"
    leave_room(room)
    
    # Remove from active list
    if project_id in project_users and current_user.id in project_users[project_id]:
        del project_users[project_id][current_user.id]
        
    emit('user_left', {'user_id': current_user.id}, room=room)
    
    # Unlock segments
    locked_segments = Segment.query.join(Paragraph).filter(Paragraph.project_id == project_id, Segment.locked_by_user_id == current_user.id).all()
    for seg in locked_segments:
        seg.locked_by_user_id = None
        seg.locked_at = None
        emit('segment_unlocked', {'segment_id': seg.id}, room=room)
    db.session.commit()

@socketio.on('update_segment')
def on_update_segment(data):
    print(f"DEBUG: on_update_segment {data}")
    project_id = data['project_id']
    segment_id = data['segment_id']
    target_text = data['target_text']
    note = data.get('note', '')
    
    room = f"project_{project_id}"
    
    # Broadcast update
    emit('segment_updated', {
        'segment_id': segment_id,
        'target_text': target_text,
        'note': note,
        'user_id': current_user.id,
        'user_name': current_user.name or current_user.email,
        'last_modified_by_name': current_user.name or current_user.email,
        'last_modified_at': datetime.utcnow().isoformat()
    }, room=room, include_self=False)
    print(f"DEBUG: Broadcasted to {room}")

@socketio.on('typing')
def on_typing(data):
    project_id = data['project_id']
    room = f"project_{project_id}"
    emit('user_typing', {
        'user_id': current_user.id,
        'name': current_user.name or current_user.email,
        'segment_id': data.get('segment_id')
    }, room=room, include_self=False)

@socketio.on('lock_segment')
def on_lock_segment(data):
    segment_id = data['segment_id']
    project_id = data['project_id']
    room = f"project_{project_id}"
    
    seg = Segment.query.get(segment_id)
    if seg:
        current_user_id = int(current_user.id)
        # Check if already locked by someone else
        if seg.locked_by_user_id and seg.locked_by_user_id != current_user_id:
            # Already locked, notify requester (optional, or just ignore)
            return
            
        # Lock it
        seg.locked_by_user_id = current_user_id
        seg.locked_at = datetime.utcnow()
        db.session.commit()
        
        emit('segment_locked', {
            'segment_id': segment_id,
            'user_id': current_user_id,
            'user_name': current_user.name or current_user.email
        }, room=room, include_self=False)

@socketio.on('unlock_segment')
def on_unlock_segment(data):
    segment_id = data['segment_id']
    project_id = data['project_id']
    room = f"project_{project_id}"
    
    seg = Segment.query.get(segment_id)
    if seg and seg.locked_by_user_id == int(current_user.id):
        seg.locked_by_user_id = None
        seg.locked_at = None
        db.session.commit()
        
        emit('segment_unlocked', {
            'segment_id': segment_id
        }, room=room, include_self=False)

@socketio.on('heartbeat')
def on_heartbeat(data):
    project_id = data['project_id']
    if project_id in project_users and current_user.id in project_users[project_id]:
        project_users[project_id][current_user.id]['last_seen'] = datetime.utcnow()
        
    # Check for inactive users (simple check during heartbeat)
    # In a real app, a background task is better.
    # Here we just check this project's users
    if project_id in project_users:
        to_remove = []
        now = datetime.utcnow()
        for uid, udata in project_users[project_id].items():
            last_seen = udata.get('last_seen')
            if last_seen and (now - last_seen).total_seconds() > 300: # 5 mins
                to_remove.append(uid)
        
        for uid in to_remove:
            del project_users[project_id][uid]
            emit('user_left', {'user_id': uid}, room=f"project_{project_id}")
            
            # Unlock their segments
            locked = Segment.query.filter_by(locked_by_user_id=uid).all()
            for s in locked:
                s.locked_by_user_id = None
                s.locked_at = None
                emit('segment_unlocked', {'segment_id': s.id}, room=f"project_{project_id}")
            db.session.commit()
