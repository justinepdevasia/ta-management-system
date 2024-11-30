# app/routes/applicant.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.utils.decorators import login_required, role_required
from app.utils.firebase import get_firebase
from datetime import datetime
import uuid

applicant_bp = Blueprint('applicant', __name__, url_prefix='/applicant')

@applicant_bp.route('/dashboard')
@login_required
@role_required(['applicant'])
def dashboard():
    _, _, db, _ = get_firebase()
    
    # Get applicant's applications with course details
    applications = db.child("applications")\
        .order_by_child("applicant_id")\
        .equal_to(session['user_id'])\
        .get()
    
    formatted_applications = []
    if applications.each():
        for app in applications.each():
            app_data = app.val()
            app_data['id'] = app.key()
            
            # Get course details for this application
            if 'course_id' in app_data:
                course = db.child("courses").child(app_data['course_id']).get().val()
                if course:
                    app_data['course_name'] = course.get('name')
                    app_data['course_code'] = course.get('course_code')
            formatted_applications.append(app_data)
    
    # Get available courses for new applications
    # Only show courses that the applicant hasn't already applied to
    all_courses = db.child("courses").get().val() or {}
    applied_course_ids = [app.get('course_id') for app in formatted_applications]
    available_courses = {
        k: v for k, v in all_courses.items() 
        if k not in applied_course_ids and not v.get('ta_assigned', False)
    }
    
    return render_template('applicant/dashboard.html',
                         applications=formatted_applications,
                         available_courses=available_courses)

@applicant_bp.route('/application/new', methods=['GET', 'POST'])
@login_required
@role_required(['applicant'])
def new_application():
    _, _, db, storage = get_firebase()
    
    if request.method == 'POST':
        try:
            course_id = request.form.get('course_id')
            if not course_id:
                flash('Please select a course to apply for.', 'error')
                return redirect(url_for('applicant.new_application'))
            
            # Check if already applied to this course
            existing_application = db.child("applications")\
                .order_by_child("applicant_id")\
                .equal_to(session['user_id'])\
                .get().val()
            
            if existing_application:
                for app in existing_application.values():
                    if app.get('course_id') == course_id:
                        flash('You have already applied for this course.', 'error')
                        return redirect(url_for('applicant.dashboard'))
            
            # Handle CV upload
            cv_url = None
            cv_file = request.files.get('cv')
            if cv_file:
                filename = f"cvs/{session['user_id']}/{str(uuid.uuid4())}.{cv_file.filename.rsplit('.', 1)[1].lower()}"
                storage.child(filename).put(cv_file)
                cv_url = storage.child(filename).get_url(None)
            
            # Prepare application data
            application_data = {
                "applicant_id": session['user_id'],
                "course_id": course_id,
                "status": "Submitted",
                "submission_date": datetime.now().isoformat(),
                "previous_experience": request.form.get('previous_experience') == 'yes',
                "gpa": float(request.form.get('gpa')),
                "research_interests": request.form.get('research_interests'),
                "additional_skills": request.form.get('additional_skills'),
                "cv_url": cv_url,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Add previous experience details if applicable
            if application_data["previous_experience"]:
                application_data.update({
                    "previous_courses": request.form.getlist('previous_courses[]'),
                    "previous_dates": request.form.getlist('previous_dates[]')
                })
            
            # Save application
            db.child("applications").push(application_data)
            flash('Application submitted successfully!', 'success')
            return redirect(url_for('applicant.dashboard'))
            
        except Exception as e:
            flash(f'Error submitting application: {str(e)}', 'error')
            return redirect(url_for('applicant.new_application'))
    
    # GET request - show application form
    # Only show courses that the applicant hasn't already applied to
    all_courses = db.child("courses").get().val() or {}
    existing_applications = db.child("applications")\
        .order_by_child("applicant_id")\
        .equal_to(session['user_id'])\
        .get().val() or {}
    
    applied_course_ids = [app.get('course_id') for app in existing_applications.values()]
    available_courses = {
        k: v for k, v in all_courses.items() 
        if k not in applied_course_ids and not v.get('ta_assigned', False)
    }
    
    return render_template('applicant/new_application.html', 
                         courses=available_courses)

@applicant_bp.route('/application/<application_id>', methods=['GET'])
@login_required
@role_required(['applicant'])
def view_application(application_id):
    _, _, db, _ = get_firebase()
    
    # Get application data
    application = db.child("applications").child(application_id).get().val()
    
    if not application or application['applicant_id'] != session['user_id']:
        flash('Application not found.', 'error')
        return redirect(url_for('applicant.dashboard'))
    
    # Get course details
    course = db.child("courses").child(application['course_id']).get().val()
    
    return render_template('applicant/view_application.html',
                         application=application,
                         course=course)

@applicant_bp.route('/application/<application_id>/handle-offer/<action>', methods=['POST'])
@login_required
@role_required(['applicant'])
def handle_offer(application_id, action):
    _, _, db, _ = get_firebase()
    
    if action not in ['accept', 'reject']:
        flash('Invalid action.', 'error')
        return redirect(url_for('applicant.dashboard'))
    
    try:
        # Get application data
        application = db.child("applications").child(application_id).get().val()
        
        if not application or application['applicant_id'] != session['user_id']:
            flash('Application not found.', 'error')
            return redirect(url_for('applicant.dashboard'))
        
        if application['status'] != 'Selected':
            flash('This application is not in selected status.', 'error')
            return redirect(url_for('applicant.view_application', application_id=application_id))
        
        # Update application status based on action
        new_status = 'Accepted' if action == 'accept' else 'Rejected'
        
        db.child("applications").child(application_id).update({
            "status": new_status,
            "response_date": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })
        
        # If accepted, update course TA assignment status
        if action == 'accept':
            db.child("courses").child(application['course_id']).update({
                "ta_assigned": True
            })
            
            # Create TA assignment record
            assignment_data = {
                "course_id": application['course_id'],
                "ta_id": session['user_id'],
                "status": "Active",
                "assigned_at": datetime.now().isoformat()
            }
            db.child("ta_assignments").push(assignment_data)
        
        flash(f'Application {new_status.lower()} successfully!', 'success')
        
    except Exception as e:
        flash(f'Error processing response: {str(e)}', 'error')
    
    return redirect(url_for('applicant.dashboard'))