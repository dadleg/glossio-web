from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.extensions import db

bp = Blueprint('auth', __name__)

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
