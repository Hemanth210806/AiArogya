"""
utils/claude_api.py — Claude API + fallback rule-based symptom extractor

Handles:
  - Text input → symptom extraction
  - Photo (base64) + text → vision + symptom extraction
  - Returns: {symptoms, intensity, duration, trigger}
"""

import os
import json
import re
import base64
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ─── Intensity keyword maps ───────────────────────────────────────────────────
HIGH_WORDS   = ["heavy", "severe", "worst", "unbearable", "crushing", "intense",
                "extreme", "terrible", "horrible", "excruciating", "acute"]
LOW_WORDS    = ["slight", "mild", "little", "minor", "small", "bit of", "bit",
                "slightly", "mildly", "faint", "dull"]

# ─── Duration keyword maps ───────────────────────────────────────────────────
DURATION_MAP = {
    "NEW":     ["just now", "few minutes", "suddenly", "right now"],
    "HOURS":   ["since morning", "few hours", "this morning", "today"],
    "DAYS":    ["since yesterday", "last night", "couple of days", "2 days", "3 days"],
    "WEEK":    ["past week", "last week", "a week", "7 days", "few days"],
    "CHRONIC": ["long time", "months", "years", "chronic", "always", "recurring"],
}

# ─── Common symptom keyword → dataset column name map ────────────────────────
KEYWORD_MAP = {
    "fever": "fever", "temperature": "fever", "high temperature": "fever",
    "cough": "cough", "coughing": "cough",
    "chest pain": "chest_pain", "chest ache": "chest_pain",
    "headache": "headache", "head pain": "headache", "head ache": "headache",
    "fatigue": "fatigue", "tired": "fatigue", "tiredness": "fatigue", "weakness": "fatigue",
    "nausea": "nausea", "vomiting": "vomiting", "vomit": "vomiting",
    "diarrhea": "diarrhoea", "loose stool": "diarrhoea", "loose motion": "diarrhoea",
    "diarrhoea": "diarrhoea",
    "sweating": "sweating", "sweats": "sweating",
    "breathlessness": "breathlessness", "shortness of breath": "breathlessness",
    "difficulty breathing": "breathlessness",
    "joint pain": "joint_pain", "joint ache": "joint_pain",
    "back pain": "back_pain", "backache": "back_pain",
    "stomach pain": "stomach_pain", "abdominal pain": "stomach_pain", "belly pain": "stomach_pain",
    "skin rash": "skin_rash", "rash": "skin_rash",
    "itching": "itching", "itchy": "itching",
    "yellowing": "yellowing_of_eyes", "yellow eyes": "yellowing_of_eyes",
    "jaundice": "yellowing_of_eyes",
    "weight loss": "weight_loss", "losing weight": "weight_loss",
    "loss of appetite": "loss_of_appetite", "no appetite": "loss_of_appetite",
    "constipation": "constipation",
    "anxiety": "anxiety", "panic": "anxiety",
    "muscle pain": "muscle_pain", "muscle ache": "muscle_pain",
    "throat pain": "throat_irritation", "sore throat": "throat_irritation",
    "runny nose": "runny_nose", "nasal discharge": "runny_nose",
    "burning urination": "burning_micturition",
    "frequent urination": "polyuria", "polyuria": "polyuria",
    "blurred vision": "blurred_and_distorted_vision",
    "swelling": "swelling_joints", "swollen": "swelling_joints",
    "dizziness": "dizziness", "dizzy": "dizziness",
    "depression": "depression",
    "irritability": "irritability",
}


def detect_intensity(text: str) -> str:
    text_lower = text.lower()
    for word in HIGH_WORDS:
        if word in text_lower:
            return "HIGH"
    for word in LOW_WORDS:
        if word in text_lower:
            return "LOW"
    return "MEDIUM"


def detect_duration(text: str) -> str:
    text_lower = text.lower()
    for level, keywords in DURATION_MAP.items():
        for kw in keywords:
            if kw in text_lower:
                return level
    return "HOURS"  # default


def rule_based_extract(text: str, symptom_list: list) -> dict:
    """Fallback extraction when Claude API key is not available."""
    text_lower = text.lower()
    found = []

    # Check KEYWORD_MAP first
    for kw, col in KEYWORD_MAP.items():
        if kw in text_lower and col in symptom_list:
            if col not in found:
                found.append(col)

    # Direct match against symptom_list column names
    for symptom in symptom_list:
        readable = symptom.replace("_", " ")
        if readable in text_lower and symptom not in found:
            found.append(symptom)

    # Deduplicate
    found = list(dict.fromkeys(found))

    return {
        "symptoms": found[:10],  # cap at 10
        "intensity": detect_intensity(text),
        "duration":  detect_duration(text),
        "trigger":   ""
    }


def extract_symptoms_claude(text: str, symptom_list: list, image_path: str = None) -> dict:
    """
    Extract symptoms using Claude API.
    Falls back to rule-based if API key is missing.

    Args:
        text:         Raw user input text (may be empty if image only)
        symptom_list: List of 132 symptom column names from dataset
        image_path:   Optional path to uploaded image file

    Returns:
        dict: {symptoms, intensity, duration, trigger}
    """
    # ── Fallback mode ────────────────────────────────────────────────────────
    if config.DEMO_CLAUDE:
        result = rule_based_extract(text or "", symptom_list)
        result["_mode"] = "rule_based"
        return result

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

        symptom_list_str = ", ".join(symptom_list)

        system_prompt = f"""You are a medical symptom extractor for ArogyaAI, an Indian healthcare app.

Your job is to analyze patient-described symptoms and extract structured information.

Available symptom names (EXACT column names from dataset — use ONLY these):
{symptom_list_str}

Return ONLY valid JSON in this exact format:
{{
  "symptoms": ["symptom_name1", "symptom_name2"],
  "intensity": "HIGH" or "MEDIUM" or "LOW",
  "duration": "NEW" or "HOURS" or "DAYS" or "WEEK" or "CHRONIC",
  "trigger": "any trigger mentioned or empty string"
}}

Intensity rules:
- HIGH: heavy, severe, worst, unbearable, crushing, intense, extreme
- LOW: slight, mild, little, minor, small, bit of
- MEDIUM: anything else

Duration rules:
- NEW: just now, few minutes, suddenly
- HOURS: since morning, few hours, today
- DAYS: since yesterday, couple of days
- WEEK: past week, 7 days
- CHRONIC: long time, months, years

Important:
- Only include symptoms that exactly match the dataset column names above
- Maximum 15 symptoms
- Return valid JSON only, no explanation"""

        # Build message content
        content = []

        # Add image if provided
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as img_file:
                img_data = base64.standard_b64encode(img_file.read()).decode("utf-8")

            ext = image_path.rsplit(".", 1)[-1].lower()
            media_type_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                              "png": "image/png",  "gif": "image/gif",
                              "webp": "image/webp"}
            media_type = media_type_map.get(ext, "image/jpeg")

            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": img_data
                }
            })

        # Add text
        user_text = text or "Please analyze the image above for medical symptoms."
        content.append({"type": "text", "text": user_text})

        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": content}]
        )

        raw = response.content[0].text.strip()

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = json.loads(raw)

        # Validate fields
        result.setdefault("symptoms", [])
        result.setdefault("intensity", "MEDIUM")
        result.setdefault("duration", "HOURS")
        result.setdefault("trigger", "")
        result["_mode"] = "claude"

        # Filter to only valid symptom names
        result["symptoms"] = [s for s in result["symptoms"] if s in symptom_list]

        return result

    except Exception as e:
        print(f"Claude API error: {e} - falling back to rule-based extraction")
        result = rule_based_extract(text or "", symptom_list)
        result["_mode"] = "rule_based_fallback"
        return result
