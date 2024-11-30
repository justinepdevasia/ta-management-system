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
    all_applications = db.child("applications").get().val() or {}
    pending_applications = {k: v for k, v in all_applications.items() if v.get('status') == 'Submitted'}
    reviewed_applications = {k: v for k, v in all_applications.items() if v.get('status') == 'Reviewed'}
    
    stats = {
        'total_applications': len(all_applications),
        'pending_review': len(pending_applications),
        'reviewed': len(reviewed_applications),
        'courses_needing_tas': len(db.child("courses").order_by_child("ta_assigned").equal_to(False).get().val() or {})
    }
    
    # Get recent applications with applicant details
    recent_applications = []
    for app_id, app in all_applications.items():
        if len(recent_applications) >= 5:  # Limit to 5 recent applications
            break
            
        applicant = db.child("users").child(app.get('applicant_id')).get().val()
        if applicant:
            app_data = {
                'id': app_id,
                **app,
                'applicant_name': applicant.get('name'),
                'applicant_email': applicant.get('email')
            }
            recent_applications.append(app_data)
    
    # Get courses needing TAs
    courses = db.child("courses").order_by_child("ta_assigned").equal_to(False).get().val() or {}
    
    # Get course recommendations
    recommendations = db.child("recommendations").get().val() or {}
    
    return render_template('staff/dashboard.html',
                         stats=stats,
                         recent_applications=recent_applications,
                         courses=courses,
                         recommendations=recommendations)

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
            app_data = {
                'id': app_id,
                **app,
                'applicant_name': applicant.get('name'),
                'applicant_email': applicant.get('email')
            }
            
            # Apply filters
            if status_filter != 'all' and app.get('status') != status_filter:
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
                "ta_assigned": False,
                "created_by": session['user_id'],
                "created_at": datetime.now().isoformat()
            }
            
            db.child("courses").push(course_data)
            flash('Course added successfully!', 'success')
            return redirect(url_for('staff.manage_courses'))
            
        except Exception as e:
            flash(f'Error adding course: {str(e)}', 'error')
    
    # Get all courses with department and instructor details
    courses = db.child("courses").get().val() or {}
    departments = db.child("departments").get().val() or {}
    instructors = db.child("users").order_by_child("role").equal_to("instructor").get().val() or {}
    
    return render_template('staff/manage_courses.html',
                         courses=courses,
                         departments=departments,
                         instructors=instructors)

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
    
    # Get all recommendations with application and course details
    recommendations = db.child("recommendations").get().val() or {}
    
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
    
    return render_template('staff/recommendations.html',
                         recommendations=enriched_recommendations)