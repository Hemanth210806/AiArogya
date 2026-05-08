"""
seed_departments.py — Seed 15 departments for ArogyaAI
"""
from app import app
from models import db, Department
import json

departments_data = [
    {
        "id": 1,
        "name": "General Medicine",
        "icon": "🩺",
        "description": "Fever, infections, general illness",
        "diseases": ["Flu", "Typhoid", "Malaria", "Dengue"]
    },
    {
        "id": 2,
        "name": "Cardiology",
        "icon": "❤️",
        "description": "Heart & blood pressure conditions",
        "diseases": ["Heart Attack", "Hypertension", "Arrhythmia"]
    },
    {
        "id": 3,
        "name": "Gastroenterology",
        "icon": "🫃",
        "description": "Digestive system & stomach issues",
        "diseases": ["GERD", "Gastritis", "IBS", "Jaundice"]
    },
    {
        "id": 4,
        "name": "Neurology",
        "icon": "🧠",
        "description": "Brain, nerves & mental conditions",
        "diseases": ["Migraine", "Vertigo", "Paralysis", "Epilepsy"]
    },
    {
        "id": 5,
        "name": "Pulmonology",
        "icon": "🫁",
        "description": "Lungs & respiratory conditions",
        "diseases": ["Pneumonia", "Bronchitis", "Asthma", "TB"]
    },
    {
        "id": 6,
        "name": "Dermatology",
        "icon": "🧴",
        "description": "Skin, hair & nail conditions",
        "diseases": ["Psoriasis", "Fungal Infection", "Acne"]
    },
    {
        "id": 7,
        "name": "Orthopedics",
        "icon": "🦴",
        "description": "Bones, joints & muscle issues",
        "diseases": ["Arthritis", "Osteoporosis", "Back Pain"]
    },
    {
        "id": 8,
        "name": "Endocrinology",
        "icon": "⚗️",
        "description": "Hormones & metabolic disorders",
        "diseases": ["Diabetes", "Thyroid", "PCOD"]
    },
    {
        "id": 9,
        "name": "Nephrology",
        "icon": "🫘",
        "description": "Kidney & urinary conditions",
        "diseases": ["UTI", "Kidney Stones", "CKD"]
    },
    {
        "id": 10,
        "name": "Ophthalmology",
        "icon": "👁️",
        "description": "Eye & vision conditions",
        "diseases": ["Conjunctivitis", "Glaucoma", "Cataracts"]
    },
    {
        "id": 11,
        "name": "ENT",
        "icon": "👂",
        "description": "Ear, nose & throat conditions",
        "diseases": ["Sinusitis", "Tonsillitis", "Hearing Loss"]
    },
    {
        "id": 12,
        "name": "Psychiatry",
        "icon": "🧘",
        "description": "Mental health & behavioral issues",
        "diseases": ["Anxiety", "Depression", "Insomnia"]
    },
    {
        "id": 13,
        "name": "Pediatrics",
        "icon": "👶",
        "description": "Children's health (0-18 years)",
        "diseases": ["Chickenpox", "Measles", "Child Fever"]
    },
    {
        "id": 14,
        "name": "Gynecology",
        "icon": "🌸",
        "description": "Women's health conditions",
        "diseases": ["PCOD", "Pregnancy Issues", "UTI"]
    },
    {
        "id": 15,
        "name": "Oncology",
        "icon": "🎗️",
        "description": "Cancer screening & treatment",
        "diseases": ["Early Cancer Detection", "Tumor"]
    }
]

def seed():
    with app.app_context():
        # Clear existing departments to avoid duplicates
        # db.session.query(Department).delete()
        
        for dept in departments_data:
            existing = db.session.get(Department, dept["id"])
            if not existing:
                new_dept = Department(
                    id=dept["id"],
                    name=dept["name"],
                    icon=dept["icon"],
                    description=dept["description"],
                    diseases=json.dumps(dept["diseases"])
                )
                db.session.add(new_dept)
        
        db.session.commit()
        print(f"Successfully seeded {len(departments_data)} departments.")

if __name__ == "__main__":
    seed()
