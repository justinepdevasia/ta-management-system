from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.utils.firebase import get_firebase
from app.utils.decorators import login_required
import re

auth_bp = Blueprint('auth', __name__)

FAU_EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@fau\.edu$'
ALLOWED_ROLES = ['applicant', 'staff', 'committee', 'instructor']

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Registration logic from previous response
    pass

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Login logic from previous response
    pass

@auth_bp.route('/logout')
@login_required
def logout():
    # Logout logic from previous response
    pass# app/routes/auth.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.utils.firebase import get_firebase
from app.utils.decorators import login_required
from datetime import datetime
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    _, auth, db, _ = get_firebase()
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']
        name = request.form['name']
        
        # Validate FAU email
        if not email.endswith('@fau.edu'):
            flash('Please use your FAU email address.', 'error')
            return redirect(url_for('auth.register'))
        
        # Validate password match
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.register'))
        
        # Validate role
        if role not in ['applicant', 'staff', 'committee', 'instructor']:
            flash('Invalid role selected.', 'error')
            return redirect(url_for('auth.register'))
        
        try:
            # Create user in Firebase Authentication
            user = auth.create_user_with_email_and_password(email, password)
            user_id = user['localId']
            
            # Prepare user data based on role
            user_data = {
                "name": name,
                "email": email,
                "role": role,
                "created_at": datetime.now().isoformat(),
                "status": "pending"  # All new accounts need approval
            }
            
            # Add role-specific information
            if role == 'applicant':
                user_data.update({
                    "degree_program": request.form.get('degree_program', ''),
                    "previous_ta": request.form.get('previous_ta', 'no'),
                    "graduation_year": request.form.get('graduation_year', '')
                })
            elif role == 'instructor':
                user_data.update({
                    "department": request.form.get('department', ''),
                    "office": request.form.get('office', ''),
                    "courses": request.form.getlist('courses')
                })
            
            # Store user data in Firebase
            db.child("users").child(user_id).set(user_data)
            
            # Send verification email
            auth.send_email_verification(user['idToken'])
            
            flash('Registration successful! Please verify your email.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return redirect(url_for('auth.register'))
    
    # GET request - show registration form
    departments = db.child("departments").get().val() or []
    return render_template('auth/register.html', departments=departments)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    _, auth, db, _ = get_firebase()
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            # Authenticate with Firebase
            user = auth.sign_in_with_email_and_password(email, password)
            
            # Get user info
            account_info = auth.get_account_info(user['idToken'])
            email_verified = account_info['users'][0]['emailVerified']
            
            if not email_verified:
                flash('Please verify your email before logging in.', 'error')
                return redirect(url_for('auth.login'))
            
            # Get user data from database
            user_data = db.child("users").child(user['localId']).get().val()
            
            if not user_data:
                flash('User account not found.', 'error')
                return redirect(url_for('auth.login'))
            
            if user_data.get('status') != 'approved':
                flash('Your account is pending approval.', 'error')
                return redirect(url_for('auth.login'))
            
            # Set session data
            session['user_id'] = user['localId']
            session['email'] = email
            session['role'] = user_data['role']
            session['name'] = user_data['name']
            
            # Log login activity
            db.child("activity_logs").push({
                "user_id": user['localId'],
                "action": "login",
                "timestamp": datetime.now().isoformat(),
                "ip_address": request.remote_addr
            })
            
            # Redirect based on role
            return redirect(url_for(f'{user_data["role"]}.dashboard'))
            
        except Exception as e:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    _, auth, db, _ = get_firebase()
    
    try:
        # Log the logout activity
        if 'user_id' in session:
            db.child("activity_logs").push({
                "user_id": session['user_id'],
                "action": "logout",
                "timestamp": datetime.now().isoformat(),
                "ip_address": request.remote_addr
            })
        
        # Clear session
        session.clear()
        flash('You have been logged out successfully.', 'success')
        
    except Exception as e:
        flash('Logout encountered an error.', 'error')
    
    return redirect(url_for('auth.login'))

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    _, auth, _, _ = get_firebase()
    
    if request.method == 'POST':
        email = request.form['email']
        
        if not email.endswith('@fau.edu'):
            flash('Please use your FAU email address.', 'error')
            return redirect(url_for('auth.reset_password'))
        
        try:
            auth.send_password_reset_email(email)
            flash('Password reset email sent. Please check your inbox.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash('Failed to send password reset email.', 'error')
    
    return render_template('auth/reset_password.html')

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    _, _, db, _ = get_firebase()
    
    if request.method == 'POST':
        try:
            user_data = {
                "name": request.form['name'],
                "phone": request.form.get('phone', '')
            }
            
            # Update role-specific information
            if session['role'] == 'applicant':
                user_data.update({
                    "degree_program": request.form.get('degree_program', ''),
                    "graduation_year": request.form.get('graduation_year', '')
                })
            elif session['role'] == 'instructor':
                user_data.update({
                    "department": request.form.get('department', ''),
                    "office": request.form.get('office', '')
                })
            
            # Update user data
            db.child("users").child(session['user_id']).update(user_data)
            flash('Profile updated successfully!', 'success')
            
        except Exception as e:
            flash('Failed to update profile.', 'error')
    
    # Get current user data
    user_data = db.child("users").child(session['user_id']).get().val()
    departments = db.child("departments").get().val() or []
    
    return render_template('auth/profile.html', 
                         user=user_data,
                         departments=departments)