from flask import Flask
from config.config import Config
from app.utils.firebase import initialize_firebase

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize Firebase
    initialize_firebase(app)
    
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