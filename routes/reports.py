"""routes/reports.py — PDF report generation + health score"""
from flask import Blueprint, render_template, request, session, send_file, redirect, url_for, jsonify
from datetime import datetime
import json, os
from models import db, HealthScore, User

reports_bp = Blueprint("reports", __name__)

@reports_bp.route("/report")
def report():
    return render_template("report.html",
        predictions=session.get("predictions", []),
        severity=session.get("severity", {}),
        top_disease=session.get("top_disease", ""),
        extracted_symptoms=session.get("extracted_symptoms", []),
        intensity=session.get("intensity", "MEDIUM"),
        duration=session.get("duration", "HOURS"),
        booking_id=session.get("booking_id"),
        booking_doctor=session.get("booking_doctor"),
        booking_department=session.get("booking_department"),
        booking_date=session.get("booking_date"),
        booking_time=session.get("booking_time"),
        booking_hospital=session.get("booking_hospital"),
    )

@reports_bp.route("/download-pdf")
def download_pdf():
    from utils.pdf_generator import generate_report
    import config
    predictions = session.get("predictions", [])
    severity    = session.get("severity", {})
    # Build data dict
    data = {
        "patient_name":     session.get("name", "Guest"),
        "phone":            session.get("phone", "N/A"),
        "symptoms_text":    session.get("symptoms_text", ""),
        "extracted_symptoms": session.get("extracted_symptoms", []),
        "predictions":      predictions,
        "severity_level":   severity.get("level", "MILD"),
        "intensity":        session.get("intensity", "MEDIUM"),
        "duration":         session.get("duration", "HOURS"),
        "precautions":      severity.get("precautions", []),
        "department":       severity.get("department", "General Physician"),
        "description":      severity.get("description", ""),
        "hospital_name":    session.get("booking_hospital", ""),
        "doctor_name":      session.get("booking_doctor", ""),
        "appointment_date": session.get("booking_date", ""),
        "appointment_time": session.get("booking_time", ""),
        "booking_id":       session.get("booking_id", ""),
    }
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
    os.makedirs(reports_dir, exist_ok=True)
    fname = f"arogyaai_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    path  = os.path.join(reports_dir, fname)
    generate_report(data, path)
    return send_file(path, as_attachment=True, download_name=fname)

@reports_bp.route("/health-score", methods=["GET", "POST"])
def health_score():
    if request.method == "POST":
        # Get ALL fields
        answers = {
            "allergies":         request.form.get("allergies", "").strip(),
            "chronic_conditions": request.form.get("chronic_conditions", "").strip(),
            "past_surgeries":     request.form.get("past_surgeries", "").strip(),
            "smoke":             request.form.get("smoke", "no"),
            "exercise":          request.form.get("exercise", "no"),
            "sleep":             request.form.get("sleep", "no"),
            "water":             request.form.get("water", "no"),
            "vegetables":        request.form.get("vegetables", "no"),
            "stress":            int(request.form.get("stress", 5)),
            "age":               request.form.get("age", ""),
            "weight":            request.form.get("weight", ""),
        }
        
        # Scoring Logic (Max 100)
        score = 100
        
        # Lifestyle Penalties
        if answers["smoke"] == "yes":     score -= 15
        if answers["exercise"] == "no":   score -= 10
        if answers["sleep"] == "no":      score -= 5
        if answers["water"] == "no":      score -= 5
        if answers["vegetables"] == "no": score -= 5
        
        # Stress Impact
        if answers["stress"] > 7:   score -= 10
        elif answers["stress"] > 4: score -= 5
        
        # Medical History Penalties
        if answers["allergies"]:         score -= 5
        if answers["chronic_conditions"]: score -= 15
        if answers["past_surgeries"]:     score -= 5
        
        user_id = session.get("user_id")
        if user_id:
            # Check Recent Symptoms for impact
            from models import SymptomLog
            recent_symptom = SymptomLog.query.filter_by(user_id=user_id).order_by(SymptomLog.created_at.desc()).first()
            if recent_symptom and recent_symptom.intensity == 'HIGH':
                score -= 10
        
        score = max(0, min(100, score))

        if user_id:
            hs = HealthScore(user_id=user_id, score=score, answers=json.dumps(answers))
            db.session.add(hs)
            db.session.commit()

        # History for graph
        history = []
        if user_id:
            records = db.session.execute(db.select(HealthScore).filter_by(user_id=user_id).order_by(HealthScore.created_at)).scalars().all()
            history = [{"date": r.created_at.strftime("%d %b"), "score": r.score} for r in records]

        return render_template("health_score.html",
            result=True, score=score, answers=answers, history=history)

    return render_template("health_score.html", result=False)

@reports_bp.route("/severity-page")
def severity_page():
    severity = session.get("severity", {})
    predictions = session.get("predictions", [])
    top_disease = session.get("top_disease", "")
    extracted   = session.get("extracted_symptoms", [])
    emergency_contact = session.get("emergency_contact")
    print(f"DEBUG: Session contact: {emergency_contact}")
    
    user_id = session.get("user_id")
    if not emergency_contact and user_id:
        user = db.session.get(User, user_id)
        if user: 
            emergency_contact = user.emergency_contact
            session["emergency_contact"] = emergency_contact
            print(f"DEBUG: DB contact found: {emergency_contact}")
            
    return render_template("severity.html",
        severity=severity,
        severity_val=severity.get("level", "MILD"),
        dept_val=severity.get("department", "General Medicine"),
        precs_val=severity.get("precautions", []),
        predictions=predictions,
        top_disease=top_disease, extracted_symptoms=extracted,
        emergency_contact=emergency_contact)

@reports_bp.route("/send-alert", methods=["POST"])
def send_alert():
    from utils.sms_sender import send_critical_alert
    user_id = session.get("user_id")
    emergency_contact = session.get("emergency_contact")
    
    if not emergency_contact and user_id:
        user = db.session.get(User, user_id)
        if user: 
            emergency_contact = user.emergency_contact
            session["emergency_contact"] = emergency_contact
    
    print(f"DEBUG: send_alert contact: {emergency_contact}")
    
    if not emergency_contact:
        return jsonify({"status": "no_contact"})
        
    predictions = session.get("predictions", [])
    top_disease = session.get("top_disease", "")
    extracted   = session.get("extracted_symptoms", [])
    
    top_prob = 0
    if predictions:
        top_prob = predictions[0].get("percent", 0)
        
    result = send_critical_alert(emergency_contact, extracted, top_disease, top_prob)
    return jsonify(result)
