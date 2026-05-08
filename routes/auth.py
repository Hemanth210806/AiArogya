"""routes/auth.py — Login / Guest / Logout"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, User

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        emg   = request.form.get("emergency_contact", "").strip()
        name  = request.form.get("name", "").strip()

        print(f"DEBUG: Login attempt - Phone: {phone}, Name: {name}, EMG: {emg}")

        if not phone:
            flash("Phone number is required.", "error")
            return render_template("login.html")

        # Use robust query pattern
        user = db.session.query(User).filter_by(phone=phone).first()
        
        if not user:
            print("DEBUG: Creating new user")
            user = User(phone=phone, emergency_contact=emg or None,
                        name=name or "Patient")
            db.session.add(user)
        else:
            print("DEBUG: Updating existing user")
            if emg:  user.emergency_contact = emg
            if name: user.name = name
            
        try:
            db.session.commit()
            print(f"DEBUG: User saved successfully. ID: {user.id}")
        except Exception as e:
            db.session.rollback()
            print(f"DEBUG: DB Error during login: {e}")
            flash("Database error. Please try again.", "error")
            return render_template("login.html")

        session["user_id"] = user.id
        session["phone"]   = user.phone
        session["name"]    = user.name or "Patient"
        session["emergency_contact"] = user.emergency_contact
        
        # Ensure session is saved
        session.modified = True
        print(f"DEBUG: Session set - Name: {session['name']}, ID: {session['user_id']}")
        
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@auth_bp.route("/guest")
def guest():
    session.clear()
    session["user_id"] = None
    session["phone"]   = "guest"
    session["name"]    = "Guest"
    return redirect(url_for("dashboard"))

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
