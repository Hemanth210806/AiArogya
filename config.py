"""
config.py — ArogyaAI Configuration Settings
"""

import os

# ─── Flask Settings ───────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "arogya_ai_hackathon_2026_secret")

# ─── Directory Settings ───────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
DATABASE_DIR = os.path.join(BASE_DIR, "database")

# Ensure database directory exists
if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR, exist_ok=True)

# Use absolute path for SQLite
DATABASE_URL = f"sqlite:///{os.path.join(DATABASE_DIR, 'arogya.db')}"

# ─── Google Gemini AI API ─────────────────────────────────────────────────────
# AI for symptom extraction and health assistant
GEMINI_API_KEY = "AIzaSyCFwraC--6Tm2ufX10ojWR2sBsQitpmXNY"
USE_GEMINI     = True

# ─── Geoapify (Maps) API ───────────────────────────────────────────────────────
# Maps for hospital locator
GEOAPIFY_API_KEY = "5594c3a6781c4a51aad5a3567c6bbd6b"
MAPS_PROVIDER    = "geoapify"

# ─── SMS Gateway (Fast2SMS) ───────────────────────────────────────────────────
# Register at: https://www.fast2sms.com/
FAST2SMS_API_KEY = "rP4phG7cDnu9jRWxzEoZTIMJYsSO3y0mXgBAf6HL5bV2e8NCatm62h4OUdekaF5ocf9JAlPDiBtjIRWY"
SMS_PROVIDER     = "fast2sms"

# ─── Twilio (Optional) ────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID = ""
TWILIO_AUTH_TOKEN  = ""
TWILIO_PHONE       = ""
