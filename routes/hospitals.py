"""routes/hospitals.py — Nearby hospitals (Geoapify/Google Maps + mock fallback)"""
from flask import Blueprint, render_template, session
import config
hospitals_bp = Blueprint("hospitals", __name__)

@hospitals_bp.route("/hospitals")
def hospitals():
    severity    = session.get("severity", {})
    department  = severity.get("department", "General Medicine")
    
    # Provider logic
    provider = config.MAPS_PROVIDER
    if provider == "geoapify":
        maps_key = config.GEOAPIFY_API_KEY
    else:
        maps_key = getattr(config, "GOOGLE_MAPS_API_KEY", "")

    # For hackathon simplicity, if key is missing, use demo
    demo_maps = not maps_key
    
    from utils.maps_helper import get_mock_hospitals
    mock_hospitals = get_mock_hospitals() if demo_maps else []
    
    return render_template("hospitals.html",
        department=department, 
        maps_key=maps_key,
        maps_provider=provider,
        demo_maps=demo_maps, 
        mock_hospitals=mock_hospitals)
