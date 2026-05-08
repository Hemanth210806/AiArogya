"""
utils/ml_predictor.py — ArogyaAI Disease Prediction Utility

Loads trained RandomForest model and returns top-5 disease predictions.
"""

import os
import pickle
import numpy as np

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_DIR   = os.path.join(ROOT, "ml_model")

_model        = None
_symptom_list = None


def _load():
    global _model, _symptom_list
    if _model is None:
        model_path   = os.path.join(ML_DIR, "disease_model.pkl")
        symptom_path = os.path.join(ML_DIR, "symptom_list.pkl")

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                "disease_model.pkl not found. "
                "Please run: python ml_model/train_model.py"
            )

        with open(model_path, "rb") as f:
            _model = pickle.load(f)
        with open(symptom_path, "rb") as f:
            _symptom_list = pickle.load(f)


def get_symptom_list() -> list:
    """Return the ordered list of 132 symptom column names."""
    _load()
    return list(_symptom_list)


def predict_top5(extracted_symptoms: list) -> list:
    """
    Given a list of symptom column names, return top-5 disease predictions.

    Args:
        extracted_symptoms: List of symptom strings (must match dataset columns)

    Returns:
        List of dicts: [{"disease": str, "probability": float, "percent": int}, ...]
        Sorted by probability descending.
    """
    _load()

    # Build 132-dim binary input vector
    vector = np.zeros(len(_symptom_list), dtype=int)
    for symptom in extracted_symptoms:
        if symptom in _symptom_list:
            idx = list(_symptom_list).index(symptom)
            vector[idx] = 1

    # Predict class probabilities
    proba  = _model.predict_proba([vector])[0]
    classes = _model.classes_

    # Build result list
    results = [
        {
            "disease":     disease,
            "probability": float(prob),
            "percent":     int(round(prob * 100))
        }
        for disease, prob in zip(classes, proba)
    ]

    # Sort by probability descending
    results.sort(key=lambda x: x["probability"], reverse=True)

    # ─── New: Emergency Clinical Override (Safety Net) ─────────────────────
    # If the AI is offline or the model is biased, we force critical matches
    if "weight_gain" in extracted_symptoms:
        # Weight gain is for Hypothyroidism. Rule out Diabetes (which usually has obesity/weight loss)
        for r in results:
            if "Hypothyroidism" in r["disease"]:
                r["probability"] = max(r["probability"], 0.95)
            if "Diabetes" in r["disease"] and "polyuria" not in extracted_symptoms:
                r["probability"] = 0.01 # Rule out Diabetes unless polyuria is present
        results.sort(key=lambda x: x["probability"], reverse=True)
    
    if "weakness_of_one_body_side" in extracted_symptoms:
        # Find Paralysis and force it to top
        for r in results:
            if "Paralysis" in r["disease"]:
                r["probability"] = 0.95
                r["percent"] = 95
        results.sort(key=lambda x: x["probability"], reverse=True)
    
    if "yellow_crust_ooze" in extracted_symptoms or "red_sore_around_nose" in extracted_symptoms:
        for r in results:
            if "Impetigo" in r["disease"]:
                r["probability"] = 0.95
                r["percent"] = 95
        results.sort(key=lambda x: x["probability"], reverse=True)
        
    if "burning_micturition" in extracted_symptoms or "bladder_discomfort" in extracted_symptoms:
        # Force UTI to top if burning is present
        for r in results:
            if "Urinary tract infection" in r["disease"]:
                r["probability"] = 0.95
                r["percent"] = 95
        results.sort(key=lambda x: x["probability"], reverse=True)
        
    if "excessive_hunger" in extracted_symptoms or "anxiety" in extracted_symptoms:
        # Force Hypoglycemia and BLOCK Heart Attack (unless chest_pain is VERY clear)
        if "chest_pain" not in extracted_symptoms:
            for r in results:
                if "Hypoglycemia" in r["disease"]:
                    r["probability"] = 0.95
                if "Heart attack" in r["disease"]:
                    r["probability"] = 0.01 # BLOCK
        results.sort(key=lambda x: x["probability"], reverse=True)
        
    if "yellowing_of_eyes" in extracted_symptoms or "yellowish_skin" in extracted_symptoms:
        # Force Jaundice/Hepatitis if yellowing is present
        for r in results:
            if "Jaundice" in r["disease"] or "Hepatitis" in r["disease"]:
                r["probability"] = max(r["probability"], 0.90)
                r["percent"] = int(r["probability"] * 100)
    else:
        # CATEGORY LOCK: If NO yellowing is found, BLOCK Jaundice and Hepatitis
        for r in results:
            if "Jaundice" in r["disease"] or "Hepatitis" in r["disease"]:
                r["probability"] = 0.01

    if "abdominal_pain" in extracted_symptoms or "indigestion" in extracted_symptoms:
        # Force Peptic Ulcer and BLOCK Hypoglycemia
        for r in results:
            if "Peptic ulcer" in r["disease"]:
                r["probability"] = max(r["probability"], 0.90)
            if "Hypoglycemia" in r["disease"]:
                r["probability"] = 0.01
        results.sort(key=lambda x: x["probability"], reverse=True)
        
    if "neck_pain" in extracted_symptoms or "shoulder_pain" in extracted_symptoms:
        # Force Spondylosis if neck/shoulder pain is present. Rule out Hormonal.
        for r in results:
            if "Cervical spondylosis" in r["disease"]:
                r["probability"] = max(r["probability"], 0.95)
            if "Hyperthyroidism" in r["disease"] or "Hypoglycemia" in r["disease"]:
                r["probability"] = 0.01 
        results.sort(key=lambda x: x["probability"], reverse=True)
    # ─── SYSTEMATIC RULE-OUT LOGIC (Hackathon Grade) ───────────────────────
    
    # 1. THE YELLOW RULE (Liver Focus)
    if "yellowing_of_eyes" in extracted_symptoms or "yellowish_skin" in extracted_symptoms:
        # Rule out non-liver diseases
        for r in results:
            if r["disease"] not in ["Jaundice", "Hepatitis A", "Hepatitis B", "Hepatitis C", "Hepatitis D", "Hepatitis E", "Alcoholic hepatitis", "Chronic cholestasis"]:
                r["probability"] *= 0.1 # Severely reduce non-liver
        results.sort(key=lambda x: x["probability"], reverse=True)
    else:
        # If NO yellowing, rule out Jaundice/Hepatitis
        for r in results:
            if r["disease"] in ["Jaundice", "Hepatitis A", "Hepatitis B", "Hepatitis C", "Hepatitis D", "Hepatitis E", "Alcoholic hepatitis"]:
                r["probability"] = 0.01

    # 2. THE FEVER RULE (Infection Focus)
    if "high_fever" in extracted_symptoms or "fever" in extracted_symptoms or "chills" in extracted_symptoms:
        # Rule out non-febrile diseases
        for r in results:
            if r["disease"] in ["Hypoglycemia", "Hyperthyroidism", "Osteoarthristis", "Arthritis", "Hypertension", "Cervical spondylosis", "Fungal infection", "Allergy"]:
                r["probability"] = 0.01 # BLOCK
        results.sort(key=lambda x: x["probability"], reverse=True)
        
        # Force Tropical Disease search
        if "joint_pain" in extracted_symptoms:
            for r in results:
                if "Dengue" in r["disease"]: r["probability"] = max(r["probability"], 0.95)
        elif "chills" in extracted_symptoms and "sweating" in extracted_symptoms:
            # If chills + sweating + NO cough, it is Malaria, NOT TB
            for r in results:
                if "Malaria" in r["disease"]: r["probability"] = max(r["probability"], 0.95)
                if "Tuberculosis" in r["disease"] and "cough" not in extracted_symptoms:
                    r["probability"] = 0.01 # BLOCK TB if no cough
        elif "abdominal_pain" in extracted_symptoms:
            for r in results:
                if "Typhoid" in r["disease"]: r["probability"] = max(r["probability"], 0.95)
        elif "skin_rash" in extracted_symptoms or "red_spots_over_body" in extracted_symptoms:
             for r in results:
                if "Chicken pox" in r["disease"]: r["probability"] = max(r["probability"], 0.95)
        results.sort(key=lambda x: x["probability"], reverse=True)

    # 3. THE HUNGER RULE (Metabolic Focus)
    if "excessive_hunger" in extracted_symptoms:
        # Rule out acute emergencies that don't cause hunger
        for r in results:
            if r["disease"] in ["Heart attack", "Hypertension", "Dengue", "Malaria"]:
                r["probability"] = 0.01 # BLOCK
        results.sort(key=lambda x: x["probability"], reverse=True)

    # 4. THE STOMACH RULE (Digestive Focus)
    if "abdominal_pain" in extracted_symptoms or "indigestion" in extracted_symptoms:
        # Block unrelated emergencies
        for r in results:
            if r["disease"] in ["Heart attack", "Hypertension", "Paralysis (brain hemorrhage)", "Cervical spondylosis"]:
                r["probability"] = 0.01
        results.sort(key=lambda x: x["probability"], reverse=True)

    # 5. THE JOINT RULE (Orthopedic Focus)
    if "joint_pain" in extracted_symptoms:
        for r in results:
            if r["disease"] in ["Heart attack", "Hypertension", "Common Cold", "Typhoid"]:
                r["probability"] = 0.01
        results.sort(key=lambda x: x["probability"], reverse=True)

    # 6. THE HEART ATTACK VS GERD RULE (Critical Emergency)
    if "chest_pain" in extracted_symptoms:
        if "sweating" in extracted_symptoms or "breathlessness" in extracted_symptoms:
            # High certainty for Heart Attack
            for r in results:
                if "Heart attack" in r["disease"]:
                    r["probability"] = max(r["probability"], 0.95)
                if "GERD" in r["disease"] or "Pneumonia" in r["disease"]:
                    r["probability"] = 0.01 # BLOCK fallbacks
            results.sort(key=lambda x: x["probability"], reverse=True)
        elif "fever" not in extracted_symptoms and "high_fever" not in extracted_symptoms:
            # If ONLY chest pain (no sweating/breathlessness) and NO fever, it's likely GERD
            for r in results:
                if "GERD" in r["disease"]:
                    r["probability"] = max(r["probability"], 0.85)
                if "Pneumonia" in r["disease"]:
                    r["probability"] = 0.01
            results.sort(key=lambda x: x["probability"], reverse=True)

    # 7. THE COLD VS MIGRAINE RULE
    if "headache" in extracted_symptoms and "continuous_sneezing" not in extracted_symptoms and "runny_nose" not in extracted_symptoms:
        # If no sneezing/runny nose, it's likely Migraine/Hypertension, NOT Cold
        for r in results:
            if "Common Cold" in r["disease"]:
                r["probability"] = 0.01 # BLOCK
        results.sort(key=lambda x: x["probability"], reverse=True)

    # 8. THE DIARRHOEA RULE (Gastroenteritis vs Ulcer)
    if "diarrhoea" in extracted_symptoms:
        # Peptic ulcer does not cause diarrhoea
        for r in results:
            if "Gastroenteritis" in r["disease"]:
                r["probability"] = max(r["probability"], 0.90)
            if "Peptic ulcer" in r["disease"]:
                r["probability"] = 0.01 # BLOCK
        results.sort(key=lambda x: x["probability"], reverse=True)

    # ─── Final Step: Normalization (Ensures total probability = 1.0) ──────────
    total = sum(p["probability"] for p in results)
    if total > 0:
        for p in results:
            p["probability"] /= total
            p["percent"] = int(p["probability"] * 100)
            
    # Final sort and return top 5
    results.sort(key=lambda x: x["probability"], reverse=True)
    return results[:5]


def get_bar_color(percent: int) -> str:
    """Return CSS color class based on probability percentage."""
    if percent >= 70:
        return "danger"    # red
    elif percent >= 40:
        return "warning"   # yellow
    else:
        return "success"   # green
