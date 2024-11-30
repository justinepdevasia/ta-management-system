# app/routes/staff.py

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
    
    # Get summary statistics
    stats = {
        'total_applications': len(db.child("applications").get().val() or {}),
        'pending_review': len(db.child("applications").order_by_child("status").equal_to("Submitted").get().val() or {}),
        'courses_needing_tas': len(db.child("courses").order_by_child("ta_assigned").equal_to(False).get().val() or {}),
        'active_tas': len(db.child("ta_assignments").order_by_child("status").equal_to("Active").get().val() or {})
    }
    
    # Get recent applications
    recent_applications = db.child("applications").order_by_child("submission_date").limit_to_last(5).get().val() or {}
    
    # Get courses needing TAs
    courses_needing_tas = db.child("courses").order_by_child("ta_assigned").equal_to(False).get().val() or {}
    
    return render_template('staff/dashboard.html',
                         stats=stats,
                         recent_applications=recent_applications,
                         courses_needing_tas=courses_needing_tas)

@staff_bp.route('/courses', methods=['GET', 'POST'])
@login_required
@role_required(['staff'])
def manage_courses():
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
                    "required_skills": request.form.getlist('required_skills'),
                    "preferred_skills": request.form.getlist('preferred_skills')
                },
                "ta_assigned": False,
                "created_by": session['user_id'],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            db.child("courses").push(course_data)
            flash('Course added successfully!', 'success')
            
        except Exception as e:
            flash(f'Error adding course: {str(e)}', 'error')
    
    # Get all courses and instructors for display
    courses = db.child("courses").get().val() or {}
    instructors = db.child("users").order_by_child("role").equal_to("instructor").get().val() or {}
    departments = db.child("departments").get().val() or {}
    
    return render_template('staff/manage_courses.html',
                         courses=courses,
                         instructors=instructors,
                         departments=departments)

@staff_bp.route('/course/<course_id>', methods=['GET', 'POST'])
@login_required
@role_required(['staff'])
def edit_course(course_id):
    _, _, db, _ = get_firebase()
    
    if request.method == 'POST':
        try:
            update_data = {
                "name": request.form['name'],
                "department": request.form['department'],
                "semester": request.form['semester'],
                "instructor_id": request.form['instructor_id'],
                "ta_requirements": {
                    "number_needed": int(request.form['number_needed']),
                    "hours_per_week": int(request.form['hours_per_week']),
                    "required_skills": request.form.getlist('required_skills'),
                    "preferred_skills": request.form.getlist('preferred_skills')
                },
                "updated_at": datetime.now().isoformat()
            }
            
            db.child("courses").child(course_id).update(update_data)
            flash('Course updated successfully!', 'success')
            
        except Exception as e:
            flash(f'Error updating course: {str(e)}', 'error')
    
    course = db.child("courses").child(course_id).get().val()
    instructors = db.child("users").order_by_child("role").equal_to("instructor").get().val() or {}
    departments = db.child("departments").get().val() or {}
    
    return render_template('staff/edit_course.html',
                         course=course,
                         instructors=instructors,
                         departments=departments)

@staff_bp.route('/applications')
@login_required
@role_required(['staff'])
def view_applications():
    _, _, db, _ = get_firebase()
    
    status_filter = request.args.get('status', 'Submitted')
    department = request.args.get('department', None)
    
    # Get applications based on filters
    applications = db.child("applications").order_by_child("status").equal_to(status_filter).get().val() or {}
    
    if department:
        applications = {k: v for k, v in applications.items() if v.get('department') == department}
    
    # Get related data
    courses = db.child("courses").get().val() or {}
    departments = db.child("departments").get().val() or {}
    
    return render_template('staff/applications.html',
                         applications=applications,
                         courses=courses,
                         departments=departments,
                         current_status=status_filter,
                         current_department=department)

@staff_bp.route('/application/<application_id>/review', methods=['GET', 'POST'])
@login_required
@role_required(['staff'])
def review_application(application_id):
    _, _, db, _ = get_firebase()
    
    if request.method == 'POST':
        try:
            recommendation = {
                "reviewer_id": session['user_id'],
                "recommended_courses": request.form.getlist('recommended_courses'),
                "evaluation": {
                    "academic_strength": int(request.form['academic_strength']),
                    "teaching_potential": int(request.form['teaching_potential']),
                    "technical_skills": int(request.form['technical_skills']),
                    "communication": int(request.form['communication'])
                },
                "comments": request.form['comments'],
                "overall_recommendation": request.form['overall_recommendation'],
                "created_at": datetime.now().isoformat()
            }
            
            # Add recommendation to application
            db.child("applications").child(application_id).child("staff_review").set(recommendation)
            
            # Update application status
            db.child("applications").child(application_id).update({
                "status": "Reviewed",
                "updated_at": datetime.now().isoformat()
            })
            
            flash('Application review submitted successfully!', 'success')
            return redirect(url_for('staff.view_applications'))
            
        except Exception as e:
            flash(f'Error submitting review: {str(e)}', 'error')
    
    # Get application data
    application = db.child("applications").child(application_id).get().val()
    
    if not application:
        flash('Application not found.', 'error')
        return redirect(url_for('staff.view_applications'))
    
    # Get related data
    courses = db.child("courses").get().val() or {}
    applicant = db.child("users").child(application['applicant_id']).get().val() or {}
    
    return render_template('staff/review_application.html',
                         application=application,
                         courses=courses,
                         applicant=applicant)

@staff_bp.route('/ta-assignments')
@login_required
@role_required(['staff'])
def ta_assignments():
    _, _, db, _ = get_firebase()
    
    # Get all TA assignments
    assignments = db.child("ta_assignments").get().val() or {}
    
    # Get related data
    courses = db.child("courses").get().val() or {}
    tas = db.child("users").order_by_child("role").equal_to("applicant").get().val() or {}
    
    return render_template('staff/ta_assignments.html',
                         assignments=assignments,
                         courses=courses,
                         tas=tas)

@staff_bp.route('/reports')
@login_required
@role_required(['staff'])
def reports():
    _, _, db, _ = get_firebase()
    
    # Get statistics for reporting
    stats = {
        'applications_by_department': {},
        'applications_by_status': {},
        'courses_by_department': {},
        'ta_assignments_by_department': {}
    }
    
    # Gather application statistics
    applications = db.child("applications").get().val() or {}
    for app_id, app in applications.items():
        dept = app.get('department', 'Unknown')
        status = app.get('status', 'Unknown')
        stats['applications_by_department'][dept] = stats['applications_by_department'].get(dept, 0) + 1
        stats['applications_by_status'][status] = stats['applications_by_status'].get(status, 0) + 1
    
    # Gather course statistics
    courses = db.child("courses").get().val() or {}
    for course_id, course in courses.items():
        dept = course.get('department', 'Unknown')
        stats['courses_by_department'][dept] = stats['courses_by_department'].get(dept, 0) + 1
    
    return render_template('staff/reports.html', stats=stats)

@staff_bp.route('/notifications', methods=['GET', 'POST'])
@login_required
@role_required(['staff'])
def manage_notifications():
    _, _, db, _ = get_firebase()
    
    if request.method == 'POST':
        try:
            notification_data = {
                "recipient_role": request.form['recipient_role'],
                "recipient_ids": request.form.getlist('recipient_ids'),
                "subject": request.form['subject'],
                "message": request.form['message'],
                "created_by": session['user_id'],
                "created_at": datetime.now().isoformat()
            }
            
            db.child("notifications").push(notification_data)
            flash('Notification sent successfully!', 'success')
            
        except Exception as e:
            flash(f'Error sending notification: {str(e)}', 'error')
    
    # Get all users grouped by role
    users = db.child("users").get().val() or {}
    users_by_role = {}
    for user_id, user in users.items():
        role = user.get('role', 'unknown')
        if role not in users_by_role:
            users_by_role[role] = {}
        users_by_role[role][user_id] = user
    
    return render_template('staff/notifications.html',
                         users_by_role=users_by_role)