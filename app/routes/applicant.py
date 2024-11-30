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
    
    # Get applicant's applications
    applications = db.child("applications").order_by_child("applicant_id").equal_to(session['user_id']).get()
    
    # Get all available courses
    available_courses = db.child("courses").get().val() or {}
    
    # Format applications for display
    formatted_applications = []
    if applications.each():
        for app in applications.each():
            app_data = app.val()
            app_data['id'] = app.key()
            # Add course details to application
            if 'course_id' in app_data:
                course = available_courses.get(app_data['course_id'], {})
                app_data['course_name'] = course.get('name', 'Unknown Course')
            formatted_applications.append(app_data)
    
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
            # Get form data
            courses = request.form.getlist('courses')
            previous_experience = request.form.get('previous_experience') == 'yes'
            prev_courses = request.form.getlist('previous_courses')
            prev_dates = request.form.getlist('previous_dates')
            
            # Prepare application data first
            application_data = {
                "applicant_id": session['user_id'],
                "status": "Draft",
                "submission_date": datetime.now().isoformat(),
                "courses": courses,
                "previous_experience": previous_experience,
                "previous_courses": prev_courses if previous_experience else [],
                "previous_dates": prev_dates if previous_experience else [],
                "gpa": request.form.get('gpa'),
                "semester": request.form.get('semester'),
                "current_step": request.form.get('current_step'),
                "research_interests": request.form.get('research_interests'),
                "additional_skills": request.form.get('additional_skills'),
                "references": request.form.get('references'),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            # Handle CV upload if file is provided
            cv_file = request.files.get('cv')
            if cv_file and cv_file.filename:
                try:
                    # Generate unique filename
                    file_extension = cv_file.filename.rsplit('.', 1)[1].lower()
                    filename = f"cvs/{session['user_id']}/{str(uuid.uuid4())}.{file_extension}"
                    
                    # Upload file to Firebase Storage
                    storage.child(filename).put(cv_file)
                    
                    # Get the URL only if upload was successful
                    cv_url = storage.child(filename).get_url(None)
                    application_data["cv_url"] = cv_url
                except Exception as e:
                    # Log the error but continue with application creation
                    print(f"CV upload failed: {str(e)}")
                    # Still create application without CV
                    application_data["cv_url"] = None
            
            # Save application
            db.child("applications").push(application_data)
            
            flash('Application draft created successfully!', 'success')
            return redirect(url_for('applicant.dashboard'))
            
        except Exception as e:
            flash(f'Error creating application: {str(e)}', 'error')
            return redirect(url_for('applicant.new_application'))
    
    # GET request - show application form
    courses = db.child("courses").get().val() or {}
    return render_template('applicant/new_application.html', courses=courses)
    
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
    courses = db.child("courses").get().val() or {}
    
    return render_template('applicant/view_application.html',
                         application=application,
                         courses=courses)

@applicant_bp.route('/application/<application_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['applicant'])
def edit_application(application_id):
    _, _, db, storage = get_firebase()
    
    # Get application data
    application = db.child("applications").child(application_id).get().val()
    
    if not application or application['applicant_id'] != session['user_id']:
        flash('Application not found.', 'error')
        return redirect(url_for('applicant.dashboard'))
    
    if application['status'] != 'Draft':
        flash('Only draft applications can be edited.', 'error')
        return redirect(url_for('applicant.view_application', application_id=application_id))
    
    if request.method == 'POST':
        try:
            # Update application data
            update_data = {
                "courses": request.form.getlist('courses'),
                "previous_experience": request.form.get('previous_experience') == 'yes',
                "gpa": request.form.get('gpa'),
                "semester": request.form.get('semester'),
                "current_step": request.form.get('current_step'),
                "research_interests": request.form.get('research_interests'),
                "additional_skills": request.form.get('additional_skills'),
                "references": request.form.get('references'),
                "updated_at": datetime.now().isoformat()
            }
            
            # Handle CV update if provided
            cv_file = request.files.get('cv')
            if cv_file:
                filename = f"cvs/{session['user_id']}/{str(uuid.uuid4())}.{cv_file.filename.rsplit('.', 1)[1].lower()}"
                storage.child(filename).put(cv_file)
                update_data['cv_url'] = storage.child(filename).get_url(None)
            
            # Update application
            db.child("applications").child(application_id).update(update_data)
            
            flash('Application updated successfully!', 'success')
            return redirect(url_for('applicant.view_application', application_id=application_id))
            
        except Exception as e:
            flash(f'Error updating application: {str(e)}', 'error')
    
    # GET request - show edit form
    courses = db.child("courses").get().val() or {}
    return render_template('applicant/edit_application.html',
                         application=application,
                         courses=courses)

@applicant_bp.route('/application/<application_id>/submit', methods=['POST'])
@login_required
@role_required(['applicant'])
def submit_application(application_id):
    _, _, db, _ = get_firebase()
    
    # Get application data
    application = db.child("applications").child(application_id).get().val()
    
    if not application or application['applicant_id'] != session['user_id']:
        flash('Application not found.', 'error')
        return redirect(url_for('applicant.dashboard'))
    
    if application['status'] != 'Draft':
        flash('Only draft applications can be submitted.', 'error')
        return redirect(url_for('applicant.view_application', application_id=application_id))
    
    try:
        # Update application status
        db.child("applications").child(application_id).update({
            "status": "Submitted",
            "submission_date": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })
        
        flash('Application submitted successfully!', 'success')
    except Exception as e:
        flash(f'Error submitting application: {str(e)}', 'error')
    
    return redirect(url_for('applicant.view_application', application_id=application_id))

@applicant_bp.route('/offer/<offer_id>/<action>', methods=['POST'])
@login_required
@role_required(['applicant'])
def handle_offer(offer_id, action):
    _, _, db, _ = get_firebase()
    
    if action not in ['accept', 'reject']:
        flash('Invalid action.', 'error')
        return redirect(url_for('applicant.dashboard'))
    
    try:
        # Get offer data
        offer = db.child("offers").child(offer_id).get().val()
        
        if not offer or offer['applicant_id'] != session['user_id']:
            flash('Offer not found.', 'error')
            return redirect(url_for('applicant.dashboard'))
        
        # Update offer status
        new_status = 'Accepted' if action == 'accept' else 'Rejected'
        db.child("offers").child(offer_id).update({
            "status": new_status,
            "response_date": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })
        
        # Update application status if offer is accepted
        if action == 'accept':
            db.child("applications").child(offer['application_id']).update({
                "status": "OfferAccepted",
                "updated_at": datetime.now().isoformat()
            })
        
        flash(f'Offer {action}ed successfully!', 'success')
    except Exception as e:
        flash(f'Error handling offer: {str(e)}', 'error')
    
    return redirect(url_for('applicant.dashboard'))