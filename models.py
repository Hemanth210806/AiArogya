from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"
    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name              = db.Column(db.Text, nullable=True)
    phone             = db.Column(db.Text, unique=True, nullable=False)
    emergency_contact = db.Column(db.Text, nullable=True)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    symptoms_logs = db.relationship("SymptomLog",  back_populates="user", lazy=True)
    predictions   = db.relationship("Prediction",  back_populates="user", lazy=True)
    bookings      = db.relationship("Booking",      back_populates="user", lazy=True)
    medicines     = db.relationship("Medicine",     back_populates="user", lazy=True)
    health_scores = db.relationship("HealthScore",  back_populates="user", lazy=True)
    notifications = db.relationship("Notification", back_populates="user", lazy=True)
    history       = db.relationship("AnalysisHistory", back_populates="user", lazy=True)

class SymptomLog(db.Model):
    __tablename__ = "symptoms_log"
    id                 = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id            = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    symptoms_text      = db.Column(db.Text, nullable=True)
    extracted_symptoms = db.Column(db.Text, nullable=True)
    photo_path         = db.Column(db.Text, nullable=True)
    intensity          = db.Column(db.Text, default="MEDIUM")
    duration           = db.Column(db.Text, default="HOURS")
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)

    user        = db.relationship("User",       back_populates="symptoms_logs")
    predictions = db.relationship("Prediction", back_populates="symptom_log", lazy=True)

class Prediction(db.Model):
    __tablename__ = "predictions"
    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"),       nullable=False)
    symptom_log_id = db.Column(db.Integer, db.ForeignKey("symptoms_log.id"), nullable=False)
    disease        = db.Column(db.Text, nullable=False)
    probability    = db.Column(db.Float, nullable=False)
    severity       = db.Column(db.Text, default="MILD")
    department     = db.Column(db.Text, nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    user        = db.relationship("User",       back_populates="predictions")
    symptom_log = db.relationship("SymptomLog", back_populates="predictions")

class Doctor(db.Model):
    __tablename__ = "doctors"
    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name             = db.Column(db.Text, nullable=False)
    email            = db.Column(db.Text, unique=True, nullable=False)
    password_hash    = db.Column(db.Text, nullable=False)
    department_id    = db.Column(db.Integer, db.ForeignKey("departments.id"))
    specialization   = db.Column(db.Text)
    license_number   = db.Column(db.Text, unique=True)
    experience_years = db.Column(db.Integer)
    consultation_fee = db.Column(db.Integer)
    available_days   = db.Column(db.Text) # JSON array
    available_time_start = db.Column(db.Text)
    available_time_end   = db.Column(db.Text)
    profile_photo    = db.Column(db.Text)
    is_available     = db.Column(db.Boolean, default=False)
    is_verified      = db.Column(db.Boolean, default=False)
    hospital_name    = db.Column(db.Text) # New field
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    # Legacy fields (for backward compatibility during migration)
    dept       = db.Column(db.Text)
    experience = db.Column(db.Integer)
    fee        = db.Column(db.Integer)
    photo      = db.Column(db.Text)

    slots         = db.relationship("Slot", back_populates="doctor", lazy=True)
    notifications = db.relationship("Notification", back_populates="doctor", lazy=True)
    prescriptions = db.relationship("Prescription", back_populates="doctor", lazy=True)
    department    = db.relationship("Department", back_populates="doctors")

class Department(db.Model):
    __tablename__ = "departments"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.Text, nullable=False)
    icon        = db.Column(db.Text)
    description = db.Column(db.Text)
    diseases    = db.Column(db.Text) # JSON array

    doctors = db.relationship("Doctor", back_populates="department")

class Notification(db.Model):
    __tablename__ = "notifications"
    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id           = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    doctor_id         = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=True)
    user_type         = db.Column(db.Text) # 'patient' or 'doctor'
    message           = db.Column(db.Text)
    is_read           = db.Column(db.Boolean, default=False)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    notification_type = db.Column(db.Text) # 'appointment', 'prescription', 'doctor_arrived'

    user   = db.relationship("User", back_populates="notifications")
    doctor = db.relationship("Doctor", back_populates="notifications")

class Prescription(db.Model):
    __tablename__ = "prescriptions"
    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("bookings.id"))
    doctor_id      = db.Column(db.Integer, db.ForeignKey("doctors.id"))
    patient_id     = db.Column(db.Integer, db.ForeignKey("users.id"))
    diagnosis      = db.Column(db.Text)
    instructions   = db.Column(db.Text)
    follow_up_date = db.Column(db.Text)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    doctor       = db.relationship("Doctor", back_populates="prescriptions")
    medicines    = db.relationship("PrescriptionMedicine", back_populates="prescription", lazy=True)

class PrescriptionMedicine(db.Model):
    __tablename__ = "prescription_medicines"
    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescriptions.id"))
    medicine_name   = db.Column(db.Text)
    dosage          = db.Column(db.Text)
    frequency       = db.Column(db.Text)
    duration        = db.Column(db.Text)
    buy_link        = db.Column(db.Text)

    prescription = db.relationship("Prescription", back_populates="medicines")

class AnalysisHistory(db.Model):
    __tablename__ = "analysis_history"
    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id           = db.Column(db.Integer, db.ForeignKey("users.id"))
    symptoms_entered  = db.Column(db.Text) # JSON array
    predicted_disease = db.Column(db.Text)
    confidence_score  = db.Column(db.Float)
    all_predictions   = db.Column(db.Text) # JSON
    doctor_consulted  = db.Column(db.Integer)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="history")

class Slot(db.Model):
    __tablename__ = "slots"
    id        = db.Column(db.Integer, primary_key=True, autoincrement=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    date      = db.Column(db.Text, nullable=False)
    time      = db.Column(db.Text, nullable=False)
    is_booked = db.Column(db.Boolean, default=False)

    doctor  = db.relationship("Doctor",  back_populates="slots")
    booking = db.relationship("Booking", back_populates="slot", uselist=False)

class Booking(db.Model):
    __tablename__ = "bookings"
    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    slot_id      = db.Column(db.Integer, db.ForeignKey("slots.id"),  nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"),  nullable=False)
    hospital_name= db.Column(db.Text, nullable=True)
    patient_name = db.Column(db.Text, nullable=False)
    phone        = db.Column(db.Text, nullable=False)
    age          = db.Column(db.Integer, nullable=True)
    note         = db.Column(db.Text, nullable=True)
    booking_id   = db.Column(db.Text, unique=True, nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    slot = db.relationship("Slot",    back_populates="booking")
    user = db.relationship("User",    back_populates="bookings")

class Medicine(db.Model):
    __tablename__ = "medicines"
    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name         = db.Column(db.Text, nullable=False)
    dosage       = db.Column(db.Text, nullable=False)
    times_per_day= db.Column(db.Integer, nullable=False)
    schedule     = db.Column(db.Text, nullable=False)
    start_date   = db.Column(db.Text, nullable=False)
    duration     = db.Column(db.Integer, nullable=False)
    is_active    = db.Column(db.Boolean, default=True)

    user = db.relationship("User", back_populates="medicines")
    logs = db.relationship("MedicineLog", back_populates="medicine", lazy=True)

class MedicineLog(db.Model):
    __tablename__ = "medicine_logs"
    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    medicine_id    = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    scheduled_time = db.Column(db.Text, nullable=False)
    taken_at       = db.Column(db.DateTime, nullable=True)
    status         = db.Column(db.Text, default="MISSED")
    points_earned  = db.Column(db.Integer, default=0)

    medicine = db.relationship("Medicine", back_populates="logs")

class HealthScore(db.Model):
    __tablename__ = "health_scores"
    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    score      = db.Column(db.Integer, nullable=False)
    answers    = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="health_scores")
