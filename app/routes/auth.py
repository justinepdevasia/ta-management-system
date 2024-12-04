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
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.register'))
        
        try:
            user = auth.create_user_with_email_and_password(email, password)
            user_id = user['localId']
            
            user_data = {
                "name": name,
                "email": email,
                "role": role,
                "created_at": datetime.now().isoformat()
            }
            
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
            
            db.child("users").child(user_id).set(user_data)
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return redirect(url_for('auth.register'))
    
    departments = db.child("departments").get().val() or []
    return render_template('auth/register.html', departments=departments)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    _, auth, db, _ = get_firebase()
    
    if 'user_id' in session:
        return redirect(url_for(f"{session['role']}.dashboard"))
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            user_data = db.child("users").child(user['localId']).get().val()
            
            if not user_data:
                flash('User account not found.', 'error')
                return redirect(url_for('auth.login'))
            
            session['user_id'] = user['localId']
            session['email'] = email
            session['role'] = user_data['role']
            session['name'] = user_data['name']
            
            return redirect(url_for(f"{user_data['role']}.dashboard"))
            
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
            
            db.child("users").child(session['user_id']).update(user_data)
            flash('Profile updated successfully!', 'success')
            
        except Exception as e:
            flash('Failed to update profile.', 'error')
    
    user_data = db.child("users").child(session['user_id']).get().val()
    departments = db.child("departments").get().val() or []
    
    return render_template('auth/profile.html', 
                         user=user_data,
                         departments=departments)

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    _, auth, _, _ = get_firebase()
    
    if request.method == 'POST':
        email = request.form['email']
        
        try:
            auth.send_password_reset_email(email)
            flash('Password reset email sent. Please check your inbox.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash('Failed to send password reset email.', 'error')
    
    return render_template('auth/reset_password.html')