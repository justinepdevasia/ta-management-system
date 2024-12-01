from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.utils.decorators import login_required, role_required
from app.utils.firebase import get_firebase
from datetime import datetime, timedelta

committee_bp = Blueprint('committee', __name__, url_prefix='/committee')

@committee_bp.route('/dashboard')
@login_required
@role_required(['committee'])
def dashboard():
    _, _, db, _ = get_firebase()
    
    # Get courses needing TAs
    courses = db.child("courses").get().val() or {}
    courses_needing_tas = {k: v for k, v in courses.items() 
                          if int(v.get('ta_requirements', {}).get('number_needed', 0)) > 
                             len(db.child("ta_assignments").order_by_child("course_id").equal_to(k).get().val() or {})}
    
    # Get recent TA decisions
    recent_decisions = db.child("applications")\
        .order_by_child("status")\
        .start_at("Selected")\
        .end_at("Selected\uf8ff")\
        .limit_to_last(5)\
        .get().val() or {}
    
    stats = {
        'courses_needing_tas': len(courses_needing_tas),
        'pending_decisions': len([d for d in recent_decisions.values() if d['status'] == 'Selected']),
        'accepted_offers': len([d for d in recent_decisions.values() if d['status'] == 'Accepted']),
        'rejected_offers': len([d for d in recent_decisions.values() if d['status'] == 'Rejected'])
    }
    
    return render_template('committee/dashboard.html',
                         stats=stats,
                         courses=courses_needing_tas,
                         recent_decisions=recent_decisions)

@committee_bp.route('/courses')
@login_required
@role_required(['committee'])
def view_courses():
    _, _, db, _ = get_firebase()
    
    department = request.args.get('department')
    semester = request.args.get('semester')
    
    # Get all courses with their TA requirements and current assignments
    courses = db.child("courses").get().val() or {}
    
    # Apply filters if provided
    if department or semester:
        filtered_courses = {}
        for course_id, course in courses.items():
            if department and course.get('department') != department:
                continue
            if semester and course.get('semester') != semester:
                continue
            filtered_courses[course_id] = course
        courses = filtered_courses
    
    # Enrich course data with current TA assignments and recommendations
    for course_id, course in courses.items():
        # Get current TA assignments
        assignments = db.child("ta_assignments")\
            .order_by_child("course_id")\
            .equal_to(course_id)\
            .get().val() or {}
        course['current_tas'] = len(assignments)
        
        # Get recommendations for this course
        recommendations = db.child("recommendations")\
            .order_by_child("course_id")\
            .equal_to(course_id)\
            .get().val() or {}
        course['recommendation_count'] = len(recommendations)
    
    departments = db.child("departments").get().val() or {}
    
    return render_template('committee/courses.html',
                         courses=courses,
                         departments=departments)

@committee_bp.route('/course/<course_id>/select-ta/<application_id>', methods=['POST'])
@login_required
@role_required(['committee'])
def select_ta(course_id, application_id):
    _, _, db, _ = get_firebase()
    
    try:
        # Verify course exists and needs TAs
        course = db.child("courses").child(course_id).get().val()
        if not course:
            flash('Course not found.', 'error')
            return redirect(url_for('committee.course_recommendations', course_id=course_id))
        
        current_assignments = db.child("ta_assignments")\
            .order_by_child("course_id")\
            .equal_to(course_id)\
            .get().val() or {}
            
        if len(current_assignments) >= int(course['ta_requirements']['number_needed']):
            flash('Course has reached maximum number of TAs.', 'error')
            return redirect(url_for('committee.course_recommendations', course_id=course_id))
        
        # Get application
        application = db.child("applications").child(application_id).get().val()
        if not application:
            flash('Application not found.', 'error')
            return redirect(url_for('committee.course_recommendations', course_id=course_id))
        
        # Update application status
        db.child("applications").child(application_id).update({
            "status": "Selected",
            "selected_by": session['user_id'],
            "selected_date": datetime.now().isoformat(),
            "response_due_date": (datetime.now() + timedelta(days=7)).isoformat()
        })
        
        # Create TA assignment
        assignment_data = {
            "course_id": course_id,
            "application_id": application_id,
            "ta_id": application.get('applicant_id'),
            "status": "Pending",
            "assigned_by": session['user_id'],
            "assigned_at": datetime.now().isoformat()
        }
        
        db.child("ta_assignments").push(assignment_data)
        
        flash('TA selected successfully. Waiting for applicant response.', 'success')
        return redirect(url_for('committee.course_recommendations', course_id=course_id))
        
    except Exception as e:
        flash(f'Error selecting TA: {str(e)}', 'error')
        return redirect(url_for('committee.course_recommendations', course_id=course_id))

@committee_bp.route('/decisions')
@login_required
@role_required(['committee'])
def view_decisions():
    _, _, db, _ = get_firebase()
    
    # Get all applications with decisions
    applications = db.child("applications")\
        .order_by_child("status")\
        .start_at("Selected")\
        .get().val() or {}
    
    # Enrich application data
    enriched_applications = []
    for app_id, app in applications.items():
        applicant = db.child("users").child(app['applicant_id']).get().val()
        course = db.child("courses").child(app['course_id']).get().val()
        
        if applicant and course:
            enriched_applications.append({
                'id': app_id,
                **app,
                'applicant_name': applicant.get('name'),
                'applicant_email': applicant.get('email'),
                'course_code': course.get('course_code'),
                'course_name': course.get('name')
            })
    
    return render_template('committee/decisions.html',
                         applications=enriched_applications)

@committee_bp.route('/api/select-ta', methods=['POST'])
@login_required
@role_required(['committee'])
def api_select_ta():
    _, _, db, _ = get_firebase()
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
            
        course_id = data.get('course_id')
        application_id = data.get('application_id')
        
        if not course_id or not application_id:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Get course and application details
        course = db.child("courses").child(course_id).get().val()
        application = db.child("applications").child(application_id).get().val()
        
        if not course or not application:
            return jsonify({'success': False, 'error': 'Course or application not found'}), 404
        
        # Verify course needs TAs
        current_assignments = db.child("ta_assignments")\
            .order_by_child("course_id")\
            .equal_to(course_id)\
            .get().val() or {}
            
        ta_requirements = course.get('ta_requirements', {})
        number_needed = int(ta_requirements.get('number_needed', 1))
        
        if len(current_assignments) >= number_needed:
            return jsonify({
                'success': False,
                'error': f'Course already has maximum number of TAs ({number_needed})'
            }), 400
        
        # Verify application status is appropriate
        if application.get('status') in ['Selected', 'Accepted', 'Rejected']:
            return jsonify({
                'success': False,
                'error': f'Application is already in {application.get("status")} status'
            }), 400
        
        # Update application status
        update_data = {
            "status": "Selected",
            "selected_by": session['user_id'],
            "selected_date": datetime.now().isoformat(),
            "response_due_date": (datetime.now() + timedelta(days=7)).isoformat()
        }
        
        db.child("applications").child(application_id).update(update_data)
        
        # Create TA assignment
        assignment_data = {
            "course_id": course_id,
            "application_id": application_id,
            "ta_id": application.get('applicant_id'),
            "status": "Pending",
            "assigned_by": session['user_id'],
            "assigned_at": datetime.now().isoformat()
        }
        
        db.child("ta_assignments").push(assignment_data)
        
        return jsonify({
            'success': True,
            'message': 'TA selected successfully'
        })
        
    except Exception as e:
        print(f"Error selecting TA: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }), 500

@committee_bp.route('/api/application/<application_id>', methods=['GET'])
@login_required
@role_required(['committee'])
def api_get_application(application_id):
    _, _, db, _ = get_firebase()
    
    try:
        # Get application details
        application = db.child("applications").child(application_id).get().val()
        if not application:
            return jsonify({'error': 'Application not found'}), 404
        
        # Get applicant details
        applicant = db.child("users").child(application.get('applicant_id')).get().val()
        if not applicant:
            return jsonify({'error': 'Applicant not found'}), 404
        
        # Format previous experience
        previous_experience = ""
        if application.get('previous_experience'):
            previous_courses = application.get('previous_courses', [])
            previous_dates = application.get('previous_dates', [])
            for i in range(len(previous_courses)):
                previous_experience += f"<div class='mb-2'>"
                previous_experience += f"<p class='font-medium'>{previous_courses[i]}</p>"
                previous_experience += f"<p class='text-sm text-gray-600'>{previous_dates[i]}</p>"
                previous_experience += "</div>"
        
        # Prepare response data
        response_data = {
            'applicant_name': applicant.get('name'),
            'applicant_email': applicant.get('email'),
            'gpa': application.get('gpa'),
            'previous_experience': previous_experience,
            'additional_info': application.get('additional_skills', ''),
            'research_interests': application.get('research_interests', ''),
            'cv_url': application.get('cv_url', ''),
            'status': application.get('status'),
            'submission_date': application.get('submission_date')
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@committee_bp.route('/course/<course_id>/recommendations')
@login_required
@role_required(['committee'])
def course_recommendations(course_id):
    _, _, db, _ = get_firebase()
    
    try:
        # Get course details and include the ID
        course = db.child("courses").child(course_id).get().val()
        if not course:
            flash('Course not found.', 'error')
            return redirect(url_for('committee.view_courses'))
            
        # Add the course_id to the course object
        course['id'] = course_id
        
        # Get current TA assignments
        current_assignments = db.child("ta_assignments")\
            .order_by_child("course_id")\
            .equal_to(course_id)\
            .get().val() or {}
            
        # Get recommendations
        try:
            recommendations = db.child("recommendations")\
                .order_by_child("course_id")\
                .equal_to(course_id)\
                .get().val() or {}
        except:
            all_recommendations = db.child("recommendations").get().val() or {}
            recommendations = {
                k: v for k, v in all_recommendations.items()
                if v.get('course_id') == course_id
            }
            
        # Enrich recommendations with applicant data
        enriched_recommendations = []
        for rec_id, rec in recommendations.items():
            # Make sure we have the application_id in the recommendation
            application_id = rec.get('application_id')
            if not application_id:
                continue
                
            application = db.child("applications").child(application_id).get().val()
            if application:
                applicant = db.child("users").child(application['applicant_id']).get().val() if application else None
                
                if applicant:
                    # Skip if applicant is already assigned to this course
                    if any(a.get('ta_id') == application['applicant_id'] for a in current_assignments.values()):
                        continue
                        
                    enriched_recommendations.append({
                        'id': rec_id,
                        **rec,
                        'applicant_name': applicant.get('name'),
                        'applicant_email': applicant.get('email'),
                        'application_id': application_id,  # Use the original application_id from recommendation
                        'application_status': application.get('status'),
                        'gpa': application.get('gpa'),
                        'evaluation_scores': rec.get('evaluation_scores', {}),
                        'reviewer_name': rec.get('reviewer_name', 'Unknown Reviewer')
                    })
        
        # Sort recommendations by average evaluation score
        for rec in enriched_recommendations:
            scores = rec.get('evaluation_scores', {})
            rec['average_score'] = sum(scores.values()) / len(scores) if scores else 0
            
        enriched_recommendations.sort(key=lambda x: x['average_score'], reverse=True)
        
        return render_template('committee/course_recommendations.html',
                             course=course,
                             recommendations=enriched_recommendations,
                             current_assignments=current_assignments)
                             
    except Exception as e:
        flash(f'Error loading recommendations: {str(e)}', 'error')
        return redirect(url_for('committee.view_courses'))

@committee_bp.route('/reports')
@login_required
@role_required(['committee'])
def reports():
    _, _, db, _ = get_firebase()
    
    # Initialize stats dictionary with default values
    stats = {
        'by_department': {},
        'by_semester': {},
        'response_times': [],
        'acceptance_rate': 0,
        'total_selected': 0,
        'total_accepted': 0,
        'total_rejected': 0,
        'avg_response_time': 0,  # Initialize with default value
        'response_time_distribution': {
            'quick': 0,    # < 2 days
            'normal': 0,   # 2-5 days
            'delayed': 0   # > 5 days
        }
    }
    
    try:
        # Get all applications with decisions
        applications = db.child("applications")\
            .order_by_child("status")\
            .start_at("Selected")\
            .get().val() or {}
        
        response_times = []
        
        for app_id, app in applications.items():
            # Count total selections
            if app['status'] in ['Selected', 'Accepted', 'Rejected']:
                stats['total_selected'] += 1
            
            # Count acceptances and rejections
            if app['status'] == 'Accepted':
                stats['total_accepted'] += 1
            elif app['status'] == 'Rejected':
                stats['total_rejected'] += 1
            
            # Calculate response time if available
            if app.get('selected_date') and app.get('response_date'):
                try:
                    selected_date = datetime.fromisoformat(app['selected_date'])
                    response_date = datetime.fromisoformat(app['response_date'])
                    response_time = (response_date - selected_date).days
                    response_times.append(response_time)
                    
                    # Categorize response time
                    if response_time < 2:
                        stats['response_time_distribution']['quick'] += 1
                    elif response_time <= 5:
                        stats['response_time_distribution']['normal'] += 1
                    else:
                        stats['response_time_distribution']['delayed'] += 1
                except (ValueError, TypeError):
                    continue
            
            # Get course info for department and semester stats
            course = db.child("courses").child(app.get('course_id')).get().val() or {}
            dept = course.get('department', 'Unknown')
            semester = course.get('semester', 'Unknown')
            
            # Initialize department stats if needed
            if dept not in stats['by_department']:
                stats['by_department'][dept] = {'selected': 0, 'accepted': 0, 'rejected': 0}
            if semester not in stats['by_semester']:
                stats['by_semester'][semester] = {'selected': 0, 'accepted': 0, 'rejected': 0}
            
            # Update department and semester stats
            if app['status'] in ['Selected', 'Accepted', 'Rejected']:
                stats['by_department'][dept]['selected'] += 1
                stats['by_semester'][semester]['selected'] += 1
                
                if app['status'] == 'Accepted':
                    stats['by_department'][dept]['accepted'] += 1
                    stats['by_semester'][semester]['accepted'] += 1
                elif app['status'] == 'Rejected':
                    stats['by_department'][dept]['rejected'] += 1
                    stats['by_semester'][semester]['rejected'] += 1
        
        # Calculate averages and rates
        if stats['total_selected'] > 0:
            stats['acceptance_rate'] = (stats['total_accepted'] / stats['total_selected']) * 100
        
        if response_times:
            stats['avg_response_time'] = sum(response_times) / len(response_times)
            stats['response_times'] = response_times
        
        # Sort semester data chronologically
        stats['by_semester'] = dict(sorted(stats['by_semester'].items()))
        
    except Exception as e:
        flash(f'Error generating reports: {str(e)}', 'error')
        # Initialize default values in case of error
        stats.update({
            'acceptance_rate': 0,
            'avg_response_time': 0,
            'total_selected': 0,
            'total_accepted': 0,
            'total_rejected': 0
        })
    
    return render_template('committee/reports.html', stats=stats)
    _, _, db, _ = get_firebase()
    
    # Generate statistics for committee decisions and responses
    stats = {
        'by_department': {},
        'by_semester': {},
        'response_times': [],
        'acceptance_rate': 0,
        'total_selected': 0,
        'total_accepted': 0,
        'total_rejected': 0
    }
    
    # Get all applications with decisions
    applications = db.child("applications")\
        .order_by_child("status")\
        .start_at("Selected")\
        .get().val() or {}
    
    for app in applications.values():
        stats['total_selected'] += 1
        if app['status'] == 'Accepted':
            stats['total_accepted'] += 1
        elif app['status'] == 'Rejected':
            stats['total_rejected'] += 1
        
        # Calculate response time if available
        if app.get('selected_date') and app.get('response_date'):
            selected_date = datetime.fromisoformat(app['selected_date'])
            response_date = datetime.fromisoformat(app['response_date'])
            response_time = (response_date - selected_date).days
            stats['response_times'].append(response_time)
        
        # Aggregate by department and semester
        course = db.child("courses").child(app['course_id']).get().val()
        if course:
            dept = course.get('department', 'Unknown')
            semester = course.get('semester', 'Unknown')
            
            if dept not in stats['by_department']:
                stats['by_department'][dept] = {'selected': 0, 'accepted': 0, 'rejected': 0}
            if semester not in stats['by_semester']:
                stats['by_semester'][semester] = {'selected': 0, 'accepted': 0, 'rejected': 0}
            
            stats['by_department'][dept]['selected'] += 1
            stats['by_semester'][semester]['selected'] += 1
            
            if app['status'] == 'Accepted':
                stats['by_department'][dept]['accepted'] += 1
                stats['by_semester'][semester]['accepted'] += 1
            elif app['status'] == 'Rejected':
                stats['by_department'][dept]['rejected'] += 1
                stats['by_semester'][semester]['rejected'] += 1
    
    # Calculate acceptance rate
    if stats['total_selected'] > 0:
        stats['acceptance_rate'] = (stats['total_accepted'] / stats['total_selected']) * 100
    
    # Calculate average response time
    if stats['response_times']:
        stats['avg_response_time'] = sum(stats['response_times']) / len(stats['response_times'])
    
    return render_template('committee/reports.html', stats=stats)