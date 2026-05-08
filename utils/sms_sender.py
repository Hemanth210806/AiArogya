"""
utils/sms_sender.py — Multi-provider SMS Sender (Twilio / Fast2SMS / Preview / WhatsApp Link)
"""

import sys, os
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def send_sms(to_number: str, message: str) -> dict:
    """
    Send SMS via Twilio or Fast2SMS. Returns dict with status.
    Falls back to preview mode if no provider configured.
    """
    provider = getattr(config, "SMS_PROVIDER", "demo")
    
    # Format number for WhatsApp (adding 91 for India if missing)
    clean_number = "".join(filter(str.isdigit, to_number))
    if len(clean_number) == 10:
        clean_number = "91" + clean_number
    
    wa_link = f"https://wa.me/{clean_number}?text={requests.utils.quote(message)}"

    if provider == "demo" or not to_number:
        return {"status": "preview", "message": message, "to": to_number, "wa_link": wa_link}

    # ─── Fast2SMS Integration ─────────────────────────────────────────────────
    if provider == "fast2sms":
        api_key = getattr(config, "FAST2SMS_API_KEY", "")
        if not api_key:
            return {"status": "error", "error": "Fast2SMS API key missing", "wa_link": wa_link}
        
        url = "https://www.fast2sms.com/dev/bulkV2"
        payload = {
            "message": message,
            "language": "english",
            "route": "q",
            "numbers": to_number,
        }
        headers = {'authorization': api_key, 'Content-Type': "application/x-www-form-urlencoded"}
        try:
            response = requests.post(url, data=payload, headers=headers)
            res_json = response.json()
            if res_json.get("return"):
                return {"status": "sent", "provider": "fast2sms", "wa_link": wa_link}
            else:
                return {"status": "error", "error": res_json.get("message", "API Error"), "wa_link": wa_link}
        except Exception as e:
            return {"status": "error", "error": str(e), "wa_link": wa_link}

    # ─── Twilio Integration ───────────────────────────────────────────────────
    if provider == "twilio":
        try:
            from twilio.rest import Client
            client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
            msg = client.messages.create(body=message, from_=config.TWILIO_PHONE, to=to_number)
            return {"status": "sent", "sid": msg.sid, "wa_link": wa_link}
        except Exception as e:
            return {"status": "error", "error": str(e), "wa_link": wa_link}

    return {"status": "preview", "message": message, "to": to_number, "wa_link": wa_link}


def send_critical_alert(emergency_contact: str, symptoms: list,
                        disease: str, probability: int) -> dict:
    message = f"""HEALTH ALERT - ArogyaAI
Reported Symptoms: {', '.join(symptoms[:5])}
Predicted: {disease} ({probability}%)
Severity: CRITICAL
Check on them immediately!
- ArogyaAI"""
    return send_sms(emergency_contact, message)


def send_appointment_confirmation(to_number: str, doctor_name: str,
                                  hospital_name: str, department: str,
                                  appt_date: str, appt_time: str,
                                  booking_id: str, fee: int) -> dict:
    message = f"""Appointment Confirmed - ArogyaAI
Doctor: {doctor_name}
Hospital: {hospital_name}
Date: {appt_date}
Time: {appt_time}
Booking ID: {booking_id}
- ArogyaAI"""
    return send_sms(to_number, message)
