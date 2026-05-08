"""
seed_data.py — Populate the database with Mysore-based doctors and slots.
"""
import os
import sys
from datetime import datetime, timedelta

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Doctor, Slot

def seed():
    with app.app_context():
        # Clear existing
        db.session.query(Slot).delete()
        db.session.query(Doctor).delete()
        db.session.commit()

        doctors_data = [
            # Cardiology
            {"name": "Dr. Kiran Kumar", "dept": "Cardiology", "exp": 18, "fee": 800},
            {"name": "Dr. Ramesh Hegde", "dept": "Cardiology", "exp": 15, "fee": 750},
            {"name": "Dr. Vinayaka S", "dept": "Cardiology", "exp": 12, "fee": 700},
            
            # General Physician
            {"name": "Dr. Anitha Mahesh", "dept": "General Physician", "exp": 12, "fee": 500},
            {"name": "Dr. Sunil Rao", "dept": "General Physician", "exp": 10, "fee": 450},
            {"name": "Dr. Kavitha J", "dept": "General Physician", "exp": 15, "fee": 550},
            
            # Dermatology
            {"name": "Dr. Meena Rao", "dept": "Dermatology", "exp": 8, "fee": 600},
            {"name": "Dr. Shwetha G", "dept": "Dermatology", "exp": 5, "fee": 500},
            {"name": "Dr. Harish B", "dept": "Dermatology", "exp": 11, "fee": 650},

            # Neurology
            {"name": "Dr. Suresh Mysore", "dept": "Neurology", "exp": 20, "fee": 1000},
            {"name": "Dr. Guruprasad", "dept": "Neurology", "exp": 14, "fee": 900},
            
            # Orthopedics
            {"name": "Dr. Pradeep J", "dept": "Orthopedics", "exp": 15, "fee": 700},
            {"name": "Dr. Arun Kumar", "dept": "Orthopedics", "exp": 9, "fee": 600},
            
            # Pediatrics
            {"name": "Dr. Sahana S", "dept": "Pediatrics", "exp": 10, "fee": 500},
            {"name": "Dr. Preethi M", "dept": "Pediatrics", "exp": 7, "fee": 450},
        ]

        for d in doctors_data:
            doc = Doctor(name=d["name"], dept=d["dept"], experience=d["exp"], fee=d["fee"])
            db.session.add(doc)
            db.session.commit()

            # Create slots for the next 3 days
            today = datetime.now()
            for day_offset in range(3):
                date_str = (today + timedelta(days=day_offset)).strftime("%Y-%m-%d")
                for hour in range(10, 18): # 10 AM to 6 PM
                    slot = Slot(doctor_id=doc.id, date=date_str, time=f"{hour:02d}:00")
                    db.session.add(slot)
                    slot2 = Slot(doctor_id=doc.id, date=date_str, time=f"{hour:02d}:30")
                    db.session.add(slot2)
            db.session.commit()

        print(f"✅ Successfully seeded {len(doctors_data)} Mysore doctors with slots!")

if __name__ == "__main__":
    seed()
