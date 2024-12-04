from flask import Flask, redirect, url_for
from config.config import Config
from app.utils.firebase import initialize_firebase
from app.utils.filters import format_datetime, is_today, within_days

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize Firebase
    initialize_firebase(app)

    # Register template filters
    app.jinja_env.filters['datetime'] = format_datetime
    app.jinja_env.tests['is_today'] = is_today
    app.jinja_env.filters['within_days'] = within_days
    
    # Root route handler
    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for(f"{session['role']}.dashboard"))
        return redirect(url_for('auth.login'))
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.applicant import applicant_bp
    from app.routes.staff import staff_bp
    from app.routes.committee import committee_bp
    from app.routes.instructor import instructor_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(applicant_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(committee_bp)
    app.register_blueprint(instructor_bp)
    
    return app