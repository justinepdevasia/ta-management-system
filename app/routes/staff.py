# app/routes/staff.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.utils.decorators import login_required, role_required
from app.utils.firebase import get_firebase
from datetime import datetime
import uuid

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

DEPARTMENTS = {
    'cs': 'Computer Science',
    'math': 'Mathematics',
    'physics': 'Physics',
    'eng': 'Engineering',
    'bio': 'Biology',
    'chem': 'Chemistry'
}

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
    
    # Get courses needing TAs with assigned TAs info
    courses_needing_tas = {}
    all_courses = db.child("courses").order_by_child("ta_assigned").equal_to(False).get().val() or {}
    ta_assignments = db.child("ta_assignments").get().val() or {}
    
    for course_id, course in all_courses.items():
        course_tas = [ta for ta in ta_assignments.values() if ta.get('course_id') == course_id]
        course['assigned_tas'] = course_tas
        courses_needing_tas[course_id] = course
    
    # Get instructors for the course input form
    instructors = db.child("users").order_by_child("role").equal_to("instructor").get().val() or {}
    
    return render_template('staff/dashboard.html',
                         stats=stats,
                         recent_applications=recent_applications,
                         courses_needing_tas=courses_needing_tas,
                         departments=DEPARTMENTS,  # Use hardcoded departments
                         instructors=instructors)

@staff_bp.route('/courses', methods=['GET', 'POST'])
@login_required
@role_required(['staff'])
def manage_courses():
    _, _, db, _ = get_firebase()
    
    if request.method == 'POST':
        try:
            department_code = request.form['department']
            course_data = {
                "course_code": request.form['course_code'],
                "name": request.form['name'],
                "department": department_code,
                "department_name": DEPARTMENTS[department_code],
                "semester": request.form.get('semester', 'Fall 2024'),
                "ta_requirements": {
                    "number_needed": int(request.form['number_needed']),
                    "hours_per_week": int(request.form['hours_per_week']),
                    "required_skills": request.form.get('required_skills', '').split(','),
                    "preferred_skills": request.form.get('preferred_skills', '').split(',')
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
    
    # Get all courses and related data
    courses = db.child("courses").get().val() or {}
    instructors = db.child("users").order_by_child("role").equal_to("instructor").get().val() or {}
    ta_assignments = db.child("ta_assignments").get().val() or {}
    
    # Add TA information to courses
    for course_id, course in courses.items():
        course_tas = [ta for ta in ta_assignments.values() if ta.get('course_id') == course_id]
        course['assigned_tas'] = course_tas
    
    return render_template('staff/manage_courses.html',
                         courses=courses,
                         instructors=instructors,
                         departments=DEPARTMENTS)

@staff_bp.route('/course/<course_id>/tas')
@login_required
@role_required(['staff'])
def get_course_tas(course_id):
    _, _, db, _ = get_firebase()
    
    try:
        assignments = db.child("ta_assignments").order_by_child("course_id").equal_to(course_id).get().val() or {}
        
        ta_details = []
        for assignment in assignments.values():
            ta_user = db.child("users").child(assignment.get('user_id')).get().val()
            if ta_user:
                ta_details.append({
                    'name': ta_user.get('name'),
                    'hours_per_week': assignment.get('hours_per_week'),
                    'status': assignment.get('status'),
                    'start_date': assignment.get('start_date'),
                    'end_date': assignment.get('end_date')
                })
        
        return jsonify(ta_details)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@staff_bp.route('/course/<course_id>/assign-ta', methods=['POST'])
@login_required
@role_required(['staff'])
def assign_ta_to_course(course_id):
    _, _, db, _ = get_firebase()
    
    try:
        assignment_data = {
            'course_id': course_id,
            'user_id': request.form['user_id'],
            'hours_per_week': int(request.form['hours_per_week']),
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date'],
            'status': 'Active',
            'assigned_by': session['user_id'],
            'assigned_at': datetime.now().isoformat()
        }
        
        # Create assignment
        db.child("ta_assignments").push(assignment_data)
        
        # Update user role
        db.child("users").child(request.form['user_id']).update({'role': 'ta'})
        
        # Check if course has all needed TAs
        course = db.child("courses").child(course_id).get().val()
        assignments = db.child("ta_assignments").order_by_child("course_id").equal_to(course_id).get().val() or {}
        
        if len(assignments) >= course['ta_requirements']['number_needed']:
            db.child("courses").child(course_id).update({'ta_assigned': True})
        
        flash('TA assigned successfully!', 'success')
        
    except Exception as e:
        flash(f'Error assigning TA: {str(e)}', 'error')
    
    return redirect(url_for('staff.dashboard'))

@staff_bp.route('/course/<course_id>/recommend-tas')
@login_required
@role_required(['staff'])
def recommend_tas(course_id):
    _, _, db, _ = get_firebase()
    
    course = db.child("courses").child(course_id).get().val()
    if not course:
        flash('Course not found.', 'error')
        return redirect(url_for('staff.manage_courses'))
    
    # Get all reviewed applications
    applications = db.child("applications").order_by_child("status").equal_to("Reviewed").get().val() or {}
    
    recommended_tas = []
    required_skills = set(course['ta_requirements'].get('required_skills', []))
    preferred_skills = set(course['ta_requirements'].get('preferred_skills', []))
    
    for app_id, app in applications.items():
        applicant_skills = set(app.get('skills', []))
        required_match = len(required_skills & applicant_skills) / len(required_skills) if required_skills else 1
        preferred_match = len(preferred_skills & applicant_skills) / len(preferred_skills) if preferred_skills else 0
        
        if required_match > 0.7:  # At least 70% match on required skills
            recommendation = {
                'application_id': app_id,
                'applicant_name': app['applicant_name'],
                'required_skills_match': round(required_match * 100, 1),
                'preferred_skills_match': round(preferred_match * 100, 1),
                'overall_score': round((required_match * 0.7 + preferred_match * 0.3) * 100, 1),
                'application': app
            }
            recommended_tas.append(recommendation)
    
    # Sort by overall score
    recommended_tas.sort(key=lambda x: x['overall_score'], reverse=True)
    
    return render_template('staff/recommend_tas.html',
                         course=course,
                         recommendations=recommended_tas)

@staff_bp.route('/applications')
@login_required
@role_required(['staff'])
def view_applications():
    _, _, db, _ = get_firebase()
    
    status_filter = request.args.get('status', 'Submitted')
    department_filter = request.args.get('department', None)
    
    applications = db.child("applications").order_by_child("status").equal_to(status_filter).get().val() or {}
    
    if department_filter:
        applications = {k: v for k, v in applications.items() 
                      if v.get('department') == department_filter}
    
    courses = db.child("courses").get().val() or {}
    
    return render_template('staff/applications.html',
                         applications=applications,
                         courses=courses,
                         departments=DEPARTMENTS,
                         current_status=status_filter,
                         current_department=department_filter)