"""routes/appointments.py — Doctor slots + booking flow"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import json
from models import db, Doctor, Slot, Department
from utils.notifications import create_notification

appointments_bp = Blueprint("appointments", __name__)

def _get_doctor_for_dept(dept_name):
    """Try to find a doctor for the specific department name, or fallback."""
    dept = Department.query.filter(Department.name.ilike(f"%{dept_name}%")).first()
    if dept:
        doctor = Doctor.query.filter_by(department_id=dept.id).first()
    else:
        doctor = Doctor.query.filter_by(name="General Physician").first()
    
    if not doctor:
        doctor = Doctor.query.first()
    return doctor

@appointments_bp.route("/appointment")
def appointment():
    # Priority: 1. URL param 2. Session 3. Severity 4. Fallback
    url_dept   = request.args.get("dept")
    severity   = session.get("severity", {})
    
    if url_dept:
        department = url_dept
    else:
        department = session.get("selected_department") or severity.get("department", "General Medicine")
    
    hospital   = request.args.get("hospital", session.get("selected_hospital", "Local Health Center"))
    
    session["selected_hospital"] = hospital
    session["selected_department"] = department

    # Check if a specific doctor was chosen
    doctor_id = request.args.get("doctor_id")
    
    dept_obj = Department.query.filter(Department.name.ilike(f"%{department}%")).first()
    
    query = Doctor.query
    if dept_obj:
        query = query.filter_by(department_id=dept_obj.id)
    
    # Shared Pool: Always show all doctors in the department regardless of hospital
    doctors = query.all()
    
    selected_doctor = None
    if doctor_id:
        selected_doctor = db.session.get(Doctor, int(doctor_id))
    elif doctors:
        selected_doctor = doctors[0]

    slots = []
    if selected_doctor:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # 1. Fetch existing future slots
        all_slots = Slot.query.filter(
            Slot.doctor_id == selected_doctor.id, 
            Slot.is_booked == False,
            Slot.date >= today_str
        ).order_by(Slot.date, Slot.time).all()
        
        # 2. If no future slots, generate some for demo/stability
        if not all_slots:
            from datetime import timedelta
            times = ["09:00 AM", "10:00 AM", "11:00 AM", "02:00 PM", "03:00 PM", "04:00 PM"]
            for i in range(3): # Next 3 days
                d_str = (now + timedelta(days=i)).strftime("%Y-%m-%d")
                for t in times:
                    s = Slot(doctor_id=selected_doctor.id, date=d_str, time=t, is_booked=False)
                    db.session.add(s)
            db.session.commit()
            # Re-fetch
            all_slots = Slot.query.filter(Slot.doctor_id == selected_doctor.id, Slot.is_booked == False, Slot.date >= today_str).all()
        
        # 3. Filter past times if it's today
        for s in all_slots:
            if s.date == today_str:
                try:
                    s_time = datetime.strptime(s.time, "%I:%M %p").time()
                    if s_time > now.time():
                        slots.append(s)
                except:
                    slots.append(s) # Fallback if format is weird
            else:
                slots.append(s)
        slots = slots[:30]

    return render_template("appointment.html",
        doctor=selected_doctor, doctors=doctors, slots=slots, hospital=hospital, department=department)

@appointments_bp.route("/book", methods=["POST"])
def book():
    from models import Booking
    from utils.sms_sender import send_appointment_confirmation

    slot_id      = request.form.get("slot_id")
    patient_name = request.form.get("patient_name", "").strip()
    phone        = request.form.get("phone", "").strip()
    age          = request.form.get("age", "")
    note         = request.form.get("note", "").strip()
    hospital     = session.get("selected_hospital", "Local Health Center")
    user_id      = session.get("user_id")

    if not slot_id:
        flash("Please select a time slot.", "error")
        return redirect(url_for("appointments.appointment"))

    slot = db.session.get(Slot, int(slot_id))
    if not slot or slot.is_booked:
        flash("Slot not available.", "error")
        return redirect(url_for("appointments.appointment"))

    # Generate booking ID
    from sqlalchemy import func
    count = db.session.execute(db.select(func.count(Booking.id))).scalar() + 1
    booking_id = f"ARG2026{count:03d}"

    booking = Booking(
        slot_id=int(slot_id),
        user_id=user_id,
        hospital_name=hospital,
        patient_name=patient_name,
        phone=phone,
        age=int(age) if age.isdigit() else None,
        note=note,
        booking_id=booking_id
    )
    slot.is_booked = True
    db.session.add(booking)
    db.session.commit()

    doctor = slot.doctor
    
    # Notify Patient
    create_notification(
        user_id=user_id,
        message=f"Appointment confirmed with Dr. {doctor.name} on {slot.date} at {slot.time}. ID: {booking_id}",
        n_type="appointment"
    )
    
    # Notify Doctor
    create_notification(
        doctor_id=doctor.id,
        user_type='doctor',
        message=f"New appointment booked by {patient_name} for {slot.date} at {slot.time}.",
        n_type="appointment"
    )
    sms_resp = send_appointment_confirmation(
        phone, doctor.name, hospital, doctor.dept,
        slot.date, slot.time, booking_id, doctor.fee
    )

    # Store for confirmation page
    session.update({
        "booking_id": booking_id,
        "booking_doctor": doctor.name,
        "booking_department": doctor.dept,
        "booking_date": slot.date,
        "booking_time": slot.time,
        "booking_fee": doctor.fee,
        "booking_hospital": hospital,
        "sms_preview": sms_resp.get("message", "") if sms_resp.get("status") == "preview" else "",
        "wa_link": sms_resp.get("wa_link", "")
    })

    return redirect(url_for("appointments.booking_confirmed"))

@appointments_bp.route("/booking-confirmed")
def booking_confirmed():
    return render_template("appointment.html",
        confirmed=True,
        booking_id=session.get("booking_id"),
        doctor_name=session.get("booking_doctor"),
        department=session.get("booking_department"),
        appt_date=session.get("booking_date"),
        appt_time=session.get("booking_time"),
        fee=session.get("booking_fee"),
        hospital=session.get("booking_hospital"),
        sms_preview=session.get("sms_preview", ""),
        wa_link=session.get("wa_link", "")
    )

@appointments_bp.route("/my-appointments")
def my_appointments():
    from models import Booking
    user_id = session.get("user_id")
    if not user_id: return redirect(url_for("auth.login"))
    
    bookings = Booking.query.filter_by(user_id=user_id).order_by(Booking.id.desc()).all()
    return render_template("appointment.html", view_list=True, bookings=bookings)
