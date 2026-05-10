"""routes/medicines.py — Medicine reminder + Gemini Chatbot"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
import json
from models import db, Medicine, MedicineLog

medicines_bp = Blueprint("medicines", __name__)

def _get_user_id():
    return session.get("user_id")

def _calc_points(taken_at, scheduled_time_str):
    try:
        scheduled = datetime.strptime(scheduled_time_str, "%H:%M")
        scheduled = scheduled.replace(year=taken_at.year, month=taken_at.month, day=taken_at.day)
        delta_mins = (taken_at - scheduled).total_seconds() / 60
        if delta_mins < 0: delta_mins = 0
        if delta_mins <= 15:  return 10
        elif delta_mins <= 30: return 5
        else: return 2
    except: return 2

def _get_level(total_points):
    if total_points >= 1000: return ("Health Guardian", "👑")
    elif total_points >= 600: return ("Health Legend", "🏆")
    elif total_points >= 300: return ("Health Champion", "⭐")
    elif total_points >= 100: return ("Health Warrior", "💪")
    else: return ("Health Beginner", "🌱")

@medicines_bp.route("/medicine")
def medicine():
    user_id = _get_user_id()
    meds = db.session.execute(db.select(Medicine).filter_by(user_id=user_id, is_active=True)).scalars().all() if user_id else []
    
    # Get today's logs to mark "Taken" slots
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    taken_slots = []
    if user_id:
        logs = db.session.execute(
            db.select(MedicineLog.medicine_id, MedicineLog.scheduled_time)
            .join(Medicine)
            .filter(Medicine.user_id == user_id)
            .filter(db.func.date(MedicineLog.taken_at) == today_str)
        ).all()
        # Create a list of "med_id-time" strings for easy checking
        taken_slots = [f"{log[0]}-{log[1]}" for log in logs]

    # Calculate Dose Day for each med
    for m in meds:
        try:
            start_date = datetime.strptime(m.start_date, "%Y-%m-%d")
            delta = datetime.utcnow() - start_date
            m.current_day = delta.days + 1
            if m.current_day > m.duration: m.current_day = m.duration
            if m.current_day < 1: m.current_day = 1
        except:
            m.current_day = 1

    total_points = 0
    if user_id:
        from sqlalchemy import func
        mids = [m.id for m in meds]
        if mids:
            result = db.session.execute(db.select(func.sum(MedicineLog.points_earned)).where(MedicineLog.medicine_id.in_(mids))).scalar()
            total_points = result or 0
    level_name, level_emoji = _get_level(total_points)
    
    return render_template("medicine.html", 
        medicines=meds, 
        taken_slots=taken_slots,
        total_points=total_points, 
        level_name=level_name, 
        level_emoji=level_emoji, 
        now_date=today_str)

@medicines_bp.route("/medicine/delete/<int:med_id>", methods=["POST"])
def delete_medicine(med_id):
    user_id = _get_user_id()
    if not user_id: return jsonify({"status": "error"}), 403
    med = db.session.get(Medicine, med_id)
    if med and med.user_id == user_id:
        med.is_active = False
        db.session.commit()
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 404

@medicines_bp.route("/medicine/add", methods=["POST"])
def add_medicine():
    user_id = _get_user_id()
    if not user_id: return redirect(url_for("auth.login"))
    times_per_day = int(request.form.get("times_per_day", 1))
    schedule = [request.form.get(f"time_{i}", "") for i in range(1, times_per_day + 1) if request.form.get(f"time_{i}", "")]
    med = Medicine(user_id=user_id, name=request.form.get("name", "").strip(), dosage=request.form.get("dosage", "").strip(),
                   times_per_day=times_per_day, schedule=json.dumps(schedule), start_date=request.form.get("start_date", ""), duration=int(request.form.get("duration", 7)))
    db.session.add(med); db.session.commit()
    flash(f"Medicine '{med.name}' added! 🎉", "success")
    return redirect(url_for("medicines.medicine"))

@medicines_bp.route("/medicine/taken/<int:med_id>", methods=["POST"])
def mark_taken(med_id):
    scheduled_time = request.form.get("scheduled_time", "")
    taken_at = datetime.utcnow()
    points = _calc_points(taken_at, scheduled_time)
    log = MedicineLog(medicine_id=med_id, scheduled_time=scheduled_time, taken_at=taken_at, status="TAKEN", points_earned=points)
    db.session.add(log); db.session.commit()
    return jsonify({"status": "ok", "points": points})

@medicines_bp.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    return render_template("chatbot.html", prefill=request.args.get("q", ""))

@medicines_bp.route("/chatbot/ask", methods=["POST"])
def chatbot_ask():
    import config
    import google.generativeai as genai
    question = request.json.get("question", "")
    if not question: return jsonify({"answer": "Please ask a question."})

    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        # Use gemini-1.5-flash for best stability and speed
        try:
            model = genai.GenerativeModel("gemini-flash-latest")
            response = model.generate_content(f"Answer this medicine query in simple language for a patient: {question}")
        except Exception as e:
            print(f"Gemini 1.5 Flash failed, trying flash-latest: {e}")
            model = genai.GenerativeModel("gemini-flash-latest")
            response = model.generate_content(f"Answer this medicine query in simple language for a patient: {question}")
            
        return jsonify({"answer": response.text + "\n\nNote: Consult your doctor."})
    except Exception as e:
        print(f"Chatbot Gemini Error: {e}")
        return jsonify({"answer": f"Error: {str(e)}\n\nNote: Consult your doctor."})
