from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.extensions import db
from firebase_admin import auth as firebase_auth
import firebase_admin

bp = Blueprint('auth', __name__)

@bp.route('/firebase-login', methods=['POST'])
def firebase_login():
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
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

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
            
    return render_template('login.html')

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

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
