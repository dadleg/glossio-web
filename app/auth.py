from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.extensions import db
import os

# Firebase imports - conditional for LOCAL_MODE support
FIREBASE_ENABLED = False
if os.environ.get('LOCAL_MODE', '').lower() != 'true':
    try:
        from firebase_admin import auth as firebase_auth
        import firebase_admin
        FIREBASE_ENABLED = True
    except ImportError:
        print("firebase_admin not available - running in local-only mode")
else:
    print("LOCAL_MODE enabled - Firebase auth disabled")

bp = Blueprint('auth', __name__)

@bp.route('/firebase-login', methods=['POST'])
def firebase_login():
    # Reject if Firebase is not enabled (LOCAL_MODE)
    if not FIREBASE_ENABLED:
        return jsonify({'success': False, 'message': 'Firebase authentication is disabled in local mode. Use offline login.'}), 503
    
    if current_user.is_authenticated:
        return jsonify({'success': True, 'redirect': url_for('main.index')})

    id_token = request.json.get('idToken')
    if not id_token:
        return jsonify({'success': False, 'message': 'No token provided'}), 400

    try:
        # Verify the ID token
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        
        if not email:
            return jsonify({'success': False, 'message': 'Email not found in token'}), 400

        # Check if user exists
        user = User.query.filter((User.firebase_uid == uid) | (User.email == email)).first()

        if user:
            # Update firebase_uid if missing (linking accounts)
            if not user.firebase_uid:
                user.firebase_uid = uid
                db.session.commit()
        else:
            # Create new user
            user = User(email=email, firebase_uid=uid, name=decoded_token.get('name', ''))
            db.session.add(user)
            db.session.commit()

        # Log user in
        login_user(user)
        return jsonify({'success': True, 'redirect': url_for('main.index')})

    except Exception as e:
        print(f"Firebase login error: {e}")
        return jsonify({'success': False, 'message': f'Invalid token: {str(e)}'}), 401

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('Invalid email or password')
            
    return render_template('login.html',
                           local_mode=not FIREBASE_ENABLED,
                           firebase_api_key=current_app.config.get('FIREBASE_API_KEY', ''),
                           firebase_auth_domain=current_app.config.get('FIREBASE_AUTH_DOMAIN', ''),
                           firebase_project_id=current_app.config.get('FIREBASE_PROJECT_ID', ''),
                           firebase_storage_bucket=current_app.config.get('FIREBASE_STORAGE_BUCKET', ''),
                           firebase_messaging_sender_id=current_app.config.get('FIREBASE_MESSAGING_SENDER_ID', ''),
                           firebase_app_id=current_app.config.get('FIREBASE_APP_ID', ''),
                           firebase_measurement_id=current_app.config.get('FIREBASE_MEASUREMENT_ID', ''))

# @bp.route('/register', methods=['GET', 'POST'])
# def register():
#     # Registration disabled by admin request
#     if current_user.is_authenticated:
#         return redirect(url_for('main.index'))
#         
#     if request.method == 'POST':
#         email = request.form['email']
#         password = request.form['password']
#         
#         if User.query.filter_by(email=email).first():
#             flash('Email already registered')
#         else:
#             user = User(email=email)
#             user.set_password(password)
#             db.session.add(user)
#             db.session.commit()
#             flash('Registration successful! Please login.')
#             return redirect(url_for('auth.login'))
#             
#     return render_template('register.html')

@bp.route('/offline')
def offline_login():
    """Login as guest/offline user for local-only mode."""
    # Create or get the offline user
    offline_email = 'offline@local.glossio'
    user = User.query.filter_by(email=offline_email).first()
    
    if not user:
        user = User(
            email=offline_email, 
            name='Offline User',
            firebase_uid=None
        )
        db.session.add(user)
        db.session.commit()
    
    login_user(user)
    return redirect(url_for('main.index'))

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
