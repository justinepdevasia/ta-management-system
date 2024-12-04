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
    
    # Get applicant's application
    application = db.child("applications")\
        .order_by_child("applicant_id")\
        .equal_to(session['user_id'])\
        .get().val()
    
    if application:
        # Convert to list and get the first (and only) application
        application = list(application.items())[0]
        app_id, app_data = application
        app_data['id'] = app_id
        
        # Get course details for all selected courses
        course_details = []
        for course_id in app_data.get('course_ids', []):
            course = db.child("courses").child(course_id).get().val()
            if course:
                course_details.append({
                    'id': course_id,
                    'name': course.get('name'),
                    'course_code': course.get('course_code'),
                    'status': app_data.get('course_statuses', {}).get(course_id, 'Pending')
                })
        app_data['course_details'] = course_details
        
    # Get available courses for new application
    all_courses = db.child("courses").get().val() or {}
    available_courses = {
        k: v for k, v in all_courses.items() 
        if not v.get('ta_assigned', False)
    }
    
    return render_template('applicant/dashboard.html',
                         application=app_data if application else None,
                         available_courses=available_courses if not application else {})

@applicant_bp.route('/application/new', methods=['GET', 'POST'])
@login_required
@role_required(['applicant'])
def new_application():
    _, _, db, storage = get_firebase()
    
    # Check if applicant already has an application
    existing_application = db.child("applications")\
        .order_by_child("applicant_id")\
        .equal_to(session['user_id'])\
        .get().val()
    
    if existing_application:
        flash('You already have an active application.', 'error')
        return redirect(url_for('applicant.dashboard'))
    
    if request.method == 'POST':
        try:
            course_ids = request.form.getlist('course_ids[]')
            if not course_ids:
                flash('Please select at least one course to apply for.', 'error')
                return redirect(url_for('applicant.new_application'))
            
            # Handle CV upload
            cv_url = None
            cv_file = request.files.get('cv')
            if cv_file:
                filename = f"cvs/{session['user_id']}/{str(uuid.uuid4())}.{cv_file.filename.rsplit('.', 1)[1].lower()}"
                storage.child(filename).put(cv_file)
                cv_url = storage.child(filename).get_url(None)
            
            # Initialize course statuses
            course_statuses = {course_id: 'Submitted' for course_id in course_ids}
            
            # Prepare application data
            application_data = {
                "applicant_id": session['user_id'],
                "course_ids": course_ids,
                "course_statuses": course_statuses,
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
    
    # Get available courses
    all_courses = db.child("courses").get().val() or {}
    available_courses = {
        k: v for k, v in all_courses.items() 
        if not v.get('ta_assigned', False)
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