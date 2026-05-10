"""
utils/severity_calc.py — ArogyaAI Severity Calculator

Calculates severity level (CRITICAL / MODERATE / MILD) using:
  - Symptom weights from severity_dict.pkl
  - Intensity adjustment
  - Duration adjustment
  - Heart disease special override
  - Precautions from precaution_dict.pkl (CSV-sourced, never hardcoded)
"""

import os
import pickle

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_DIR = os.path.join(ROOT, "ml_model")

_severity_dict   = None
_precaution_dict = None
_desc_dict       = None


def _load():
    global _severity_dict, _precaution_dict, _desc_dict
    if _severity_dict is None:
        sev_path  = os.path.join(ML_DIR, "severity_dict.pkl")
        prec_path = os.path.join(ML_DIR, "precaution_dict.pkl")
        desc_path = os.path.join(ML_DIR, "description_dict.pkl")

        if os.path.exists(sev_path):
            with open(sev_path, "rb") as f:
                _severity_dict = pickle.load(f)
        else:
            _severity_dict = {}

        if os.path.exists(prec_path):
            with open(prec_path, "rb") as f:
                _precaution_dict = pickle.load(f)
        else:
            _precaution_dict = {}

        if os.path.exists(desc_path):
            with open(desc_path, "rb") as f:
                _desc_dict = pickle.load(f)
        else:
            _desc_dict = {}


# ─── Intensity adjustment ─────────────────────────────────────────────────────
INTENSITY_DELTA = {"HIGH": +3, "MEDIUM": 0, "LOW": -3}

# ─── Duration adjustment ──────────────────────────────────────────────────────
DURATION_DELTA  = {"NEW": 0, "HOURS": +1, "DAYS": +2, "WEEK": +3, "CHRONIC": +4}

# ─── Heart/critical disease keywords ─────────────────────────────────────────
CRITICAL_DISEASES = [
    "heart attack", "myocardial infarction", "cardiac arrest",
    "stroke", "brain stroke", "paralysis (brain hemorrhage)",
    "pulmonary embolism", "hypoglycemia"
]

MILD_DISEASES = [
    "common cold", "acne", "fungal infection", "allergy", 
    "cervical spondylosis", "dimorphic hemmorhoids(piles)",
    "varicose veins", "hypothyroidism", "hyperthyroidism",
    "psoriasis", "impetigo", "osteoarthritis", "arthritis",
    "vertigo"
]

# ─── Department mapping ───────────────────────────────────────────────────────
# Order matters: more specific keywords should be checked first.
DEPT_MAP = {
    "cold": "General Medicine",
    "flu": "General Medicine",
    "fever": "General Medicine",
    "cough": "General Medicine",
    "malaria": "General Medicine",
    "typhoid": "General Medicine",
    "dengue": "General Medicine",
    "heart": "Cardiology",
    "cardiac": "Cardiology",
    "hypertension": "General Medicine",
    "diabetes": "Endocrinology",
    "thyroid": "Endocrinology",
    "pcod": "Endocrinology",
    "kidney": "Nephrology",
    "renal": "Nephrology",
    "uti": "Nephrology",
    "liver": "Gastroenterology",
    "hepatitis": "Gastroenterology",
    "gastro": "Gastroenterology",
    "gerd": "Gastroenterology",
    "acidity": "Gastroenterology",
    "skin": "Dermatology",
    "acne": "Dermatology",
    "psoriasis": "Dermatology",
    "fungal": "Dermatology",
    "asthma": "Pulmonology",
    "bronchitis": "Pulmonology",
    "pneumonia": "Pulmonology",
    "tuberculosis": "Pulmonology",
    "migraine": "Neurology",
    "epilepsy": "Neurology",
    "paralysis": "Neurology",
    "vertigo": "Neurology",
    "bone": "Orthopedics",
    "joint": "Orthopedics",
    "osteo": "Orthopedics",
    "arthri": "Orthopedics",
    "arthritis": "Orthopedics",
    "spondylosis": "Orthopedics",
    "back pain": "Orthopedics",
    "eye": "Ophthalmology",
    "cataract": "Ophthalmology",
    "glaucoma": "Ophthalmology",
    "conjunctivitis": "Ophthalmology",
    "sinus": "ENT",
    "tonsil": "ENT",
    "ear": "ENT",
    "hearing": "ENT",
    "anxiety": "Psychiatry",
    "depression": "Psychiatry",
    "insomnia": "Psychiatry",
    "child": "Pediatrics",
    "chickenpox": "Pediatrics",
    "measles": "Pediatrics",
    "pregnancy": "Gynecology",
    "women": "Gynecology",
    "cancer": "Oncology",
    "tumor": "Oncology",
}


def get_department(disease: str) -> str:
    """Map a disease name to a medical department."""
    disease_lower = disease.lower().strip()
    if not disease_lower or disease_lower == "unknown":
        return "General Medicine"
        
    for keyword, dept in DEPT_MAP.items():
        if keyword in disease_lower:
            return dept
            
    return "General Medicine"


def calculate_severity(
    extracted_symptoms: list,
    intensity:          str,
    duration:           str,
    top_disease:        str,
    top_probability:    float,
    department_override: str = None
) -> dict:
    """
    Calculate severity level and return precautions + department.

    Returns:
        {
          "level":       "CRITICAL" | "MODERATE" | "MILD",
          "score":       float,
          "precautions": [str, str, str, str],
          "department":  str,
          "description": str,
        }
    """
    _load()

    # ── Severity score calculation ────────────────────────────────────────────
    i_delta = INTENSITY_DELTA.get(intensity, 0)
    d_delta = DURATION_DELTA.get(duration, 0)

    weights = []
    for symptom in extracted_symptoms:
        base = _severity_dict.get(symptom, 3)  # default weight 3 if not found
        adjusted = base + i_delta + d_delta
        adjusted = max(1, min(10, adjusted))   # clamp 1–10
        weights.append(adjusted)

    avg_score = sum(weights) / len(weights) if weights else 3.0

    # ── Critical disease override ─────────────────────────────────────────────
    is_critical_disease = any(cd in top_disease.lower() for cd in CRITICAL_DISEASES)
    heart_critical      = is_critical_disease and top_probability >= 0.5

    # ── Determine level ───────────────────────────────────────────────────────
    # We use higher thresholds to avoid over-alerting for common issues.
    if heart_critical or avg_score >= 7.0:
        level = "CRITICAL"
    elif avg_score >= 5.0:
        level = "MODERATE"
    else:
        level = "MILD"

    # ── Protection Cap: Prevent mild diseases from triggering CRITICAL/MODERATE ──
    # If the AI predicts a mild disease, we cap it at MILD unless symptoms are extreme.
    if any(md in top_disease.lower() for md in MILD_DISEASES):
        if avg_score >= 6.5:
            level = "MODERATE"
        else:
            level = "MILD"

    # ── Get precautions from CSV (never hardcoded) ────────────────────────────
    precautions = _precaution_dict.get(top_disease, [])
    if not precautions:
        # Try fuzzy match
        for key in _precaution_dict:
            if key.lower() in top_disease.lower() or top_disease.lower() in key.lower():
                precautions = _precaution_dict[key]
                break

    # ── Get disease description ───────────────────────────────────────────────
    description = _desc_dict.get(top_disease, "")
    if not description:
        for key in _desc_dict:
            if key.lower() in top_disease.lower() or top_disease.lower() in key.lower():
                description = _desc_dict[key]
                break

    # Standardize department names to match DB
    if department_override:
        department_override = department_override.strip()
        if "skin" in department_override.lower() or "derm" in department_override.lower():
            department_override = "Dermatology"
        elif "eye" in department_override.lower() or "ophth" in department_override.lower():
            department_override = "Ophthalmology"
    
    department = department_override if department_override else get_department(top_disease)

    # ── Confidence Score Calculation ──────────────────────────────────────────
    # Focus on model probability while using symptom count as a secondary guide.
    num_s = len(extracted_symptoms)
    prob_score = top_probability * 100
    
    # Base multiplier from symptom count (less harsh than before)
    if num_s >= 5:   count_mult = 1.0
    elif num_s >= 4: count_mult = 0.95
    elif num_s >= 3: count_mult = 0.90
    elif num_s >= 2: count_mult = 0.85
    else:            count_mult = 0.70
    
    # ── Confidence Score Calculation (Evidence-Weighted Blend) ────────────────
    # Blends model probability with the "Weight of Evidence" (symptom count).
    num_s = len(extracted_symptoms)
    prob_p = top_probability * 100
    
    # Evidence Modifier: More symptoms provide higher clinical certainty.
    if num_s >= 5:   evidence_mod = 10  # High evidence bonus
    elif num_s >= 3: evidence_mod = 5   # Decent evidence boost
    elif num_s == 2: evidence_mod = 0   # Neutral
    else:            evidence_mod = -10 # Skepticism penalty for sparse evidence
    
    # Calculate final trust score
    conf_score = round(prob_p + evidence_mod)
    
    # Final clamp 0-100
    conf_score = max(0, min(100, conf_score))

    return {
        "level":       level,
        "score":       round(avg_score, 2),
        "precautions": precautions,
        "department":  department,
        "description": description,
        "confidence":  conf_score
    }
