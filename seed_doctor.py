"""
seed_doctor.py — Create a test doctor account for ArogyaAI
"""
from app import app
from models import db, Doctor, Department
from werkzeug.security import generate_password_hash

def seed():
    with app.app_context():
        # Check if doctor exists
        existing = Doctor.query.filter_by(email="smith@arogyaai.in").first()
        if not existing:
            dept = Department.query.filter_by(name="General Medicine").first()
            doctor = Doctor(
                name="Dr. John Smith",
                email="smith@arogyaai.in",
                password_hash=generate_password_hash("doctor123"),
                department_id=dept.id if dept else 1,
                specialization="Internal Medicine",
                license_number="MD12345",
                experience_years=12,
                consultation_fee=500,
                is_verified=True,
                is_available=True
            )
            db.session.add(doctor)
            db.session.commit()
            print("Test doctor created: smith@arogyaai.in / doctor123")
        else:
            print("Test doctor already exists.")

if __name__ == "__main__":
    seed()
