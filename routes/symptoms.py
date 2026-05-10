"""routes/symptoms.py — Symptom input, Gemini API, ML prediction"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import json, os, re
from models import db, SymptomLog, Prediction

symptoms_bp = Blueprint("symptoms", __name__)

@symptoms_bp.route("/symptoms", methods=["GET"])
def symptom_input():
    return render_template("symptom_input.html")

@symptoms_bp.route("/analyze", methods=["POST"])
def analyze():
    from utils.gemini_api import extract_symptoms_gemini
    from utils.ml_predictor import predict_top5, get_symptom_list, get_bar_color
    from utils.severity_calc import calculate_severity
    from models import AnalysisHistory

    user_id    = session.get("user_id")
    text       = request.form.get("symptoms_text", "").strip()
    photo      = request.files.get("photo")
    photo_path = None

    # Clear old reasoning
    session.pop("ai_reasoning", None)

    if photo and photo.filename:
        import config
        from werkzeug.utils import secure_filename
        os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
        fname      = secure_filename(photo.filename)
        photo_path = os.path.join(config.UPLOAD_FOLDER, fname)
        photo.save(photo_path)

    try:
        symptom_list = get_symptom_list()
    except FileNotFoundError:
        flash("ML model not trained yet.", "error")
        return redirect(url_for("symptoms.symptom_input"))

    # ─── NEW: Direct Image Analysis (API-Only) ──────────────────────────────
    image_analysis = None
    ai_dept        = None
    predictions    = []
    intensity      = "MEDIUM"
    duration       = "HOURS"

    if photo_path:
        from utils.gemini_api import analyze_image_gemini
        print(f"DEBUG: Analyzing photo at {photo_path}")
        image_analysis = analyze_image_gemini(photo_path, text)
        print(f"DEBUG: Image Analysis Result: {image_analysis}")
        
        if image_analysis and image_analysis.get("predictions"):
            predictions = image_analysis["predictions"]
            extracted_symptoms = ["Image Analysis (Specialized)"]
            ai_dept = image_analysis.get("department")
            # We'll store reasoning in the session for later display
            session["ai_reasoning"] = image_analysis.get("reasoning")
        else:
            # If photo was uploaded but analysis failed, don't fall back to ML if text is also empty
            if not text:
                print("DEBUG: Image analysis failed and no text provided. Flashing error.")
                flash("AI Image Analysis failed to identify the condition. Please try a clearer photo or describe the symptoms in the text box.", "warning")
                return redirect(url_for("symptoms.symptom_input"))
    
    # Fallback to Symptom Extraction + ML if no image results
    if not predictions:
        extraction = extract_symptoms_gemini(text, symptom_list, photo_path)
        extracted_symptoms = extraction.get("symptoms", [])
        intensity          = extraction.get("intensity", "MEDIUM")
        duration           = extraction.get("duration", "HOURS")

        if not extracted_symptoms:
            # ─── Ghost AI Predictor ────────────────────────────────
            from utils.gemini_api import get_gemini_response
            ai_prompt = f"""A patient described these symptoms: '{text}'. 
            Our primary model couldn't find a confident match. Based on your medical expertise, what are the top 5 most likely diseases?
            
            Return ONLY a JSON list of top 5 objects.
            Format: [{"disease": "Name", "probability": 0.85, "percent": 85}, ...]
            Rules: 
            - Probabilities must sum to 1.0. 
            - Use common clinical names (e.g., 'Acne', 'Dengue', 'Migraine')."""
            
            try:
                ai_raw = get_gemini_response(ai_prompt)
                json_match = re.search(r"\[.*\]", ai_raw, re.DOTALL)
                ai_predictions = json.loads(json_match.group() if json_match else ai_raw)
                for p in ai_predictions: p["ai_refined"] = True
                predictions = ai_predictions
                extracted_symptoms = ["General Symptoms (AI Analyzed)"]
            except Exception as e:
                print(f"Ghost AI Error: {e}")
                flash("We couldn't identify specific symptoms. Please try again.", "warning")
                return redirect(url_for("symptoms.symptom_input"))
        else:
            predictions = predict_top5(extracted_symptoms)
            # AI Reasoning Refinement (Hybrid Model)
            from utils.gemini_api import refine_predictions_gemini
            predictions = refine_predictions_gemini(text, predictions)
    
    # ─── Post-Prediction Processing ──────────────────────────────────────────
    recurring_symptoms = []
    if user_id:
        history = AnalysisHistory.query.filter_by(user_id=user_id).order_by(AnalysisHistory.created_at.desc()).limit(5).all()
        all_past_symptoms = []
        for h in history:
            all_past_symptoms.extend(json.loads(h.symptoms_entered or "[]"))
        from collections import Counter
        counts = Counter(all_past_symptoms)
        recurring_symptoms = [s for s in extracted_symptoms if counts.get(s, 0) >= 2]
        
        # History Boost (Only if not already AI refined)
        if not any(p.get("ai_refined") for p in predictions):
            past_diseases = [h.predicted_disease for h in history]
            for p in predictions:
                if p["disease"] in past_diseases:
                    p["probability"] += 0.10
                    p["probability"] = min(1.0, p["probability"])
                    p["percent"] = int(p["probability"] * 100)
            predictions.sort(key=lambda x: x["probability"], reverse=True)

    top_disease  = predictions[0]["disease"] if predictions else "Unknown"
    top_prob     = predictions[0]["probability"] if predictions else 0.0
    severity_info = calculate_severity(extracted_symptoms, intensity, duration, top_disease, top_prob, department_override=ai_dept)
    severity_info["recurring_warning"] = recurring_symptoms

    for p in predictions:
        p["color"] = get_bar_color(p["percent"])

    if user_id:
        from datetime import datetime, timezone, timedelta
        # Adjust to local time (IST +5:30)
        local_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        
        log = SymptomLog(
            user_id=user_id,
            symptoms_text=text,
            extracted_symptoms=json.dumps(extracted_symptoms),
            photo_path=photo_path,
            intensity=intensity,
            duration=duration,
            created_at=local_now
        )
        db.session.add(log)
        db.session.flush()

        for p in predictions:
            pred = Prediction(
                user_id=user_id,
                symptom_log_id=log.id,
                disease=p["disease"],
                probability=p["probability"],
                severity=severity_info["level"],
                department=severity_info["department"],
                created_at=local_now
            )
            db.session.add(pred)
        
        # Save to AnalysisHistory
        history_entry = AnalysisHistory(
            user_id=user_id,
            symptoms_entered=json.dumps(extracted_symptoms),
            predicted_disease=top_disease,
            confidence_score=top_prob,
            all_predictions=json.dumps(predictions),
            created_at=local_now
        )
        db.session.add(history_entry)
        
        db.session.commit()
        session["symptom_log_id"] = log.id

    session["predictions"]   = predictions
    session["intensity"]     = intensity
    session["duration"]      = duration
    session["severity"]      = severity_info
    session["top_disease"]   = top_disease
    session["extracted_symptoms"] = extracted_symptoms
    session["selected_department"] = severity_info.get("department", "General Medicine")

    return redirect(url_for("symptoms.results"))

@symptoms_bp.route("/results")
def results():
    return render_template("results.html",
        predictions=session.get("predictions", []),
        intensity=session.get("intensity", "MEDIUM"),
        duration=session.get("duration", "HOURS"),
        severity=session.get("severity", {}),
        top_disease=session.get("top_disease", ""),
        extracted_symptoms=session.get("extracted_symptoms", []),
        ai_reasoning=session.get("ai_reasoning"))
