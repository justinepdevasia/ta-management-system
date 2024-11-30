# app/routes/committee.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.utils.decorators import login_required, role_required
from app.utils.firebase import get_firebase
from datetime import datetime

committee_bp = Blueprint('committee', __name__, url_prefix='/committee')

@committee_bp.route('/dashboard')
@login_required
@role_required(['committee'])
def dashboard():
    _, _, db, _ = get_firebase()
    
    # Get summary statistics
    applications_pending = db.child("applications").order_by_child("status").equal_to("Reviewed").get().val() or {}
    applications_decided = db.child("applications").order_by_child("status").equal_to("Decided").get().val() or {}
    
    stats = {
        'pending_review': len(applications_pending),
        'decisions_made': len(applications_decided),
        'total_applications': len(applications_pending) + len(applications_decided)
    }
    
    # Get recent applications that need committee review
    recent_applications = db.child("applications")\
        .order_by_child("status")\
        .equal_to("Reviewed")\
        .limit_to_last(5)\
        .get().val() or {}
    
    return render_template('committee/dashboard.html',
                         stats=stats,
                         recent_applications=recent_applications)

@committee_bp.route('/applications')
@login_required
@role_required(['committee'])
def view_applications():
    _, _, db, _ = get_firebase()
    
    # Get filter parameters
    status = request.args.get('status', 'Reviewed')
    department = request.args.get('department')
    semester = request.args.get('semester')
    
    # Get applications based on filters
    applications = db.child("applications").order_by_child("status").equal_to(status).get().val() or {}
    
    # Apply additional filters
    if department or semester:
        filtered_applications = {}
        for app_id, app in applications.items():
            if department and app.get('department') != department:
                continue
            if semester and app.get('semester') != semester:
                continue
            filtered_applications[app_id] = app
        applications = filtered_applications
    
    # Get related data
    courses = db.child("courses").get().val() or {}
    departments = db.child("departments").get().val() or {}
    
    return render_template('committee/applications.html',
                         applications=applications,
                         courses=courses,
                         departments=departments,
                         current_filters={
                             'status': status,
                             'department': department,
                             'semester': semester
                         })

@committee_bp.route('/application/<application_id>', methods=['GET', 'POST'])
@login_required
@role_required(['committee'])
def review_application(application_id):
    _, _, db, _ = get_firebase()
    
    if request.method == 'POST':
        try:
            # Get form data
            decision = request.form['decision']
            assigned_courses = request.form.getlist('assigned_courses')
            comments = request.form['comments']
            
            # Prepare decision data
            decision_data = {
                "committee_member_id": session['user_id'],
                "decision": decision,
                "assigned_courses": assigned_courses,
                "comments": comments,
                "created_at": datetime.now().isoformat()
            }
            
            # Update application with decision
            db.child("applications").child(application_id).update({
                "status": "Decided",
                "decision": decision,
                "committee_decision": decision_data,
                "updated_at": datetime.now().isoformat()
            })
            
            # If approved, create TA assignments
            if decision == 'approved':
                for course_id in assigned_courses:
                    assignment_data = {
                        "application_id": application_id,
                        "course_id": course_id,
                        "ta_id": db.child("applications").child(application_id).get().val()['applicant_id'],
                        "status": "Pending",
                        "assigned_by": session['user_id'],
                        "assigned_at": datetime.now().isoformat()
                    }
                    db.child("ta_assignments").push(assignment_data)
            
            flash('Decision recorded successfully!', 'success')
            return redirect(url_for('committee.view_applications'))
            
        except Exception as e:
            flash(f'Error recording decision: {str(e)}', 'error')
    
    # Get application data
    application = db.child("applications").child(application_id).get().val()
    if not application:
        flash('Application not found.', 'error')
        return redirect(url_for('committee.view_applications'))
    
    # Get related data
    courses = db.child("courses").get().val() or {}
    applicant = db.child("users").child(application['applicant_id']).get().val() or {}
    staff_review = application.get('staff_review', {})
    
    return render_template('committee/review_application.html',
                         application=application,
                         courses=courses,
                         applicant=applicant,
                         staff_review=staff_review)

@committee_bp.route('/meetings')
@login_required
@role_required(['committee'])
def meetings():
    _, _, db, _ = get_firebase()
    
    # Get upcoming and past meetings
    meetings = db.child("committee_meetings").get().val() or {}
    
    # Split meetings into upcoming and past
    upcoming_meetings = {}
    past_meetings = {}
    current_date = datetime.now()
    
    for meeting_id, meeting in meetings.items():
        meeting_date = datetime.fromisoformat(meeting['date'])
        if meeting_date > current_date:
            upcoming_meetings[meeting_id] = meeting
        else:
            past_meetings[meeting_id] = meeting
    
    return render_template('committee/meetings.html',
                         upcoming_meetings=upcoming_meetings,
                         past_meetings=past_meetings)

@committee_bp.route('/meeting/<meeting_id>', methods=['GET', 'POST'])
@login_required
@role_required(['committee'])
def meeting_details(meeting_id):
    _, _, db, _ = get_firebase()
    
    if request.method == 'POST':
        try:
            # Update meeting notes
            notes = request.form['notes']
            decisions = request.form.getlist('decisions')
            
            update_data = {
                "notes": notes,
                "decisions": decisions,
                "updated_by": session['user_id'],
                "updated_at": datetime.now().isoformat()
            }
            
            db.child("committee_meetings").child(meeting_id).update(update_data)
            flash('Meeting notes updated successfully!', 'success')
            
        except Exception as e:
            flash(f'Error updating meeting notes: {str(e)}', 'error')
    
    # Get meeting data
    meeting = db.child("committee_meetings").child(meeting_id).get().val()
    
    if not meeting:
        flash('Meeting not found.', 'error')
        return redirect(url_for('committee.meetings'))
    
    # Get applications to be reviewed in this meeting
    applications_for_review = db.child("applications")\
        .order_by_child("status")\
        .equal_to("Reviewed")\
        .get().val() or {}
    
    return render_template('committee/meeting_details.html',
                         meeting=meeting,
                         applications=applications_for_review)

@committee_bp.route('/reports')
@login_required
@role_required(['committee'])
def reports():
    _, _, db, _ = get_firebase()
    
    # Generate committee decision statistics
    decisions = db.child("applications")\
        .order_by_child("status")\
        .equal_to("Decided")\
        .get().val() or {}
    
    stats = {
        'total_decisions': len(decisions),
        'approvals': sum(1 for d in decisions.values() if d.get('decision') == 'approved'),
        'rejections': sum(1 for d in decisions.values() if d.get('decision') == 'rejected'),
        'by_department': {},
        'by_semester': {}
    }
    
    # Calculate departmental and semester statistics
    for decision in decisions.values():
        dept = decision.get('department', 'Unknown')
        semester = decision.get('semester', 'Unknown')
        
        if dept not in stats['by_department']:
            stats['by_department'][dept] = {'approved': 0, 'rejected': 0}
        if semester not in stats['by_semester']:
            stats['by_semester'][semester] = {'approved': 0, 'rejected': 0}
        
        decision_type = 'approved' if decision.get('decision') == 'approved' else 'rejected'
        stats['by_department'][dept][decision_type] += 1
        stats['by_semester'][semester][decision_type] += 1
    
    return render_template('committee/reports.html', stats=stats)

# API endpoints for AJAX requests
@committee_bp.route('/api/application-status', methods=['POST'])
@login_required
@role_required(['committee'])
def update_application_status():
    _, _, db, _ = get_firebase()
    
    try:
        application_id = request.json['application_id']
        new_status = request.json['status']
        
        if new_status not in ['Reviewed', 'Decided']:
            return jsonify({'error': 'Invalid status'}), 400
        
        db.child("applications").child(application_id).update({
            "status": new_status,
            "updated_by": session['user_id'],
            "updated_at": datetime.now().isoformat()
        })
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500