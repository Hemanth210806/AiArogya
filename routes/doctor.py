"""
routes/doctor.py — Doctor login, dashboard, and prescriptions
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, Doctor, Booking, Slot, Prescription, PrescriptionMedicine, AnalysisHistory, User, Department
from werkzeug.security import generate_password_hash, check_password_hash
from utils.notifications import create_notification
import json
from datetime import datetime

doctor_bp = Blueprint("doctor", __name__, url_prefix="/doctor")

@doctor_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        doctor = Doctor.query.filter_by(email=email).first()
        if doctor and check_password_hash(doctor.password_hash, password):
            session["doctor_id"] = doctor.id
            session["doctor_name"] = doctor.name
            session["is_doctor"] = True
            return redirect(url_for("doctor.dashboard"))
        flash("Invalid email or password", "error")
    return render_template("doctor_login.html")

@doctor_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        dept_id = request.form.get("department_id")
        
        # Check if exists
        existing = Doctor.query.filter_by(email=email).first()
        if existing:
            flash("Email already registered", "error")
            return redirect(url_for("doctor.register"))
            
        dept = db.session.get(Department, int(dept_id))
        experience = request.form.get("experience", 5)
        fee = request.form.get("consultation_fee", 500)
        
        new_doctor = Doctor(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            department_id=int(dept_id),
            specialization=f"{dept.name} Specialist" if dept else "Specialist",
            is_verified=True,
            is_available=True,
            dept=dept.name if dept else "General Medicine", # Legacy
            consultation_fee=int(fee),
            experience_years=int(experience)
        )
        db.session.add(new_doctor)
        db.session.commit()
        
        # Seed initial slots for the next 3 days
        from datetime import datetime, timedelta
        times = ["09:00 AM", "10:00 AM", "11:00 AM", "02:00 PM", "03:00 PM", "04:00 PM"]
        for i in range(3):
            date_str = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
            for t in times:
                s = Slot(doctor_id=new_doctor.id, date=date_str, time=t, is_booked=False)
                db.session.add(s)
        db.session.commit()
        
        flash("Registration successful! You are now available for bookings for the next 3 days.", "success")
        return redirect(url_for("doctor.login"))
        
    departments = Department.query.all()
    return render_template("doctor_register.html", departments=departments)

@doctor_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("doctor.login"))

@doctor_bp.route("/dashboard")
def dashboard():
    doctor_id = session.get("doctor_id")
    if not doctor_id: return redirect(url_for("doctor.login"))
    
    doctor = db.session.get(Doctor, doctor_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Get today's appointments
    today_appointments = Booking.query.join(Slot).filter(
        Slot.doctor_id == doctor_id,
        Slot.date == today
    ).order_by(Slot.time).all()
    
    # Get upcoming appointments (Future)
    upcoming_appointments = Booking.query.join(Slot).filter(
        Slot.doctor_id == doctor_id,
        Slot.date > today
    ).order_by(Slot.date, Slot.time).all()
    
    # Earnings (simple sum of fees for booked slots)
    total_consultations = Booking.query.join(Slot).filter(Slot.doctor_id == doctor_id).count()
    earnings = total_consultations * (doctor.consultation_fee or 500)

    return render_template("doctor_dashboard.html", 
        doctor=doctor, 
        appointments=today_appointments,
        upcoming=upcoming_appointments,
        today=today,
        total_consultations=total_consultations,
        earnings=earnings
    )

@doctor_bp.route("/toggle-availability", methods=["POST"])
def toggle_availability():
    doctor_id = session.get("doctor_id")
    if not doctor_id: return jsonify({"status": "error"}), 403
    
    doctor = db.session.get(Doctor, doctor_id)
    doctor.is_available = not doctor.is_available
    db.session.commit()
    
    if doctor.is_available:
        # Notify all patients with appointments today
        today = datetime.now().strftime("%Y-%m-%d")
        appointments = Booking.query.join(Slot).filter(Slot.doctor_id == doctor_id, Slot.date == today).all()
        for appt in appointments:
            create_notification(
                user_id=appt.user_id,
                message=f"Dr. {doctor.name} has arrived and is now available. Your appointment is at {appt.slot.time}.",
                n_type="doctor_arrived"
            )
            
    return jsonify({"status": "success", "is_available": doctor.is_available})

@doctor_bp.route("/patient-report/<int:user_id>/<int:booking_id>")
def patient_report(user_id, booking_id):
    if not session.get("is_doctor"): return redirect(url_for("doctor.login"))
    
    user = db.session.get(User, user_id)
    booking = db.session.get(Booking, booking_id)
    history = AnalysisHistory.query.filter_by(user_id=user_id).order_by(AnalysisHistory.created_at.desc()).limit(5).all()
    
    return render_template("doctor_patient_view.html", user=user, booking=booking, history=history)

@doctor_bp.route("/prescribe", methods=["POST"])
def prescribe():
    if not session.get("is_doctor"): return jsonify({"status": "error"}), 403
    
    data = request.json
    doctor_id = session.get("doctor_id")
    patient_id = data.get("patient_id")
    appointment_id = data.get("appointment_id")
    
    prescription = Prescription(
        appointment_id=appointment_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        diagnosis=data.get("diagnosis"),
        instructions=data.get("instructions"),
        follow_up_date=data.get("follow_up_date")
    )
    db.session.add(prescription)
    db.session.flush() # Get prescription ID
    
    for med in data.get("medicines", []):
        m_name = med.get("name")
        new_med = PrescriptionMedicine(
            prescription_id=prescription.id,
            medicine_name=m_name,
            dosage=med.get("dosage"),
            frequency=med.get("frequency"),
            duration=med.get("duration"),
            buy_link=f"https://www.1mg.com/search/all?name={m_name.replace(' ', '+')}"
        )
        db.session.add(new_med)
    
    db.session.commit()
    
    # Notify patient
    doctor_name = session.get("doctor_name")
    create_notification(
        user_id=patient_id,
        message=f"Dr. {doctor_name} has prescribed you medicines. Click to view and buy online.",
        n_type="prescription"
    )
    
    return jsonify({"status": "success", "prescription_id": prescription.id})
