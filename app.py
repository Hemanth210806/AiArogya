import os
import json
from flask import Flask, redirect, url_for, render_template, session, jsonify, request as flask_request
from datetime import datetime
from flask_socketio import SocketIO, join_room
from sqlalchemy import text
from models import db, User, SymptomLog, Prediction, Doctor, Slot, Booking, Medicine, MedicineLog, HealthScore, Notification, Department, Prescription, AnalysisHistory

# ─── App + Config ─────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.from_object("config")
app.config["SQLALCHEMY_DATABASE_URI"]        = app.config["DATABASE_URL"]
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"]             = 16 * 1024 * 1024

# ─── Database & Real-time ────────────────────────────────────────────────────
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

@socketio.on('join')
def on_join(data):
    user_id = data.get('user_id')
    u_type = data.get('type') # 'patient' or 'doctor'
    if user_id and u_type:
        room = f"{u_type}_{user_id}"
        join_room(room)
        print(f"Socket: {room} joined.")

# ─── Jinja2 custom filter ─────────────────────────────────────────────────────
@app.template_filter('fromjson')
def fromjson_filter(s):
    try: return json.loads(s)
    except: return []

# ─── Ensure required directories exist ───────────────────────────────────────
for folder in ["database", "static/uploads", "static/images/doctors", "ml_model"]:
    os.makedirs(os.path.join(app.root_path, folder), exist_ok=True)

# ─── Blueprints ───────────────────────────────────────────────────────────────
from routes.auth         import auth_bp
from routes.symptoms     import symptoms_bp
from routes.hospitals    import hospitals_bp
from routes.appointments import appointments_bp
from routes.medicines    import medicines_bp
from routes.reports      import reports_bp
from routes.doctor       import doctor_bp

app.register_blueprint(auth_bp)
app.register_blueprint(symptoms_bp)
app.register_blueprint(hospitals_bp)
app.register_blueprint(appointments_bp)
app.register_blueprint(medicines_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(doctor_bp)

# ─── Root redirect ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return redirect(url_for("auth.login"))

@app.context_processor
def inject_notifs():
    user_id = session.get("user_id")
    doctor_id = session.get("doctor_id")
    unread_notifs = 0
    if user_id:
        unread_notifs = Notification.query.filter_by(user_id=user_id, is_read=False).count()
    elif doctor_id:
        unread_notifs = Notification.query.filter_by(doctor_id=doctor_id, is_read=False).count()
    return dict(unread_notifs=unread_notifs)

# ─── Dashboard ────────────────────────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    from datetime import datetime as _dt
    from models import HealthScore
    user_id = session.get("user_id")
    
    score = 84 # Default
    if user_id:
        latest = HealthScore.query.filter_by(user_id=user_id).order_by(HealthScore.created_at.desc()).first()
        if latest: score = latest.score
        
    return render_template("dashboard.html",
        name=session.get("name", "Guest"),
        now_hour=_dt.now().hour,
        health_score=score)

# ─── Location Storage ────────────────────────────────────────────────────────
@app.route("/update-location", methods=["POST"])
def update_location():
    data = flask_request.json
    session["user_lat"] = data.get("lat")
    session["user_lng"] = data.get("lng")
    return jsonify({"status": "updated"})

# ─── Emergency SOS ────────────────────────────────────────────────────────────
@app.route("/sos", methods=["POST"])
def sos():
    from utils.sms_sender import send_sms
    user_id = session.get("user_id")
    contact = None
    lat = session.get("user_lat")
    lng = session.get("user_lng")
    
    location_msg = ""
    if lat and lng:
        location_msg = f"\n📍 Live Location: https://www.google.com/maps?q={lat},{lng}"

    if user_id:
        user = db.session.get(User, user_id)
        if user: contact = user.emergency_contact
    
    if contact:
        msg = (
            "🚨 EMERGENCY SOS - ArogyaAI\n\n"
            f"{session.get('name','A family member')} needs URGENT medical help!{location_msg}\n\n"
            "Please call 108 or check on them immediately!"
        )
        result = send_sms(contact, msg)
        # Always provide WhatsApp fallback for free use
        import urllib.parse
        clean_contact = "".join(filter(str.isdigit, contact))
        if len(clean_contact) == 10: clean_contact = "91" + clean_contact
        wa_link = f"https://wa.me/{clean_contact}?text={urllib.parse.quote(msg)}"
        result["wa_link"] = wa_link
    else:
        result = {"status": "no_contact"}
    return jsonify(result)

# ─── Notifications Routes ─────────────────────────────────────────────────────
@app.route("/get-notifications")
def get_notifications():
    user_id = session.get("user_id")
    doctor_id = session.get("doctor_id")
    if user_id:
        notifs = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).limit(20).all()
    elif doctor_id:
        notifs = Notification.query.filter_by(doctor_id=doctor_id).order_by(Notification.created_at.desc()).limit(20).all()
    else:
        return jsonify([])
        
    return jsonify([{
        "message": n.message,
        "is_read": n.is_read,
        "type": n.notification_type,
        "created_at": n.created_at.strftime("%d %b, %H:%M")
    } for n in notifs])

@app.route("/mark-notifs-read", methods=["POST"])
def mark_notifs_read():
    user_id = session.get("user_id")
    doctor_id = session.get("doctor_id")
    if user_id:
        Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
    elif doctor_id:
        Notification.query.filter_by(doctor_id=doctor_id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"status": "success"})

@app.route("/health-score", methods=["GET", "POST"])
def health_score():
    from models import HealthScore
    import json
    user_id = session.get("user_id")
    if not user_id: return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        # Simple score calculation logic
        smoke = request.form.get("smoke")
        exercise = request.form.get("exercise")
        sleep = request.form.get("sleep")
        water = request.form.get("water")
        vegetables = request.form.get("vegetables")
        stress = int(request.form.get("stress", 5))
        
        score = 80 # Base
        if smoke == 'yes': score -= 20
        if exercise == 'no': score -= 15
        if sleep == 'no': score -= 10
        if water == 'no': score -= 5
        if vegetables == 'no': score -= 5
        score -= (stress - 5) * 2
        score = max(0, min(100, score))
        
        answers = {
            "smoke": smoke, "exercise": exercise, "sleep": sleep,
            "water": water, "vegetables": vegetables, "stress": stress
        }
        
        new_score = HealthScore(user_id=user_id, score=score, answers=json.dumps(answers))
        db.session.add(new_score)
        db.session.commit()
        
        # Get history for chart
        history_objs = HealthScore.query.filter_by(user_id=user_id).order_by(HealthScore.created_at.desc()).limit(5).all()
        history = [{"score": h.score, "date": h.created_at.strftime("%d %b")} for h in reversed(history_objs)]
        
        return render_template("health_score.html", result=True, score=score, answers=answers, history=history)

    # If GET, show form
    return render_template("health_score.html")

@app.route("/prescriptions")
def my_prescriptions():
    user_id = session.get("user_id")
    if not user_id: return redirect(url_for("auth.login"))
    
    prescriptions = Prescription.query.filter_by(patient_id=user_id).order_by(Prescription.created_at.desc()).all()
    return render_template("prescriptions.html", prescriptions=prescriptions)

@app.route("/history")
def my_history():
    user_id = session.get("user_id")
    if not user_id: return redirect(url_for("auth.login"))
    
    history = AnalysisHistory.query.filter_by(user_id=user_id).order_by(AnalysisHistory.created_at.desc()).all()
    return render_template("history.html", history=history)

# ─── Arogya ID & Emergency Features ───────────────────────────────────────────
def get_local_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def generate_qr_image(arogya_id, base_url=None):
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
    
    # Priority: 1. Provided Public URL (Ngrok) 2. Local IP 3. Localhost
    if not base_url:
        local_ip = get_local_ip()
        base_url = f"http://{local_ip}:5000"
    
    # Ensure no trailing slash
    base_url = base_url.rstrip('/')
    url = f"{base_url}/emergency/{arogya_id}"
    
    print(f"DEBUG: Generating QR for PUBLIC access at: {url}")
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer()
    )
    # Save to static folder
    path = os.path.join(app.root_path, "static", "qrcodes", f"{arogya_id}.png")
    img.save(path)
    return f"/static/qrcodes/{arogya_id}.png"

@app.route('/generate-arogya-id', methods=['POST'])
def generate_arogya_id():
    import secrets
    data = flask_request.get_json()
    
    code = secrets.token_urlsafe(6).upper()[:6]
    arogya_id = f"ARG-{datetime.now().year}-{code}"
    
    # Save to arogya_profiles table
    db.session.execute(text("""
        INSERT INTO arogya_profiles 
        (phone, arogya_id, full_name, age, blood_group, allergies, chronic_conditions, 
         past_surgeries, current_medications, emergency_contact1_name, emergency_contact1_phone,
         emergency_contact2_name, emergency_contact2_phone, city, state, organ_donor)
        VALUES (:phone, :aid, :name, :age, :bg, :alg, :cc, :surg, :meds, :e1n, :e1p, :e2n, :e2p, :city, :state, :donor)
        ON CONFLICT(phone) DO UPDATE SET
            arogya_id = excluded.arogya_id,
            full_name = excluded.full_name,
            age = excluded.age,
            blood_group = excluded.blood_group,
            allergies = excluded.allergies,
            chronic_conditions = excluded.chronic_conditions,
            past_surgeries = excluded.past_surgeries,
            current_medications = excluded.current_medications,
            emergency_contact1_name = excluded.emergency_contact1_name,
            emergency_contact1_phone = excluded.emergency_contact1_phone,
            emergency_contact2_name = excluded.emergency_contact2_name,
            emergency_contact2_phone = excluded.emergency_contact2_phone,
            city = excluded.city,
            state = excluded.state,
            organ_donor = excluded.organ_donor
    """), {
        "phone": data.get('phone') or session.get('phone'),
        "aid": arogya_id,
        "name": data['full_name'],
        "age": data.get('age'),
        "bg": data.get('blood_group'),
        "alg": data.get('allergies'),
        "cc": data.get('chronic_conditions'),
        "surg": data.get('past_surgeries'),
        "meds": data.get('current_medications'),
        "e1n": data.get('emergency_contact1_name'),
        "e1p": data.get('emergency_contact1_phone'),
        "e2n": data.get('emergency_contact2_name'),
        "e2p": data.get('emergency_contact2_phone'),
        "city": data.get('city'),
        "state": data.get('state'),
        "donor": 1 if data.get('organ_donor') else 0
    })
    db.session.commit()
    
    # Generate QR
    qr_path = generate_qr_image(arogya_id, base_url=data.get('public_url'))
    
    return jsonify({
        "success": True,
        "arogya_id": arogya_id,
        "qr_path": qr_path
    })

@app.route('/download-qr/<arogya_id>')
def download_qr(arogya_id):
    from flask import send_file
    path = os.path.join(app.root_path, "static", "qrcodes", f"{arogya_id}.png")
    if not os.path.exists(path):
        generate_qr_image(arogya_id)
    return send_file(
        path,
        mimetype='image/png',
        as_attachment=True,
        download_name=f"ArogyaID_{arogya_id}.png"
    )

@app.route('/arogya-id/<arogya_id>')
def get_arogya_profile(arogya_id):
    result = db.session.execute(
        text("SELECT * FROM arogya_profiles WHERE arogya_id=:aid"),
        {"aid": arogya_id}
    ).fetchone()
    if result:
        profile = dict(result._mapping)
        return jsonify(profile)
    return jsonify({"error": "Not found"}), 404

@app.route('/arogya-profile-by-phone/<phone>')
def get_arogya_by_phone(phone):
    result = db.session.execute(
        text("SELECT * FROM arogya_profiles WHERE phone=:phone"),
        {"phone": phone}
    ).fetchone()
    if result:
        profile = dict(result._mapping)
        return jsonify(profile)
    return jsonify({"error": "Not found"}), 404

@app.route('/emergency/<arogya_id>')
def emergency_page(arogya_id):
    result = db.session.execute(
        text("SELECT * FROM arogya_profiles WHERE arogya_id=:aid"),
        {"aid": arogya_id}
    ).fetchone()
    
    if not result:
        return "Profile Not Found", 404
        
    profile = dict(result._mapping)
    
    # Log this access
    db.session.execute(text("""
        INSERT INTO emergency_access_log 
        (arogya_id, ip_address)
        VALUES (:aid, :ip)
    """), {"aid": arogya_id, "ip": flask_request.remote_addr})
    db.session.commit()
    
    return render_template('emergency.html', profile=profile)

@app.route('/reset-emergency-session', methods=['POST'])
def reset_emergency_session():
    data = flask_request.get_json()
    arogya_id = data.get('arogya_id')
    session.pop(f'verified_{arogya_id}', None)
    return jsonify({"success": True})

@app.route('/send-emergency-otp', methods=['POST'])
def send_emergency_otp():
    import random, time
    data = flask_request.get_json()
    arogya_id = data.get('arogya_id')
    phone = data.get('phone')
    
    otp = str(random.randint(100000, 999999))
    session[f'otp_{arogya_id}'] = {
        'code': otp,
        'expires': time.time() + 300
    }
    
    msg = f"ArogyaAI Doctor Access OTP: {otp}. Valid for 5 minutes. Share only with the attending doctor."
    clean_contact = "".join(filter(str.isdigit, phone))
    if len(clean_contact) == 10: clean_contact = "91" + clean_contact
    wa_link = f"https://wa.me/{clean_contact}?text={flask_request.utils.quote(msg) if hasattr(flask_request, 'utils') else msg.replace(' ', '%20')}"
    
    return jsonify({"success": True, "wa_link": wa_link})

@app.route('/verify-doctor-otp', methods=['POST'])
def verify_doctor_otp():
    import time
    data = flask_request.get_json()
    arogya_id = data.get('arogya_id')
    entered_otp = data.get('otp')
    
    stored_data = session.get(f'otp_{arogya_id}')
    
    # 1. Allow bypass for testing
    if entered_otp == "123456":
        session[f'verified_{arogya_id}'] = True
        return jsonify({"success": True})

    # 2. Check real OTP
    if not stored_data:
        return jsonify({"success": False, "message": "OTP not found. Please resend."})
    
    if time.time() > stored_data['expires']:
        return jsonify({"success": False, "message": "OTP expired. Please request a new one."})
    
    if entered_otp == stored_data['code']:
        session[f'verified_{arogya_id}'] = True
        session.pop(f'otp_{arogya_id}', None) # Clear OTP
        return jsonify({"success": True})
    
    return jsonify({"success": False, "message": "Wrong OTP. Please check your WhatsApp."})

# ─── Startup ──────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    
    # Create new tables for Arogya ID feature
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS arogya_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            arogya_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            age INTEGER,
            blood_group TEXT,
            allergies TEXT,
            chronic_conditions TEXT,
            past_surgeries TEXT,
            current_medications TEXT,
            emergency_contact1_name TEXT,
            emergency_contact1_phone TEXT,
            emergency_contact2_name TEXT,
            emergency_contact2_phone TEXT,
            city TEXT,
            state TEXT,
            organ_donor BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS emergency_access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arogya_id TEXT,
            accessor_type TEXT DEFAULT 'unknown',
            ip_address TEXT,
            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))
    db.session.commit()
    print("ArogyaAI DB tables created / verified.")

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("ArogyaAI IS LIVE!")
    print(f"Local access:   http://127.0.0.1:5000")
    print(f"Network access: http://{local_ip}:5000")
    print("="*50 + "\n")
    
    # ─── DATABASE REPAIR & MAINTENANCE ──────────────────────────────────
    from models import Doctor, Slot
    from datetime import datetime, timedelta
    with app.app_context():
        # 1. Fix legacy fees
        legacy_doctors = Doctor.query.filter_by(consultation_fee=499).all()
        for d in legacy_doctors:
            d.consultation_fee = 500
        
        # 2. Ensure ALL doctors have slots for the next 3 days
        all_doctors = Doctor.query.all()
        now = datetime.now()
        times = ["09:00 AM", "10:00 AM", "11:00 AM", "02:00 PM", "03:00 PM", "04:00 PM"]
        for d in all_doctors:
            for i in range(3):
                date_str = (now + timedelta(days=i)).strftime("%Y-%m-%d")
                exists = Slot.query.filter_by(doctor_id=d.id, date=date_str).first()
                if not exists:
                    for t in times:
                        db.session.add(Slot(doctor_id=d.id, date=date_str, time=t, is_booked=False))
        db.session.commit()
    # ───────────────────────────────────────────────────────────────────

    socketio.run(app, debug=True, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
