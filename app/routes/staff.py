from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.utils.decorators import login_required, role_required
from app.utils.firebase import get_firebase
from datetime import datetime
import uuid

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

@staff_bp.route('/dashboard')
@login_required
@role_required(['staff'])
def dashboard():
    _, _, db, _ = get_firebase()
    
    # Get all applications
    all_applications = db.child("applications").get().val() or {}
    
    # Initialize counters
    status_counts = {
        'total': 0,
        'pending_review': 0,
        'reviewed': 0,
        'selected': 0,
        'accepted': 0,
        'rejected': 0
    }
    
    # Process recent applications with correct status
    recent_applications = []
    for app_id, app in all_applications.items():
        status_counts['total'] += 1
        
        # Determine the most advanced status from course_statuses
        course_statuses = app.get('course_statuses', {}).values()
        base_status = app.get('status', 'Submitted')
        
        current_status = base_status
        if course_statuses:
            if 'Accepted' in course_statuses:
                current_status = 'Accepted'
            elif 'Rejected' in course_statuses:
                current_status = 'Rejected'
            elif 'Selected' in course_statuses:
                current_status = 'Selected'
            elif base_status == 'Reviewed':
                current_status = 'Reviewed'
        
        # Update status counts
        if current_status == 'Submitted':
            status_counts['pending_review'] += 1
        elif current_status == 'Reviewed':
            status_counts['reviewed'] += 1
        elif current_status == 'Selected':
            status_counts['selected'] += 1
        elif current_status == 'Accepted':
            status_counts['accepted'] += 1
        elif current_status == 'Rejected':
            status_counts['rejected'] += 1
        
        # Add to recent applications list
        if len(recent_applications) < 5:  # Limit to 5 recent applications
            applicant = db.child("users").child(app.get('applicant_id')).get().val()
            if applicant:
                app_data = {
                    'id': app_id,
                    **app,
                    'status': current_status,  # Use the determined status
                    'applicant_name': applicant.get('name'),
                    'applicant_email': applicant.get('email')
                }
                recent_applications.append(app_data)
    
    # Get courses needing TAs
    courses = db.child("courses").order_by_child("ta_assigned").equal_to(False).get().val() or {}
    
    stats = {
        'total_applications': status_counts['total'],
        'pending_review': status_counts['pending_review'],
        'reviewed': status_counts['reviewed'],
        'selected': status_counts['selected'],
        'accepted': status_counts['accepted'],
        'rejected': status_counts['rejected'],
        'courses_needing_tas': len(courses)
    }
    
    return render_template('staff/dashboard.html',
                         stats=stats,
                         recent_applications=recent_applications,
                         courses=courses)

@staff_bp.route('/applications')
@login_required
@role_required(['staff'])
def view_applications():
    _, _, db, _ = get_firebase()
    
    status_filter = request.args.get('status', 'all')
    department_filter = request.args.get('department')
    
    # Get all applications
    applications = db.child("applications").get().val() or {}
    
    # Get applicant details for each application
    enriched_applications = []
    for app_id, app in applications.items():
        applicant = db.child("users").child(app.get('applicant_id')).get().val()
        if applicant:
            # Get the most advanced status from course_statuses
            course_statuses = app.get('course_statuses', {}).values()
            status_priority = {
                'Accepted': 4,
                'Rejected': 3,
                'Selected': 2,
                'Reviewed': 1,
                'Submitted': 0
            }
            
            # Determine the most advanced status
            current_status = app.get('status', 'Submitted')
            if course_statuses:
                max_status = max(course_statuses, 
                               key=lambda x: status_priority.get(x, -1))
                if status_priority.get(max_status, -1) > status_priority.get(current_status, -1):
                    current_status = max_status
            
            app_data = {
                'id': app_id,
                **app,
                'status': current_status,  # Use the determined status
                'applicant_name': applicant.get('name'),
                'applicant_email': applicant.get('email')
            }
            
            # Apply filters
            if status_filter != 'all' and current_status != status_filter:
                continue
            if department_filter and app.get('department') != department_filter:
                continue
                
            enriched_applications.append(app_data)
    
    # Sort by submission date (newest first)
    enriched_applications.sort(key=lambda x: x.get('submission_date', ''), reverse=True)
    
    departments = db.child("departments").get().val() or {}
    courses = db.child("courses").get().val() or {}
    
    return render_template('staff/applications.html',
                         applications=enriched_applications,
                         departments=departments,
                         courses=courses,
                         current_filters={
                             'status': status_filter,
                             'department': department_filter
                         })

@staff_bp.route('/application/<application_id>/review', methods=['GET', 'POST'])
@login_required
@role_required(['staff'])
def review_application(application_id):
    _, _, db, _ = get_firebase()
    
    if request.method == 'POST':
        try:
            # Prepare review data
            review_data = {
                "reviewer_id": session['user_id'],
                "reviewer_name": session.get('name'),
                "evaluation": {
                    "academic_strength": int(request.form['academic_strength']),
                    "teaching_potential": int(request.form['teaching_potential']),
                    "technical_skills": int(request.form['technical_skills']),
                    "communication": int(request.form['communication'])
                },
                "recommended_courses": request.form.getlist('recommended_courses'),
                "comments": request.form['comments'],
                "overall_recommendation": request.form['overall_recommendation'],
                "review_date": datetime.now().isoformat()
            }
            
            # Update application with review
            db.child("applications").child(application_id).update({
                "status": "Reviewed",
                "staff_review": review_data,
                "updated_at": datetime.now().isoformat()
            })
            
            # Create course recommendations
            for course_id in review_data['recommended_courses']:
                recommendation_data = {
                    "application_id": application_id,
                    "course_id": course_id,
                    "reviewer_id": session['user_id'],
                    "evaluation_scores": review_data['evaluation'],
                    "created_at": datetime.now().isoformat()
                }
                db.child("recommendations").push(recommendation_data)
            
            flash('Application review submitted successfully!', 'success')
            return redirect(url_for('staff.view_applications'))
            
        except Exception as e:
            flash(f'Error submitting review: {str(e)}', 'error')
    
    # Get application data
    application = db.child("applications").child(application_id).get().val()
    if not application:
        flash('Application not found.', 'error')
        return redirect(url_for('staff.view_applications'))
    
    # Get applicant details
    applicant = db.child("users").child(application['applicant_id']).get().val() or {}
    
    # Get available courses for recommendations
    courses = db.child("courses").order_by_child("ta_assigned").equal_to(False).get().val() or {}
    
    return render_template('staff/review_application.html',
                         application={**application, 'id': application_id},
                         applicant=applicant,
                         courses=courses)

@staff_bp.route('/courses', methods=['GET', 'POST'])
@login_required
@role_required(['staff'])
def manage_courses():
    _, _, db, _ = get_firebase()
    
    # Define departments
    departments = {
        'cs': {'id': 'cs', 'name': 'Computer Science'},
        'math': {'id': 'math', 'name': 'Mathematics'},
        'physics': {'id': 'physics', 'name': 'Physics'},
        'eng': {'id': 'eng', 'name': 'Engineering'},
        'bio': {'id': 'bio', 'name': 'Biology'},
        'chem': {'id': 'chem', 'name': 'Chemistry'}
    }
    
    if request.method == 'POST':
        try:
            course_data = {
                "course_code": request.form['course_code'],
                "name": request.form['name'],
                "department": request.form['department'],
                "department_name": departments[request.form['department']]['name'],
                "semester": request.form['semester'],
                "ta_requirements": {
                    "number_needed": int(request.form['number_needed']),
                    "hours_per_week": int(request.form['hours_per_week']),
                    "required_skills": [s.strip() for s in request.form.get('required_skills', '').split(',') if s.strip()],
                    "preferred_skills": [s.strip() for s in request.form.get('preferred_skills', '').split(',') if s.strip()]
                },
                "ta_assigned": False,
                "created_by": session['user_id'],
                "created_at": datetime.now().isoformat()
            }
            
            db.child("courses").push(course_data)
            flash('Course added successfully!', 'success')
            return redirect(url_for('staff.manage_courses'))
            
        except Exception as e:
            flash(f'Error adding course: {str(e)}', 'error')
    
    # Get all courses
    courses = db.child("courses").get().val() or {}
    
    return render_template('staff/manage_courses.html',
                         courses=courses,
                         departments=departments)
                                                  
@staff_bp.route('/course/<course_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['staff'])
def edit_course(course_id):
    _, _, db, _ = get_firebase()
    
    if request.method == 'POST':
        try:
            course_data = {
                "course_code": request.form['course_code'],
                "name": request.form['name'],
                "department": request.form['department'],
                "semester": request.form['semester'],
                "instructor_id": request.form['instructor_id'],
                "ta_requirements": {
                    "number_needed": int(request.form['number_needed']),
                    "hours_per_week": int(request.form['hours_per_week']),
                    "required_skills": [s.strip() for s in request.form.get('required_skills', '').split(',') if s.strip()],
                    "preferred_skills": [s.strip() for s in request.form.get('preferred_skills', '').split(',') if s.strip()]
                },
                "updated_by": session['user_id'],
                "updated_at": datetime.now().isoformat()
            }
            
            db.child("courses").child(course_id).update(course_data)
            flash('Course updated successfully!', 'success')
            return redirect(url_for('staff.manage_courses'))
            
        except Exception as e:
            flash(f'Error updating course: {str(e)}', 'error')
    
    # Get course data
    course = db.child("courses").child(course_id).get().val()
    if not course:
        flash('Course not found.', 'error')
        return redirect(url_for('staff.manage_courses'))
    
    departments = db.child("departments").get().val() or {}
    instructors = db.child("users").order_by_child("role").equal_to("instructor").get().val() or {}
    
    return render_template('staff/edit_course.html',
                         course={**course, 'id': course_id},
                         departments=departments,
                         instructors=instructors)

@staff_bp.route('/course/<course_id>/delete', methods=['POST'])
@login_required
@role_required(['staff'])
def delete_course(course_id):
    _, _, db, _ = get_firebase()
    
    try:
        # Check if course has any TA assignments
        assignments = db.child("ta_assignments").order_by_child("course_id").equal_to(course_id).get().val()
        if assignments:
            flash('Cannot delete course with active TA assignments.', 'error')
            return redirect(url_for('staff.manage_courses'))
        
        db.child("courses").child(course_id).remove()
        flash('Course deleted successfully!', 'success')
        
    except Exception as e:
        flash(f'Error deleting course: {str(e)}', 'error')
    
    return redirect(url_for('staff.manage_courses'))

@staff_bp.route('/recommendations')
@login_required
@role_required(['staff'])
def view_recommendations():
    _, _, db, _ = get_firebase()
    
    # Get course_id from query parameters if provided
    course_id = request.args.get('course_id')
    
    # Get all recommendations
    recommendations = db.child("recommendations").get().val() or {}
    
    # Filter by course if course_id provided
    if course_id:
        recommendations = {k: v for k, v in recommendations.items() 
                         if v.get('course_id') == course_id}
    
    # Enrich recommendations with application and course details
    enriched_recommendations = []
    for rec_id, rec in recommendations.items():
        application = db.child("applications").child(rec['application_id']).get().val()
        course = db.child("courses").child(rec['course_id']).get().val()
        applicant = db.child("users").child(application['applicant_id']).get().val() if application else None
        
        if application and course and applicant:
            enriched_recommendations.append({
                'id': rec_id,
                **rec,
                'applicant_name': applicant.get('name'),
                'applicant_email': applicant.get('email'),
                'course_code': course.get('course_code'),
                'course_name': course.get('name')
            })
    
    courses = db.child("courses").get().val() or {}
    departments = db.child("departments").get().val() or {}
    
    return render_template('staff/recommendations.html',
                         recommendations=enriched_recommendations,
                         courses=courses,
                         departments=departments)