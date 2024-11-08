from flask import Flask, render_template, request, redirect, url_for, flash, session
import pyrebase
from functools import wraps
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Firebase Configuration using environment variables
config = {
    "apiKey": os.getenv('FIREBASE_API_KEY'),
    "authDomain": os.getenv('FIREBASE_AUTH_DOMAIN'),
    "projectId": os.getenv('FIREBASE_PROJECT_ID'),
    "storageBucket": os.getenv('FIREBASE_STORAGE_BUCKET'),
    "messagingSenderId": os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
    "appId": os.getenv('FIREBASE_APP_ID'),
    "databaseURL": os.getenv('FIREBASE_DATABASE_URL')
}

# Initialize Firebase
firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        name = request.form['name']
        
        try:
            # Create user in Firebase Authentication
            user = auth.create_user_with_email_and_password(email, password)
            user_id = user['localId']
            
            # Store additional user data in Firebase Realtime Database
            user_data = {
                "name": name,
                "email": email,
                "role": role
            }
            db.child("users").child(user_id).set(user_data)
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            # Authenticate user with Firebase
            user = auth.sign_in_with_email_and_password(email, password)
            user_id = user['localId']
            
            # Get user data from database
            user_data = db.child("users").child(user_id).get().val()
            
            if user_data:
                session['user_id'] = user_id
                session['role'] = user_data.get('role')
                session['name'] = user_data.get('name')
                session['email'] = user_data.get('email')
                
                flash(f'Welcome back, {user_data.get("name")}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('User data not found.', 'error')
                return redirect(url_for('login'))
                
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    name = session.get('name')
    return render_template('dashboard.html', role=role, name=name)

if __name__ == '__main__':
    app.run(debug=True)