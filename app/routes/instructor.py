# app/routes/instructor.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.utils.decorators import login_required, role_required
from app.utils.firebase import get_firebase
from datetime import datetime

instructor_bp = Blueprint('instructor', __name__, url_prefix='/instructor')

@instructor_bp.route('/dashboard')
@login_required
@role_required(['instructor'])
def dashboard():
    _, _, db, _ = get_firebase()
    
    # Get instructor's courses
    courses = db.child("courses")\
        .order_by_child("instructor_id")\
        .equal_to(session['user_id'])\
        .get().val() or {}
    
    # Get active TAs for instructor's courses
    ta_assignments = {}
    for course_id in courses.keys():
        assignments = db.child("ta_assignments")\
            .order_by_child("course_id")\
            .equal_to(course_id)\
            .get().val() or {}
        ta_assignments[course_id] = assignments
    
    # Get pending evaluations
    pending_evaluations = db.child("ta_assignments")\
        .order_by_child("evaluation_status")\
        .equal_to("pending")\
        .get().val() or {}
    
    # Filter pending evaluations for instructor's courses
    pending_evaluations = {
        k: v for k, v in pending_evaluations.items()
        if v.get('course_id') in courses
    }
    
    return render_template('instructor/dashboard.html',
                         courses=courses,
                         ta_assignments=ta_assignments,
                         pending_evaluations=pending_evaluations)

@instructor_bp.route('/courses')
@login_required
@role_required(['instructor'])
def view_courses():
    _, _, db, _ = get_firebase()
    
    # Get instructor's courses
    courses = db.child("courses")\
        .order_by_child("instructor_id")\
        .equal_to(session['user_id'])\
        .get().val() or {}
    
    # Get TA information for each course
    for course_id, course in courses.items():
        ta_assignments = db.child("ta_assignments")\
            .order_by_child("course_id")\
            .equal_to(course_id)\
            .get().val() or {}
        course['tas'] = ta_assignments
    
    return render_template('instructor/courses.html',
                         courses=courses)

@instructor_bp.route('/course/<course_id>')
@login_required
@role_required(['instructor'])
def course_details(course_id):
    _, _, db, _ = get_firebase()
    
    # Get course details
    course = db.child("courses").child(course_id).get().val()
    
    if not course or course['instructor_id'] != session['user_id']:
        flash('Course not found.', 'error')
        return redirect(url_for('instructor.view_courses'))
    
    # Get TA assignments for this course
    ta_assignments = db.child("ta_assignments")\
        .order_by_child("course_id")\
        .equal_to(course_id)\
        .get().val() or {}
    
    # Get TA details and evaluations
    tas = {}
    for assignment_id, assignment in ta_assignments.items():
        ta_id = assignment['ta_id']
        ta_info = db.child("users").child(ta_id).get().val() or {}
        evaluations = db.child("evaluations")\
            .child(ta_id)\
            .child(course_id)\
            .get().val() or {}
        
        tas[ta_id] = {
            'info': ta_info,
            'assignment': assignment,
            'evaluations': evaluations
        }
    
    return render_template('instructor/course_details.html',
                         course=course,
                         tas=tas)

@instructor_bp.route('/evaluate/<assignment_id>', methods=['GET', 'POST'])
@login_required
@role_required(['instructor'])
def evaluate_ta(assignment_id):
    _, _, db, _ = get_firebase()
    
    # Get assignment details
    assignment = db.child("ta_assignments").child(assignment_id).get().val()
    
    if not assignment:
        flash('TA assignment not found.', 'error')
        return redirect(url_for('instructor.dashboard'))
    
    # Verify instructor is authorized to evaluate this TA
    course = db.child("courses").child(assignment['course_id']).get().val()
    if not course or course['instructor_id'] != session['user_id']:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('instructor.dashboard'))
    
    if request.method == 'POST':
        try:
            evaluation_data = {
                "performance_rating": int(request.form['performance_rating']),
                "teaching_effectiveness": int(request.form['teaching_effectiveness']),
                "reliability": int(request.form['reliability']),
                "communication": int(request.form['communication']),
                "technical_knowledge": int(request.form['technical_knowledge']),
                "strengths": request.form['strengths'],
                "areas_for_improvement": request.form['areas_for_improvement'],
                "additional_comments": request.form['additional_comments'],
                "recommend_future": request.form.get('recommend_future') == 'yes',
                "evaluator_id": session['user_id'],
                "created_at": datetime.now().isoformat()
            }
            
            # Save evaluation
            db.child("evaluations")\
                .child(assignment['ta_id'])\
                .child(assignment['course_id'])\
                .push(evaluation_data)
            
            # Update assignment status
            db.child("ta_assignments").child(assignment_id).update({
                "evaluation_status": "completed",
                "last_evaluation_date": datetime.now().isoformat()
            })
            
            flash('Evaluation submitted successfully!', 'success')
            return redirect(url_for('instructor.course_details', 
                                  course_id=assignment['course_id']))
            
        except Exception as e:
            flash(f'Error submitting evaluation: {str(e)}', 'error')
    
    # Get TA information
    ta_info = db.child("users").child(assignment['ta_id']).get().val()
    
    return render_template('instructor/evaluate_ta.html',
                         assignment=assignment,
                         course=course,
                         ta=ta_info)

@instructor_bp.route('/ta-performance/<ta_id>')
@login_required
@role_required(['instructor'])
def ta_performance_history(ta_id):
    _, _, db, _ = get_firebase()
    
    # Get all evaluations for this TA in instructor's courses
    instructor_courses = db.child("courses")\
        .order_by_child("instructor_id")\
        .equal_to(session['user_id'])\
        .get().val() or {}
    
    evaluations = {}
    for course_id in instructor_courses.keys():
        course_evaluations = db.child("evaluations")\
            .child(ta_id)\
            .child(course_id)\
            .get().val() or {}
        evaluations[course_id] = course_evaluations
    
    # Get TA information
    ta_info = db.child("users").child(ta_id).get().val()
    
    return render_template('instructor/ta_performance.html',
                         ta=ta_info,
                         evaluations=evaluations,
                         courses=instructor_courses)

@instructor_bp.route('/reports')
@login_required
@role_required(['instructor'])
def view_reports():
    _, _, db, _ = get_firebase()
    
    # Get instructor's courses
    courses = db.child("courses")\
        .order_by_child("instructor_id")\
        .equal_to(session['user_id'])\
        .get().val() or {}
    
    # Compile statistics for each course
    course_stats = {}
    for course_id, course in courses.items():
        # Get TA assignments
        assignments = db.child("ta_assignments")\
            .order_by_child("course_id")\
            .equal_to(course_id)\
            .get().val() or {}
        
        # Calculate statistics
        stats = {
            'total_tas': len(assignments),
            'evaluations_completed': sum(1 for a in assignments.values() 
                                      if a.get('evaluation_status') == 'completed'),
            'average_ratings': {
                'performance': 0,
                'teaching': 0,
                'reliability': 0,
                'communication': 0,
                'technical': 0
            },
            'recommended_future': 0
        }
        
        # Calculate averages from evaluations
        evaluation_count = 0
        for assignment in assignments.values():
            evaluations = db.child("evaluations")\
                .child(assignment['ta_id'])\
                .child(course_id)\
                .get().val() or {}
            
            for eval_data in evaluations.values():
                evaluation_count += 1
                stats['average_ratings']['performance'] += eval_data['performance_rating']
                stats['average_ratings']['teaching'] += eval_data['teaching_effectiveness']
                stats['average_ratings']['reliability'] += eval_data['reliability']
                stats['average_ratings']['communication'] += eval_data['communication']
                stats['average_ratings']['technical'] += eval_data['technical_knowledge']
                if eval_data['recommend_future']:
                    stats['recommended_future'] += 1
        
        if evaluation_count > 0:
            for key in stats['average_ratings']:
                stats['average_ratings'][key] /= evaluation_count
            stats['recommended_future'] = (stats['recommended_future'] / evaluation_count) * 100
        
        course_stats[course_id] = stats
    
    return render_template('instructor/reports.html',
                         courses=courses,
                         course_stats=course_stats)

@instructor_bp.route('/api/ta-hours', methods=['POST'])
@login_required
@role_required(['instructor'])
def update_ta_hours():
    _, _, db, _ = get_firebase()
    
    try:
        assignment_id = request.json['assignment_id']
        hours = float(request.json['hours'])
        week = request.json['week']
        
        # Verify instructor owns this assignment
        assignment = db.child("ta_assignments").child(assignment_id).get().val()
        course = db.child("courses").child(assignment['course_id']).get().val()
        
        if not course or course['instructor_id'] != session['user_id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update hours
        db.child("ta_assignments")\
            .child(assignment_id)\
            .child("hours")\
            .child(week)\
            .set(hours)
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500