"""
utils/gemini_api.py — Google Gemini API + fallback rule-based symptom extractor
"""

import os
import json
import re
import sys
import google.generativeai as genai
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Configure Gemini
genai.configure(api_key=config.GEMINI_API_KEY)

def get_gemini_response(prompt: str) -> str:
    """Simple wrapper to get a text response from Gemini."""
    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini Response Error: {e}")
        return ""

# ─── Intensity / Duration Keyword Maps ────────────────────────────────────────
HIGH_WORDS   = ["heavy", "severe", "worst", "unbearable", "crushing", "intense", "extreme"]
LOW_WORDS    = ["slight", "mild", "little", "minor", "small", "bit of"]
DURATION_MAP = {
    "NEW":     ["just now", "few minutes", "suddenly"],
    "HOURS":   ["since morning", "few hours", "today"],
    "DAYS":    ["since yesterday", "couple of days", "3 days"],
    "WEEK":    ["past week", "7 days"],
    "CHRONIC": ["long time", "months", "years", "chronic"],
}

KEYWORD_MAP = {
    # Stomach / Abdomen (Crucial for Typhoid/Gastro)
    "stomach": ["stomach_pain", "abdominal_pain", "belly_pain"],
    "belly": ["stomach_pain", "abdominal_pain", "belly_pain"],
    "abdomen": ["stomach_pain", "abdominal_pain", "belly_pain"],
    "cramp": ["stomach_pain", "abdominal_pain"],
    
    # Rash / Skin (Crucial for Dengue/Fungal)
    "rash": ["skin_rash", "red_spots_over_body", "nodal_skin_eruptions"],
    "spots": ["red_spots_over_body", "dischromic_patches"],
    "skin": ["skin_rash", "itching", "nodal_skin_eruptions"],
    "itch": ["itching", "skin_rash"],
    
    # Fever / Chills (Crucial for Malaria/Typhoid/Dengue)
    "fever": ["fever", "high_fever", "mild_fever"],
    "hot": ["fever", "high_fever"],
    "chill": ["chills", "shivering"],
    "shiver": ["shivering", "chills"],
    
    # Pain / Aches
    "headache": ["headache"],
    "muscle": ["muscle_pain", "back_pain", "muscle_weakness"],
    "bone": ["muscle_pain", "joint_pain"],
    "joint": ["joint_pain", "knee_pain", "hip_joint_pain"],
    "back": ["back_pain", "neck_pain"],
    
    # Respiratory (Crucial for Pneumonia/Asthma)
    "cough": ["cough", "phlegm", "throat_irritation"],
    "breath": ["breathlessness"],
    "chest": ["chest_pain"],
    "lungs": ["breathlessness", "cough"],
    
    # Gastro / Digestive (Crucial for Gastroenteritis/Typhoid)
    "vomit": ["vomiting"], "nausea": ["nausea"],
    "loose": ["diarrhoea"], "constipat": ["constipation"],
    "toilet": ["diarrhoea", "constipation", "polyuria"],
    "diarrhea": ["diarrhoea"],
    "poop": ["diarrhoea", "constipation"],
    
    # Neurology
    "dizzy": ["unsteadiness", "dizziness"],
    "spinning": ["spinning_movements", "loss_of_balance"],
    "vision": ["blurred_and_distorted_vision", "visual_disturbances"],
    
    # Others
    "yellow": ["yellowish_skin", "yellowing_of_eyes", "dark_urine"],
    "tired": ["fatigue", "lethargy", "malaise"],
    "weak": ["fatigue", "muscle_weakness", "lethargy"]
}

def detect_intensity(text: str) -> str:
    t = text.lower()
    if any(w in t for w in HIGH_WORDS): return "HIGH"
    if any(w in t for w in LOW_WORDS): return "LOW"
    return "MEDIUM"

def detect_duration(text: str) -> str:
    t = text.lower()
    for level, keywords in DURATION_MAP.items():
        if any(kw in t for kw in keywords): return level
    return "HOURS"

def rule_based_extract(text: str, symptom_list: list) -> dict:
    t = (text or "").lower()
    found = []
    
    # 1. Broad Keyword Mapping (Broadcast)
    for kw, targets in KEYWORD_MAP.items():
        if kw in t:
            if isinstance(targets, list):
                found.extend(targets)
            else:
                found.append(targets)
                
    # 2. String Match Check
    for symptom in symptom_list:
        clean_s = symptom.replace("_", " ")
        if clean_s in t or symptom in t:
            found.append(symptom)
            
    # 3. Specific Phrases (High Precision)
    if "weight" in t:
        if "loss" in t or "lost" in t or "less" in t:
            found.append("weight_loss")
        if "gain" in t or "gained" in t or "more" in t or "increase" in t:
            found.append("weight_gain")
    if "pain" in t and "eye" in t:   found.append("pain_behind_the_eyes")
    if "neck" in t and "stiff" in t: found.append("stiff_neck")
    
    # HYPOGLYCEMIA ANCHORS (Crucial for Hackathon)
    if "shaky" in t or "trembling" in t or "anxious" in t:
        found.append("anxiety")
    if "too much" in t and ("eat" in t or "hungry" in t):
        found.append("excessive_hunger")
    if "slurred" in t or "speech" in t:
        found.append("slurred_speech")
    if "lip" in t or "tingling" in t:
        found.append("drying_and_tingling_lips")
        
    # PARALYSIS ANCHORS
    if "cannot move" in t or "can't move" in t or "paralyzed" in t:
        if "side" in t or "arm" in t or "leg" in t:
            found.append("weakness_of_one_body_side")
        
    # IMPETIGO ANCHORS (Safety from Hepatitis/Sore Throat)
    if ("crust" in t or "ooze" in t or "burst" in t):
        if "nose" in t or "mouth" in t or "face" in t:
            found.append("yellow_crust_ooze")
            found.append("red_sore_around_nose")
            found.append("blister")
    
    # Specific check for red_sore_around_nose (must NOT be sore throat)
    if "sore" in t and "nose" in t and "throat" not in t:
         found.append("red_sore_around_nose")

    # HEART ATTACK SAFETY (Exclude if hunger present)
    # NECK & SHOULDER (Orthopedic Anchors)
    if "neck" in t:
        if "pain" in t or "ache" in t or "stiff" in t:
            found.append("neck_pain")
    if "shoulder" in t and ("pain" in t or "ache" in t):
        found.append("shoulder_pain")
    if "stiff" in t and "neck" in t: 
        found.append("stiff_neck")
        
    if "burning" in t and ("urine" in t or "pee" in t or "toilet" in t):
        found.append("burning_micturition")

    return {
        "symptoms": list(dict.fromkeys(found))[:20],
        "intensity": detect_intensity(t),
        "duration":  detect_duration(t)
    }

def extract_symptoms_gemini(text: str, symptom_list: list, image_path: str = None) -> dict:
    """Extract symptoms using Google Gemini API with strict timeouts."""
    if not config.USE_GEMINI:
        return rule_based_extract(text, symptom_list)

    try:
        print(f"--- AI DIAGNOSIS START: '{text[:20]}...' ---")
        
        model_name = "gemini-flash-latest"
        try:
            model = genai.GenerativeModel(model_name)
        except Exception:
            model = genai.GenerativeModel("gemini-pro")
            
        symptom_list_str = ", ".join(symptom_list)
        prompt = f"""You are a Senior Diagnostic Consultant. 
Your task is to convert a patient's natural language into a precise list of medical symptoms for an ML model.

Available symptoms list: {symptom_list_str}

CRITICAL INSTRUCTIONS:
1. CATEGORY BOUNDARIES: 
   - 'Yellow crusts/ooze' or 'Sores' on the skin are Impetigo symptoms. They are NOT Jaundice/Hepatitis.
   - A 'sore throat' is a respiratory symptom (Common Cold/Flu). It is NOT 'red_sore_around_nose'.
2. PARALYSIS ANCHOR: If the patient mentions 'weakness of one side', 'can't move one side', or 'altered speech', you MUST include 'weakness_of_one_body_side'. This is NOT Hypertension.
3. DO NOT MISS FEVER: If 'hot' or 'chills' are mentioned, include 'fever'.
4. MAPPING ACCURACY:
   - 'Yellow crust ooze' -> 'yellow_crust_ooze' (Impetigo)
   - 'Red sore' on skin -> 'red_sore_around_nose' (Impetigo)
   - 'Sore throat' -> 'throat_irritation'
   - 'Can't move side' -> 'weakness_of_one_body_side' (Paralysis)

Return ONLY a JSON object.
Format:
{{
  "symptoms": ["exact_name_1", "exact_name_2"],
  "intensity": "HIGH"|"MEDIUM"|"LOW",
  "duration": "NEW"|"HOURS"|"DAYS"|"WEEK"|"CHRONIC"
}}"""
        
        inputs = [prompt]
        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                inputs.append(img)
            except Exception as img_err:
                print(f"Warning: Could not open image: {img_err}")

        # Increased timeout to 30 seconds for more reliability
        response = model.generate_content(
            inputs, 
            request_options={"timeout": 30}
        )
        
        raw = response.text.strip()
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(json_match.group() if json_match else raw)

        # Validate against known symptoms
        valid_symptoms = [s for s in result.get("symptoms", []) if s in symptom_list]
        
        # If Gemini found nothing but text exists, try rule-based as a secondary check
        if not valid_symptoms and text:
            rule_res = rule_based_extract(text, symptom_list)
            valid_symptoms = rule_res["symptoms"]

        final_res = {
            "symptoms": valid_symptoms,
            "intensity": result.get("intensity", "MEDIUM"),
            "duration": result.get("duration", "HOURS")
        }
        print(f"--- AI DIAGNOSIS SUCCESS: Found {len(valid_symptoms)} symptoms ---")
        return final_res

        return final_res

    except Exception as e:
        print(f"--- AI DIAGNOSIS FALLBACK: {type(e).__name__} ---")
        return rule_based_extract(text, symptom_list)

def refine_predictions_gemini(text: str, predictions: list) -> list:
    """
    Refines ML predictions using AI reasoning to resolve ambiguities.
    Takes the user's original text and the ML top-5.
    """
    if not config.USE_GEMINI or not predictions:
        return predictions

    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        
        candidates = ", ".join([p["disease"] for p in predictions])
        prompt = f"""A patient said: "{text}"
        
An ML model suggested these top candidates: {candidates}.

Your job is to be the CLINICAL TIE-BREAKER. 
The ML model sometimes confuses similar diseases. Use these rules:
1. DENGUE vs OSTEOARTHRITIS: If there is fever or rash, it MUST be Dengue.
2. PARALYSIS vs HYPERTENSION: If the patient cannot move one side of their body or has slurred speech, it is **Paralysis**, NOT Hypertension.
3. IMPETIGO vs HEPATITIS: If the 'yellow' symptoms are sores, crusts, or oozing on the skin, it is **Impetigo**. Hepatitis only applies if the skin/eyes themselves are turning yellow.
4. UTI vs DIABETES: If there is **burning** or **bladder pain**, it is **Urinary Tract Infection (UTI)**. Diabetes only involves high frequency (Polyuria) without burning.
5. PNEUMONIA vs TUBERCULOSIS (TB): This is CRITICAL. If symptoms are RECENT (days/hours), it is Pneumonia. If symptoms are LONG-TERM (weeks/months) with weight loss or night sweats, it is TB.
6. COMMON COLD vs INFLUENZA (FLU): If the patient has SEVERE body aches, high fever, and extreme fatigue, it is **Influenza**. If it is mostly sneezing, sore throat, and mild or no fever, it is **Common Cold**.
7. CHICKEN POX vs DENGUE: Chicken pox has itchy, fluid-filled blisters. Dengue has flat red rashes and intense bone/joint pain.
8. MALARIA vs TYPHOID: Malaria features intense periodic shivering/chills. Typhoid features abdominal pain and sustained 'step-ladder' fever.
9. IMPETIGO vs COMMON COLD: If the symptoms involve a **sore throat**, **runny nose**, or **sneezing**, it is the **Common Cold**. **Impetigo** ONLY applies if there are actual physical sores or crusty blisters on the face/nose skin.

Which of the candidates is the single most likely? 

Return ONLY a JSON object.
Format:
{{
  "boosted_disease": "Exact Disease Name",
  "reasoning": "Explain why this fits better than the others based on the specific symptoms mentioned."
}}"""

        response = model.generate_content(prompt, request_options={"timeout": 15})
        raw = response.text.strip()
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(json_match.group() if json_match else raw)
        
        boosted = result.get("boosted_disease")
        
        # Apply a 'Power Boost' to the matched disease
        for p in predictions:
            if p["disease"].lower() == boosted.lower():
                # If AI is confident, force it to be the top prediction (95%+)
                p["probability"] = max(p["probability"] + 0.50, 0.95) 
                p["percent"] = int(p["probability"] * 100)
                p["ai_refined"] = True
                p["ai_reasoning"] = result.get("reasoning")
        
        # Re-sort to ensure the boosted disease is #1
        predictions.sort(key=lambda x: x["probability"], reverse=True)
        
        # ─── Final Step: Normalization (Ensures total probability = 1.0) ──────────
        total = sum(p["probability"] for p in predictions)
        if total > 0:
            for p in predictions:
                p["probability"] /= total
                p["percent"] = int(p["probability"] * 100)

        return predictions

    except Exception as e:
        print(f"Refinement Error: {e}")
        return predictions

def analyze_image_gemini(image_path: str, text: str = None) -> dict:
    """
    Directly analyze an image (and optional text) using Gemini for disease prediction.
    Focuses on Dermatology and Ophthalmology.
    Returns: {
        "predictions": [{"disease": "Name", "probability": 0.85, "percent": 85}, ...],
        "department": "Dermatology" | "Ophthalmology",
        "reasoning": "..."
    }
    """
    if not config.USE_GEMINI:
        return None

    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        
        prompt = """You are a world-class Medical Diagnostic AI specializing in Dermatology (Skin) and Ophthalmology (Eyes).
A patient has provided an image for analysis. 

TASK:
1. Identify the single most likely clinical condition.
2. Provide the top 5 most likely diseases.
3. Assign probabilities that sum to 1.0. If you are highly confident, assign >80% to the top result.
4. Determine the primary medical department ('Dermatology' or 'Ophthalmology').
5. Provide a brief clinical reasoning highlighting visual features like 'pustules', 'comedones', 'inflammation', etc.

JSON STRUCTURE:
{
  "predictions": [
    {"disease": "Condition Name", "probability": 0.90, "percent": 90},
    ... (total 5)
  ],
  "department": "Dermatology",
  "reasoning": "Visible features of inflammatory acne noted..."
}"""

        inputs = []
        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                # Ensure image is in a good format for Gemini
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                inputs.append(img)
            except Exception as e:
                print(f"Error opening image: {e}")
                return None
        
        inputs.append(prompt)
        if text:
            inputs.append(f"Additional Patient Context: {text}")

        # Retry logic for transient errors
        for attempt in range(2):
            try:
                print(f"--- IMAGE ANALYSIS ATTEMPT {attempt+1} START ---")
                response = model.generate_content(inputs, request_options={"timeout": 60})
                
                if not response or not response.text:
                    print(f"Empty response from Gemini on attempt {attempt+1}")
                    continue
                    
                raw = response.text.strip()
                print(f"Raw AI Response: {raw[:200]}...") # Log start of response
                
                # Robust JSON extraction
                json_match = re.search(r"\{.*\}", raw, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = json.loads(raw)

                # Ensure predictions exists and is formatted correctly
                if "predictions" not in result or not result["predictions"]:
                    print("AI response missing 'predictions' key or empty.")
                    continue

                # Ensure percent and ai_refined tag
                for p in result.get("predictions", []):
                    if "percent" not in p:
                        # Ensure probability is a float and calculate percent
                        prob = float(p.get("probability", 0))
                        p["percent"] = int(prob * 100)
                    p["ai_refined"] = True
                
                print(f"--- IMAGE ANALYSIS SUCCESS: Found {len(result['predictions'])} predictions ---")
                return result
            except Exception as inner_e:
                print(f"Attempt {attempt+1} failed: {inner_e}")
                if attempt == 1: raise inner_e
                print(f"Retrying image analysis...")
        
        return None

    except Exception as e:
        print(f"Image Analysis Error: {e}")
        return None
