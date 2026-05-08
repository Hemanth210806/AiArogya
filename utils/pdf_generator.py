"""
utils/pdf_generator.py — ReportLab PDF report generator for ArogyaAI
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Table, TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

GREEN  = colors.HexColor("#2E7D32")
BLUE   = colors.HexColor("#1565C0")
RED    = colors.HexColor("#C62828")
YELLOW = colors.HexColor("#F9A825")
LGRAY  = colors.HexColor("#F5F5F5")
DGRAY  = colors.HexColor("#424242")


def generate_report(data: dict, output_path: str) -> str:
    """
    Generate PDF health report.

    Args:
        data: dict with keys:
            patient_name, phone, symptoms_text, extracted_symptoms,
            predictions (list of {disease, percent}), severity_level,
            intensity, duration, precautions (list), department,
            hospital_name, doctor_name, appointment_date, appointment_time,
            booking_id, description
        output_path: Full path for output PDF

    Returns:
        output_path
    """
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles  = getSampleStyleSheet()
    story   = []

    # ── Title block ────────────────────────────────────────────────────────────
    title_style = ParagraphStyle("title", fontSize=22, textColor=GREEN,
                                 alignment=TA_CENTER, fontName="Helvetica-Bold")
    sub_style   = ParagraphStyle("sub",   fontSize=11, textColor=BLUE,
                                 alignment=TA_CENTER)
    story.append(Paragraph("ArogyaAI", title_style))
    story.append(Paragraph("Your AI Health Companion", sub_style))
    story.append(Paragraph("Health Analysis Report", sub_style))
    story.append(HRFlowable(width="100%", thickness=2, color=GREEN))
    story.append(Spacer(1, 0.3*cm))

    # ── Date + Patient Info ────────────────────────────────────────────────────
    now = datetime.now().strftime("%d %B %Y, %I:%M %p")
    info_data = [
        ["Date & Time", now],
        ["Patient Name", data.get("patient_name", "Guest")],
        ["Phone",        data.get("phone", "N/A")],
    ]
    info_table = Table(info_data, colWidths=[5*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), LGRAY),
        ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 10),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.lightgrey),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, LGRAY]),
        ("PADDING",    (0,0), (-1,-1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.5*cm))

    # ── Symptoms ───────────────────────────────────────────────────────────────
    h2 = ParagraphStyle("h2", fontSize=13, textColor=BLUE, fontName="Helvetica-Bold")
    story.append(Paragraph("📋 Symptoms Reported", h2))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(data.get("symptoms_text", "N/A"), styles["Normal"]))
    syms = data.get("extracted_symptoms", [])
    if syms:
        story.append(Paragraph(f"<b>Extracted:</b> {', '.join(syms)}", styles["Normal"]))
    story.append(Paragraph(
        f"<b>Intensity:</b> {data.get('intensity','N/A')} &nbsp;&nbsp; "
        f"<b>Duration:</b> {data.get('duration','N/A')}",
        styles["Normal"]))
    story.append(Spacer(1, 0.5*cm))

    # ── Top 5 Predictions ─────────────────────────────────────────────────────
    story.append(Paragraph("🔬 AI Disease Prediction (Top 5)", h2))
    story.append(Spacer(1, 0.2*cm))
    pred_data = [["#", "Disease", "Probability"]]
    for i, p in enumerate(data.get("predictions", [])[:5], 1):
        pred_data.append([str(i), p["disease"], f"{p['percent']}%"])
    pred_table = Table(pred_data, colWidths=[1*cm, 11*cm, 5*cm])
    pred_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), GREEN),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 10),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.lightgrey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LGRAY]),
        ("ALIGN",      (2,0), (2,-1), "CENTER"),
        ("PADDING",    (0,0), (-1,-1), 6),
    ]))
    story.append(pred_table)
    story.append(Spacer(1, 0.5*cm))

    # ── Severity ──────────────────────────────────────────────────────────────
    sev = data.get("severity_level", "MILD")
    sev_color = {"CRITICAL": RED, "MODERATE": YELLOW, "MILD": GREEN}.get(sev, GREEN)
    sev_style = ParagraphStyle("sev", fontSize=14, textColor=sev_color,
                               fontName="Helvetica-Bold")
    story.append(Paragraph("⚠️ Severity Assessment", h2))
    story.append(Paragraph(f"Severity Level: {sev}", sev_style))
    story.append(Paragraph(f"<b>Department Recommended:</b> {data.get('department','General Physician')}", styles["Normal"]))
    story.append(Spacer(1, 0.3*cm))

    # Description
    desc = data.get("description", "")
    if desc:
        story.append(Paragraph(f"<b>About this condition:</b> {desc}", styles["Normal"]))
        story.append(Spacer(1, 0.3*cm))

    # ── Precautions (from CSV) ────────────────────────────────────────────────
    precs = data.get("precautions", [])
    if precs:
        story.append(Paragraph("🛡️ Precautions", h2))
        story.append(Spacer(1, 0.2*cm))
        for i, p in enumerate(precs, 1):
            story.append(Paragraph(f"  {i}. {p}", styles["Normal"]))
        story.append(Spacer(1, 0.5*cm))

    # ── Appointment Info ──────────────────────────────────────────────────────
    if data.get("booking_id"):
        story.append(Paragraph("📅 Appointment Details", h2))
        appt_data = [
            ["Hospital",    data.get("hospital_name", "N/A")],
            ["Doctor",      data.get("doctor_name", "N/A")],
            ["Date & Time", f"{data.get('appointment_date','N/A')} at {data.get('appointment_time','N/A')}"],
            ["Booking ID",  data.get("booking_id", "N/A")],
        ]
        appt_table = Table(appt_data, colWidths=[5*cm, 12*cm])
        appt_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,-1), LGRAY),
            ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 10),
            ("GRID",       (0,0), (-1,-1), 0.5, colors.lightgrey),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, LGRAY]),
            ("PADDING",    (0,0), (-1,-1), 6),
        ]))
        story.append(appt_table)
        story.append(Spacer(1, 0.5*cm))

    # ── Footer disclaimer ─────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    disclaimer = ParagraphStyle("disc", fontSize=8, textColor=DGRAY,
                                alignment=TA_CENTER)
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "⚠️ This report is generated by AI and is NOT a substitute for professional "
        "medical advice. Always consult a qualified doctor for diagnosis and treatment.",
        disclaimer
    ))
    story.append(Paragraph("ArogyaAI — Your AI Health Companion | Emergency: 108", disclaimer))

    doc.build(story)
    return output_path
