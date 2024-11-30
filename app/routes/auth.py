from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.utils.firebase import get_firebase
from app.utils.decorators import login_required
from datetime import datetime

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
        
        # Validate password match
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
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
                "created_at": datetime.now().isoformat()
            }
            
            # Add role-specific information
            if role == 'applicant':
                user_data.update({
                    "degree_program": request.form.get('degree_program', ''),
                    "graduation_year": request.form.get('graduation_year', '')
                })
            elif role == 'instructor':
                user_data.update({
                    "department": request.form.get('department', ''),
                    "office": request.form.get('office', '')
                })
            
            # Store user data in Firebase
            db.child("users").child(user_id).set(user_data)
            
            flash('Registration successful! Please login.', 'success')
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
            
            # Get user data from database
            user_data = db.child("users").child(user['localId']).get().val()
            
            if not user_data:
                flash('User account not found.', 'error')
                return redirect(url_for('auth.login'))
            
            # Set session data
            session['user_id'] = user['localId']
            session['email'] = email
            session['role'] = user_data['role']
            session['name'] = user_data['name']
            
            # Redirect based on role
            return redirect(url_for(f'{user_data["role"]}.dashboard'))
            
        except Exception as e:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('auth.login'))