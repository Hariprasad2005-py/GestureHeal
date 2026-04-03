"""
GestureHeal: A Vision-Based Gamified System for Progressive Upper-Limb Rehabilitation
IEEE POC - Main Entry Point
"""

import os
import json

# Reduce noisy startup logs/prompts (must be set before importing the libs).
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")  # 0=all, 1=INFO, 2=WARNING, 3=ERROR

import sqlite3
import time
import math
import random
import sys
from datetime import datetime

# ─── Constants ────────────────────────────────────────────────────────────────
WINDOW_W, WINDOW_H = 1280, 720
CAM_W, CAM_H = 640, 480
FPS = 60
GAME_TITLE = "GestureHeal — Upper Limb Rehabilitation"

# Color Palette
COLOR_BG        = (8, 12, 28)
COLOR_ACCENT    = (0, 240, 180)
COLOR_WARN      = (255, 80, 60)
COLOR_WHITE     = (240, 245, 255)
COLOR_GRAY      = (80, 90, 110)
COLOR_GOLD      = (255, 200, 50)
COLOR_PANEL     = (15, 22, 45)

def load_intake_from_protocol_arg():
    """
    Reads intake data from rehabslash://start?data=<base64-json>
    passed as a command-line argument by the browser protocol handler.
    """
    import base64, urllib.parse
    for arg in sys.argv[1:]:
        if arg.lower().startswith("rehabslash://"):
            try:
                parsed = urllib.parse.urlparse(arg)
                qs     = urllib.parse.parse_qs(parsed.query)
                b64    = qs.get("data", [None])[0]
                if b64:
                    padded = b64 + "=" * (-len(b64) % 4)
                    raw    = base64.urlsafe_b64decode(padded).decode("utf-8")
                    data   = json.loads(raw)
                    return _normalize_intake(data)
            except Exception as e:
                print(f"[WARN] Could not parse protocol arg: {e}")
    return None

def _safe_patient_id(pid):
    return "".join(ch for ch in pid if ch.isalnum() or ch in ("-", "_")).strip()

def _safe_filename(name):
    safe = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_")).strip()
    return safe if safe else "patient"

def generate_patient_id():
    return f"P{datetime.now().strftime('%Y%m%d%H%M%S')}"

def _normalize_intake(intake):
    if not isinstance(intake, dict):
        raise ValueError("Intake must be an object.")

    def req_str(key, label=None):
        label = label or key
        val = intake.get(key, "")
        if val is None:
            val = ""
        val = str(val).strip()
        if not val:
            raise ValueError(f"{label} is required.")
        return val

    def req_int(key, label=None, min_value=None, max_value=None):
        label = label or key
        val = intake.get(key, None)
        if val is None or str(val).strip() == "":
            raise ValueError(f"{label} is required.")
        try:
            ival = int(val)
        except Exception:
            raise ValueError(f"{label} must be a number.")
        if min_value is not None and ival < min_value:
            raise ValueError(f"{label} must be >= {min_value}.")
        if max_value is not None and ival > max_value:
            raise ValueError(f"{label} must be <= {max_value}.")
        return ival

    full_name = req_str("full_name", "Full Name")
    age = req_int("age", "Age", min_value=1)
    gender = req_str("gender", "Gender")

    raw_pid = req_str("patient_id", "Patient ID")
    pid = _safe_patient_id(raw_pid)
    if not pid:
        raise ValueError("Patient ID can only contain letters, numbers, '-' and '_' .")

    condition = req_str("condition", "Condition")
    affected_side = req_str("affected_side", "Affected Side")

    surgery_date = req_str("surgery_date", "Surgery Date")
    try:
        datetime.strptime(surgery_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Surgery Date must be in YYYY-MM-DD format.")

    doctor_name = req_str("doctor_name", "Referring Doctor Name")
    prev_therapy = req_str("prev_therapy", "Previous Therapy")
    if prev_therapy not in ("Yes", "No"):
        raise ValueError("Previous Therapy must be Yes or No.")

    prev_weeks = intake.get("prev_therapy_weeks", None)
    if prev_therapy == "Yes":
        if prev_weeks is None or str(prev_weeks).strip() == "":
            raise ValueError("Previous Therapy Weeks is required when Previous Therapy is Yes.")
        try:
            prev_weeks = int(prev_weeks)
        except Exception:
            raise ValueError("Previous Therapy Weeks must be a number.")
        if prev_weeks <= 0:
            raise ValueError("Previous Therapy Weeks must be greater than 0.")
    else:
        prev_weeks = None

    pain_before = req_int("pain_before", "Pain Level", min_value=0, max_value=10)
    session_goal = req_str("session_goal", "Session Goal")
    target_reps = req_int("target_reps", "Target Reps", min_value=1)
    therapist_name = req_str("therapist_name", "Therapist / Supervisor Name")
    therapist_notes = req_str("therapist_notes", "Therapist Notes")

    return {
        "full_name": full_name,
        "age": age,
        "gender": gender,
        "patient_id": pid,
        "condition": condition,
        "affected_side": affected_side,
        "surgery_date": surgery_date,
        "doctor_name": doctor_name,
        "prev_therapy": prev_therapy,
        "prev_therapy_weeks": prev_weeks,
        "pain_before": pain_before,
        "session_goal": session_goal,
        "therapist_name": therapist_name,
        "target_reps": target_reps,
        "therapist_notes": therapist_notes,
    }

def load_intake_from_json(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _normalize_intake(data)
    except Exception as e:
        print(f"[WARN] Could not load intake from {path}: {e}")
        return None

def run_intake_form():
    import tkinter as tk
    from tkinter import ttk, messagebox
    try:
        from tkcalendar import DateEntry  # optional
    except Exception:
        DateEntry = None

    root = tk.Tk()
    root.title("GestureHeal — Patient Intake")
    root.geometry("860x820")
    root.resizable(False, False)

    # Basic modern styling (ttk + a light "card" layout)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    palette = {
        "bg": "#F5F7FB",
        "card": "#FFFFFF",
        "text": "#111827",
        "muted": "#6B7280",
        "border": "#D7DCE6",
        "accent": "#2563EB",
        "accent_hover": "#1D4ED8",
    }

    root.configure(bg=palette["bg"])
    style.configure("App.TFrame", background=palette["bg"])
    style.configure("Card.TFrame", background=palette["card"])

    style.configure(
        "Header.TLabel",
        background=palette["bg"],
        foreground=palette["text"],
        font=("Segoe UI", 20, "bold"),
    )
    style.configure(
        "Subheader.TLabel",
        background=palette["bg"],
        foreground=palette["muted"],
        font=("Segoe UI", 10),
    )
    style.configure(
        "Section.TLabel",
        background=palette["card"],
        foreground=palette["text"],
        font=("Segoe UI", 11, "bold"),
    )
    style.configure(
        "Field.TLabel",
        background=palette["card"],
        foreground=palette["muted"],
        font=("Segoe UI", 10),
    )

    style.configure("TEntry", padding=(8, 6))
    style.configure("TCombobox", padding=(6, 4))
    style.configure("TSpinbox", padding=(6, 4))

    style.configure(
        "Accent.TButton",
        background=palette["accent"],
        foreground="#FFFFFF",
        padding=(14, 10),
        font=("Segoe UI", 10, "bold"),
        borderwidth=0,
    )
    style.map(
        "Accent.TButton",
        background=[("active", palette["accent_hover"]), ("pressed", palette["accent_hover"])],
        foreground=[("disabled", "#E5E7EB")],
    )
    style.configure("TButton", padding=(14, 10), font=("Segoe UI", 10))

    values = {
        "full_name": tk.StringVar(),
        "age": tk.StringVar(),
        "gender": tk.StringVar(value="Male"),
        "patient_id": tk.StringVar(value=generate_patient_id()),
        "condition": tk.StringVar(value="Hand Surgery"),
        "affected_side": tk.StringVar(value="Right"),
        "surgery_date": tk.StringVar(),
        "doctor_name": tk.StringVar(),
        "prev_therapy": tk.StringVar(value="No"),
        "prev_therapy_weeks": tk.StringVar(),
        "pain_before": tk.StringVar(value="3"),
        "session_goal": tk.StringVar(value="Improve ROM"),
        "therapist_name": tk.StringVar(),
        "target_reps": tk.StringVar(value="50"),
    }

    def toggle_weeks(*_):
        if values["prev_therapy"].get() == "Yes":
            weeks_entry.config(state="normal")
        else:
            values["prev_therapy_weeks"].set("")
            weeks_entry.config(state="disabled")

    def submit():
        if not values["full_name"].get().strip():
            messagebox.showerror("Missing", "Full Name is required.")
            return

        age_text = values["age"].get().strip()
        if not age_text.isdigit():
            messagebox.showerror("Invalid", "Age must be a number.")
            return
        if int(age_text) <= 0:
            messagebox.showerror("Invalid", "Age must be greater than 0.")
            return

        if not values["gender"].get().strip():
            messagebox.showerror("Missing", "Gender is required.")
            return

        raw_pid = values["patient_id"].get().strip()
        if not raw_pid:
            messagebox.showerror("Missing", "Patient ID is required.")
            return
        safe_pid = _safe_patient_id(raw_pid)
        if not safe_pid:
            messagebox.showerror("Invalid", "Patient ID can only contain letters, numbers, '-' and '_' .")
            return
        values["patient_id"].set(safe_pid)

        if not values["condition"].get().strip():
            messagebox.showerror("Missing", "Condition is required.")
            return

        if not values["affected_side"].get().strip():
            messagebox.showerror("Missing", "Affected Side is required.")
            return

        surgery_date = values["surgery_date"].get().strip()
        if not surgery_date:
            messagebox.showerror("Missing", "Surgery Date is required.")
            return
        try:
            datetime.strptime(surgery_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid", "Surgery Date must be in YYYY-MM-DD format.")
            return

        if not values["doctor_name"].get().strip():
            messagebox.showerror("Missing", "Referring Doctor Name is required.")
            return

        if not values["prev_therapy"].get().strip():
            messagebox.showerror("Missing", "Previous Therapy is required.")
            return
        if values["prev_therapy"].get() == "Yes":
            weeks_text = values["prev_therapy_weeks"].get().strip()
            if not weeks_text.isdigit() or int(weeks_text) <= 0:
                messagebox.showerror("Invalid", "Previous Therapy Weeks must be a number greater than 0.")
                return

        pain = values["pain_before"].get().strip()
        if not pain.isdigit() or not (0 <= int(pain) <= 10):
            messagebox.showerror("Invalid", "Pain level must be 0-10.")
            return

        if not values["session_goal"].get().strip():
            messagebox.showerror("Missing", "Session Goal is required.")
            return

        if not values["target_reps"].get().strip().isdigit():
            messagebox.showerror("Invalid", "Target reps must be a number.")
            return
        if int(values["target_reps"].get().strip()) <= 0:
            messagebox.showerror("Invalid", "Target reps must be greater than 0.")
            return

        if not values["therapist_name"].get().strip():
            messagebox.showerror("Missing", "Therapist / Supervisor Name is required.")
            return

        if not notes.get("1.0", "end").strip():
            messagebox.showerror("Missing", "Therapist Notes is required.")
            return

        root.quit()

    def cancel():
        root.destroy()

    root.bind("<Escape>", lambda _e: cancel())
    root.bind("<Control-Return>", lambda _e: submit())

    root.protocol("WM_DELETE_WINDOW", cancel)

    app = ttk.Frame(root, padding=20, style="App.TFrame")
    app.pack(fill="both", expand=True)
    app.columnconfigure(0, weight=1)
    app.rowconfigure(1, weight=1)

    header = ttk.Frame(app, style="App.TFrame")
    header.grid(row=0, column=0, sticky="ew")
    ttk.Label(header, text="Patient Intake", style="Header.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        header,
        text="Fill the details to start the session. All fields are required.",
        style="Subheader.TLabel",
    ).grid(row=1, column=0, sticky="w", pady=(4, 0))

    frm = ttk.Frame(app, padding=16, style="Card.TFrame", relief="solid", borderwidth=1)
    frm.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
    frm.columnconfigure(0, weight=0)
    frm.columnconfigure(1, weight=1)

    row = 0
    def add_section(title_text):
        nonlocal row
        ttk.Label(frm, text=title_text, style="Section.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(10 if row else 0, 6)
        )
        row += 1
        ttk.Separator(frm, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        row += 1

    def add_row(label, widget):
        nonlocal row
        ttk.Label(frm, text=label, style="Field.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        widget.grid(row=row, column=1, sticky="ew", pady=6)
        row += 1

    add_section("Patient Information")
    full_name_entry = ttk.Entry(frm, textvariable=values["full_name"])
    add_row("Full Name *", full_name_entry)
    add_row("Age *", ttk.Entry(frm, textvariable=values["age"], width=12))
    add_row(
        "Gender *",
        ttk.Combobox(
            frm,
            textvariable=values["gender"],
            values=["Male", "Female", "Other"],
            width=14,
            state="readonly",
        ),
    )
    add_row("Patient ID *", ttk.Entry(frm, textvariable=values["patient_id"], width=22))

    add_section("Clinical Details")
    add_row(
        "Condition *",
        ttk.Combobox(
            frm,
            textvariable=values["condition"],
            values=["Hand Surgery", "Stroke Rehab", "Fracture Recovery", "Nerve Injury", "Other"],
            width=24,
            state="readonly",
        ),
    )
    add_row(
        "Affected Side *",
        ttk.Combobox(
            frm,
            textvariable=values["affected_side"],
            values=["Left", "Right", "Bilateral"],
            width=14,
            state="readonly",
        ),
    )
    if DateEntry is not None:
        surgery_date_widget = DateEntry(
            frm,
            textvariable=values["surgery_date"],
            width=20,
            date_pattern="yyyy-mm-dd",
        )
    else:
        surgery_date_widget = ttk.Entry(frm, textvariable=values["surgery_date"], width=22)
    add_row("Surgery Date *", surgery_date_widget)
    add_row("Referring Doctor Name *", ttk.Entry(frm, textvariable=values["doctor_name"], width=32))

    add_row(
        "Previous Therapy? *",
        ttk.Combobox(frm, textvariable=values["prev_therapy"], values=["Yes", "No"], width=12, state="readonly"),
    )
    weeks_entry = ttk.Entry(frm, textvariable=values["prev_therapy_weeks"], width=12, state="disabled")
    add_row("If Yes — Weeks Done *", weeks_entry)
    values["prev_therapy"].trace_add("write", toggle_weeks)

    add_section("Session Setup")
    add_row(
        "Pain Level (0–10) *",
        ttk.Spinbox(frm, from_=0, to=10, textvariable=values["pain_before"], width=8),
    )
    add_row(
        "Session Goal *",
        ttk.Combobox(
            frm,
            textvariable=values["session_goal"],
            values=["Improve ROM", "Build Strength", "Reduce Stiffness", "Coordination"],
            width=22,
            state="readonly",
        ),
    )
    add_row("Target Reps per Session *", ttk.Entry(frm, textvariable=values["target_reps"], width=12))
    add_row("Therapist / Supervisor Name *", ttk.Entry(frm, textvariable=values["therapist_name"], width=32))

    ttk.Label(frm, text="Therapist Notes *", style="Field.TLabel").grid(
        row=row, column=0, sticky="nw", padx=(0, 12), pady=6
    )
    notes_wrap = ttk.Frame(frm, style="Card.TFrame")
    notes_wrap.grid(row=row, column=1, sticky="ew", pady=6)
    notes_wrap.columnconfigure(0, weight=1)
    notes = tk.Text(
        notes_wrap,
        width=1,
        height=4,
        font=("Segoe UI", 10),
        bg=palette["card"],
        fg=palette["text"],
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground=palette["border"],
        highlightcolor=palette["accent"],
        padx=8,
        pady=6,
        wrap="word",
    )
    notes.grid(row=0, column=0, sticky="ew")
    notes_scroll = ttk.Scrollbar(notes_wrap, orient="vertical", command=notes.yview)
    notes_scroll.grid(row=0, column=1, sticky="ns")
    notes.configure(yscrollcommand=notes_scroll.set)
    row += 1

    btns = ttk.Frame(app, style="App.TFrame")
    btns.grid(row=2, column=0, sticky="e", pady=(14, 0))
    ttk.Button(btns, text="Cancel", command=cancel).pack(side="right", padx=(10, 0))
    ttk.Button(btns, text="Start Session", style="Accent.TButton", command=submit).pack(side="right")

    full_name_entry.focus_set()

    root.mainloop()

    if not root.winfo_exists():
        return None

    pid = values["patient_id"].get().strip()
    pid = _safe_patient_id(pid) or generate_patient_id()
    prev_weeks = values["prev_therapy_weeks"].get().strip()
    prev_weeks = int(prev_weeks) if values["prev_therapy"].get() == "Yes" and prev_weeks.isdigit() else None

    intake = {
        "full_name": values["full_name"].get().strip(),
        "age": int(values["age"].get().strip()),
        "gender": values["gender"].get(),
        "patient_id": pid,
        "condition": values["condition"].get(),
        "affected_side": values["affected_side"].get(),
        "surgery_date": values["surgery_date"].get().strip(),
        "doctor_name": values["doctor_name"].get().strip(),
        "prev_therapy": values["prev_therapy"].get(),
        "prev_therapy_weeks": prev_weeks,
        "pain_before": int(values["pain_before"].get().strip()),
        "session_goal": values["session_goal"].get(),
        "therapist_name": values["therapist_name"].get().strip(),
        "target_reps": int(values["target_reps"].get().strip()),
        "therapist_notes": notes.get("1.0", "end").strip(),
    }
    root.destroy()
    return intake

def generate_report_pdf(intake, stats, session_id, output_path):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    navy_hex = "#0B1320"
    ink_hex = "#111827"
    muted_hex = "#6B7280"
    line_hex = "#E5E7EB"
    panel_hex = "#F8FAFC"
    accent_hex = "#2563EB"
    green_hex = "#16A34A"
    red_hex = "#DC2626"

    navy = colors.HexColor(navy_hex)
    ink = colors.HexColor(ink_hex)
    muted = colors.HexColor(muted_hex)
    line = colors.HexColor(line_hex)
    panel = colors.HexColor(panel_hex)
    accent = colors.HexColor(accent_hex)
    green = colors.HexColor(green_hex)
    red = colors.HexColor(red_hex)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="GH_Title", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=ink, spaceAfter=6))
    styles.add(ParagraphStyle(name="GH_Brand", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, textColor=ink))
    styles.add(ParagraphStyle(name="GH_Small", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=muted, leading=12))
    styles.add(ParagraphStyle(name="GH_Label", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.8, textColor=muted, leading=10))
    styles.add(ParagraphStyle(name="GH_Value", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, textColor=ink, leading=13))
    styles.add(ParagraphStyle(name="GH_Section", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, textColor=muted, leading=11))
    styles.add(ParagraphStyle(name="GH_Body", parent=styles["Normal"], fontName="Helvetica", fontSize=10, textColor=ink, leading=15))

    def fmt_date_ymd_to_long(ymd):
        try:
            return datetime.strptime(ymd, "%Y-%m-%d").strftime("%B %d, %Y")
        except Exception:
            return str(ymd or "")

    def compute_postop_week(ymd):
        try:
            d = datetime.strptime(ymd, "%Y-%m-%d").date()
            today = datetime.now().date()
            delta = (today - d).days
            if delta < 0:
                return None
            return (delta // 7) + 1
        except Exception:
            return None

    pid = str(intake.get("patient_id", "")).strip()
    suffix = "".join(ch for ch in pid.upper() if ch.isalnum())[-5:] or "00000"
    report_id = f"GH-{datetime.now().strftime('%Y')}-{suffix}"

    patient_name = intake.get("full_name", "Patient")
    age_gender = f"{intake.get('age','')} / {intake.get('gender','')}"
    referral = intake.get("doctor_name", "")

    diagnosis = str(intake.get("condition", "")).strip()
    affected = str(intake.get("affected_side", "")).strip()
    affected_display = f"{affected} Hand" if affected in ("Left", "Right") else affected
    surgery_date_long = fmt_date_ymd_to_long(intake.get("surgery_date", ""))
    week = compute_postop_week(intake.get("surgery_date", ""))
    postop = f"Week {week}" if week is not None else "N/A"

    pain_target = f"Level {intake.get('pain_before','')} / 10"
    target_reps = f"{intake.get('target_reps','')} Reps"

    acc = stats.get("accuracy_pct", "")
    rom = stats.get("avg_rom_deg", "")
    reps_done = stats.get("sliced", "")

    try:
        acc_f = float(acc)
        acc_disp = f"{acc_f:.1f}%"
    except Exception:
        acc_disp = str(acc)

    try:
        rom_f = float(rom)
        rom_disp = f"{rom_f:.1f}°"
    except Exception:
        rom_disp = str(rom)

    try:
        reps_i = int(reps_done)
        reps_disp = f"{reps_i} Reps"
    except Exception:
        reps_disp = str(reps_done)

    post_pain = f"{intake.get('pain_before','')} / 10"

    gen_date = datetime.now().strftime("%B %d, %Y")
    gen_time = datetime.now().strftime("%H:%M:%S")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=48,
        leftMargin=48,
        topMargin=42,
        bottomMargin=54,
        title="GestureHeal — Clinical Assessment Report",
        author="GestureHeal",
    )

    def decorate(canvas, _doc):
        canvas.saveState()

        # Footer
        canvas.setStrokeColor(line)
        canvas.setLineWidth(1)
        canvas.line(doc.leftMargin, doc.bottomMargin - 18, letter[0] - doc.rightMargin, doc.bottomMargin - 18)
        canvas.setFillColor(muted)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 35, f"© {datetime.now().year} GestureHeal • HIPAA compliant document")
        canvas.drawRightString(letter[0] - doc.rightMargin, doc.bottomMargin - 35, "Page 01 of 01 • Confidential medical record")
        canvas.restoreState()

    story = []

    # Header: brand + report id
    header_left = Paragraph("<font color='#0B1320'><b>■</b></font>  <b>GestureHeal</b>", styles["GH_Brand"])
    header_right = Paragraph(
        f"<font color='{muted_hex}'>REPORT ID:</font> <b>{report_id}</b><br/>"
        f"<b>Generated:</b> {gen_date} • {gen_time}<br/>"
        f"<i>Authorized for Clinical Use Only</i>",
        ParagraphStyle("GH_R", parent=styles["GH_Small"], alignment=TA_RIGHT),
    )

    header = Table([[header_left, header_right]], colWidths=[doc.width * 0.55, doc.width * 0.45])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Clinical Assessment<br/>Report", styles["GH_Title"]))
    story.append(Spacer(1, 6))

    rule = Table([[""]], colWidths=[doc.width])
    rule.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, ink), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story.append(rule)

    # Patient information section
    story.append(Spacer(1, 6))
    story.append(Paragraph("PATIENT INFORMATION", styles["GH_Section"]))
    story.append(Spacer(1, 8))

    info_cells = [
        [Paragraph("FULL NAME", styles["GH_Label"]), Paragraph("PATIENT ID", styles["GH_Label"]), Paragraph("AGE / GENDER", styles["GH_Label"]), Paragraph("REFERRAL", styles["GH_Label"])],
        [Paragraph(patient_name, styles["GH_Value"]), Paragraph(pid, styles["GH_Value"]), Paragraph(age_gender, styles["GH_Value"]), Paragraph(referral, styles["GH_Value"])],
    ]
    info = Table(info_cells, colWidths=[doc.width * 0.27, doc.width * 0.18, doc.width * 0.22, doc.width * 0.33])
    info.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.75, line),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, line),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(info)
    story.append(Spacer(1, 14))

    # Clinical assessment
    story.append(Paragraph("CLINICAL ASSESSMENT", styles["GH_Section"]))
    story.append(Spacer(1, 8))

    clinical_rows = [
        [Paragraph("Primary Diagnosis", styles["GH_Small"]), Paragraph(f"<b>{diagnosis} Recovery</b>", styles["GH_Body"]), Paragraph("Affected Side", styles["GH_Small"]), Paragraph(f"<b>{affected_display}</b>", styles["GH_Body"])],
        [Paragraph("Surgical Date", styles["GH_Small"]), Paragraph(f"<b>{surgery_date_long}</b>", styles["GH_Body"]), Paragraph("Post-Op Progress", styles["GH_Small"]), Paragraph(f"<font color='{accent_hex}'><b>{postop}</b></font>", styles["GH_Body"])],
        [Paragraph("Pain Threshold (Target)", styles["GH_Small"]), Paragraph(f"<b>{pain_target}</b>", styles["GH_Body"]), Paragraph("Target Repetitions", styles["GH_Small"]), Paragraph(f"<b>{target_reps}</b>", styles["GH_Body"])],
    ]
    clinical = Table(clinical_rows, colWidths=[doc.width * 0.26, doc.width * 0.24, doc.width * 0.26, doc.width * 0.24])
    clinical.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), panel),
                ("BOX", (0, 0), (-1, -1), 0.75, line),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, line),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(clinical)
    story.append(Spacer(1, 16))

    # Performance metrics table
    story.append(Paragraph("SESSION PERFORMANCE METRICS", styles["GH_Section"]))
    story.append(Spacer(1, 8))

    baseline = stats.get("baseline_accuracy_pct", None)
    delta_text = "Baseline unavailable"
    delta_hex = muted_hex
    try:
        if baseline is not None:
            diff = float(acc) - float(baseline)
            sign = "+" if diff >= 0 else ""
            delta_text = f"{sign}{diff:.1f}% vs Baseline"
            delta_hex = green_hex if diff >= 0 else red_hex
    except Exception:
        pass

    metric_rows = [
        [Paragraph("<font color='#FFFFFF'><b>METRIC PARAMETERS</b></font>", styles["GH_Small"]), Paragraph("<font color='#FFFFFF'><b>RECORDED VALUE</b></font>", styles["GH_Small"]), Paragraph("<font color='#FFFFFF'><b>CLINICAL STATUS</b></font>", styles["GH_Small"])],
        [Paragraph("Session ID", styles["GH_Body"]), Paragraph(str(session_id), styles["GH_Body"]), Paragraph("Active Session Tracking", styles["GH_Body"])],
        [Paragraph("Movement Accuracy", styles["GH_Body"]), Paragraph(f"<font color='{accent_hex}'><b>{acc_disp}</b></font>", styles["GH_Body"]), Paragraph(f"<font color='{delta_hex}'><b>{delta_text}</b></font>", styles["GH_Body"])],
        [Paragraph("Range of Motion (Avg)", styles["GH_Body"]), Paragraph(f"<b>{rom_disp}</b>", styles["GH_Body"]), Paragraph("Within target parameters", styles["GH_Body"])],
        [Paragraph("Completed Repetitions", styles["GH_Body"]), Paragraph(f"<b>{reps_disp}</b>", styles["GH_Body"]), Paragraph(f"Target: {intake.get('target_reps','')} Reps", styles["GH_Body"])],
        [Paragraph("Post-Session Pain Level", styles["GH_Body"]), Paragraph(f"<font color='{red_hex}'><b>{post_pain}</b></font>", styles["GH_Body"]), Paragraph("At threshold", styles["GH_Body"])],
    ]
    metrics = Table(metric_rows, colWidths=[doc.width * 0.40, doc.width * 0.22, doc.width * 0.38])
    metrics.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.75, line),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, line),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, panel]),
            ]
        )
    )
    story.append(metrics)
    story.append(Spacer(1, 16))

    # Clinical interpretation
    story.append(Paragraph("CLINICAL INTERPRETATION", styles["GH_Section"]))
    story.append(Spacer(1, 8))

    surgeon_note = (
        f"<i>Patient {patient_name} is undergoing {diagnosis} rehabilitation with {affected} side involvement. "
        f"Reported pain level before session was {intake.get('pain_before','')} / 10. "
        f"Current session goal: {intake.get('session_goal','')}. "
        f"Average ROM achieved: {rom_disp} with {acc_disp} accuracy over {reps_disp}. "
        f"Focus should remain on improving stability and increasing active range of motion without exceeding the pain threshold.</i>"
    )
    quote_style = ParagraphStyle("GH_Q", parent=styles["GH_Body"], fontName="Helvetica-Bold", fontSize=24, leading=24, textColor=muted)
    quote_w = 30
    note_tbl = Table([[Paragraph("“", quote_style), Paragraph(surgeon_note, styles["GH_Body"])]], colWidths=[quote_w, doc.width - quote_w])
    note_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.75, line),
                ("LINEBEFORE", (0, 0), (0, 0), 3, navy),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(note_tbl)
    story.append(Spacer(1, 22))

    # Signatures
    tech_name = "System Automated Audit"
    clinician = intake.get("doctor_name", "").strip() or intake.get("therapist_name", "").strip() or "Clinician"
    sig = Table(
        [
            [
                Paragraph("<b>Technician Signature</b><br/>" + tech_name, styles["GH_Small"]),
                Paragraph(f"<b>Attending Clinician Signature</b><br/>{clinician}", ParagraphStyle("GH_SR", parent=styles["GH_Small"], alignment=TA_RIGHT)),
            ]
        ],
        colWidths=[doc.width * 0.5, doc.width * 0.5],
    )
    sig.setStyle(TableStyle([("LINEABOVE", (0, 0), (0, 0), 1, line), ("LINEABOVE", (1, 0), (1, 0), 1, line), ("TOPPADDING", (0, 0), (-1, -1), 10)]))
    story.append(sig)

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)

def main():
    intake = load_intake_from_protocol_arg()
    if intake is None:
        intake_path = os.environ.get("REHABSLASH_INTAKE_PATH") or os.path.join("data", "intake_latest.json")
        intake = load_intake_from_json(intake_path)
    if intake is None:
        intake = run_intake_form()
    if not intake:
        return

    import pygame

    pygame.init()
    pygame.font.init()

    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption(GAME_TITLE)
    clock = pygame.time.Clock()

    # Show a quick splash so the game window appears immediately.
    try:
        screen.fill(COLOR_BG)
        font = pygame.font.SysFont("Segoe UI", 42, bold=True)
        sub = pygame.font.SysFont("Segoe UI", 18)
        title_surf = font.render("Launching GestureHeal…", True, COLOR_WHITE)
        sub_surf = sub.render("Initializing camera + AI engine. Please wait.", True, (170, 180, 200))
        screen.blit(title_surf, (60, 80))
        screen.blit(sub_surf, (60, 140))
        pygame.display.flip()
        pygame.event.pump()
    except Exception:
        pass

    import cv2
    import numpy as np
    from modules.gesture_detector import GestureDetector
    from modules.metrics_logger import MetricsLogger
    from modules.game_engine import GameEngine
    from modules.ui_renderer import UIRenderer

    # ── Init subsystems ──
    detector  = GestureDetector()
    logger    = MetricsLogger("data/rehab_sessions.db")
    engine    = GameEngine(WINDOW_W // 2, WINDOW_H)
    renderer  = UIRenderer(screen, WINDOW_W, WINDOW_H, game_x=WINDOW_W // 2, game_w=WINDOW_W // 2)

    # ── Open webcam ──
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)

    if not cap.isOpened():
        print("[ERROR] Cannot open webcam. Running in DEMO mode (mouse control).")
        demo_mode = True
    else:
        demo_mode = False

    patient_id = intake.get("patient_id", "P001")
    session_id = None
    last_report_path = None
    selected_day = 1
    week_progress = [False] * 7
    next_day = 1
    running    = True
    state      = "MENU"   # MENU | LEVEL_SELECT | PLAYING | PAUSED | RESULTS

    while running:
        dt = clock.tick(FPS) / 1000.0  # delta-time in seconds

        # ── Read webcam frame ──
        frame_rgb   = None
        hand_data   = None
        cam_surface = None

        if not demo_mode:
            ret, frame_bgr = cap.read()
            if ret:
                frame_bgr  = cv2.flip(frame_bgr, 1)
                frame_rgb  = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                hand_data  = detector.process(frame_rgb)

                # Draw skeleton overlay on frame
                annotated  = detector.draw_landmarks(frame_rgb.copy(), hand_data)
                # Convert to pygame surface (small, shown in corner)
                cam_small  = cv2.resize(annotated, (WINDOW_W // 2, int((WINDOW_W // 2) * CAM_H / CAM_W)))
                cam_surf   = pygame.surfarray.make_surface(
                    np.transpose(cam_small, (1, 0, 2))
                )
                cam_surface = cam_surf

        # ── Events ──
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if state == "PLAYING":
                        state = "PAUSED"
                    elif state == "PAUSED":
                        state = "PLAYING"
                    else:
                        running = False
                if event.key == pygame.K_RETURN:
                    if state == "MENU":
                        week_progress = logger.get_week_progress(patient_id, days=7)
                        next_day = None
                        for i, done in enumerate(week_progress):
                            if not done:
                                next_day = i + 1
                                break
                        selected_day = next_day if next_day is not None else 7
                        state = "LEVEL_SELECT"
                    elif state == "LEVEL_SELECT":
                        if next_day is not None:
                            engine.reset(start_level=selected_day, lock_level=True)
                            session_id = logger.start_session(
                                patient_id=patient_id,
                                difficulty=engine.level,
                                day_index=selected_day,
                                intake=intake
                            )
                            state = "PLAYING"
                    elif state == "RESULTS":
                        engine.reset()
                        state = "MENU"
                if event.key == pygame.K_r and state == "RESULTS":
                    week_progress = logger.get_week_progress(patient_id, days=7)
                    next_day = None
                    for i, done in enumerate(week_progress):
                        if not done:
                            next_day = i + 1
                            break
                    if next_day is not None:
                        selected_day = next_day
                        engine.reset(start_level=selected_day, lock_level=True)
                        session_id = logger.start_session(
                            patient_id=patient_id,
                            difficulty=engine.level,
                            day_index=selected_day,
                            intake=intake
                        )
                        state = "PLAYING"
                if event.key == pygame.K_p and state == "RESULTS":
                    if last_report_path and os.path.exists(last_report_path):
                        try:
                            os.startfile(last_report_path)
                        except Exception as e:
                            print(f"[WARN] Could not open report: {e}")
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state == "LEVEL_SELECT":
                    mx, my = event.pos
                    for box in renderer.last_level_boxes:
                        x, y, w, h = box["rect"]
                        if x <= mx <= x + w and y <= my <= y + h:
                            day = box["day"]
                            if box["done"] or box["is_next"]:
                                selected_day = day
                            break

        # ── State Machine ──
        screen.fill(COLOR_BG)

        if state == "MENU":
            renderer.draw_menu(engine.level)

        elif state == "LEVEL_SELECT":
            renderer.draw_level_select(week_progress, next_day, selected_day, mouse_pos)

        elif state == "PLAYING":
            # Extract gesture / hand position for game control
            hands = []

            if hand_data and hand_data["detected"]:
                if hand_data.get("hands"):
                    for h in hand_data["hands"]:
                        g = h.get("gesture")
                        if g == "neutral":
                            g = None
                        hands.append({
                            "pos": h["index_tip_norm"],
                            "gesture": g,
                            "rom": h.get("rom_degrees", 0.0),
                        })
                else:
                    g = hand_data.get("gesture")
                    if g == "neutral":
                        g = None
                    hands.append({
                        "pos": hand_data["index_tip_norm"],
                        "gesture": g,
                        "rom": hand_data.get("rom_degrees", 0.0),
                    })
            elif demo_mode:
                mx, my   = pygame.mouse.get_pos()
                hand_pos = (mx / WINDOW_W, my / WINDOW_H)
                # Mouse button held = slashing gesture
                if pygame.mouse.get_pressed()[0]:
                    gesture = "swipe_left"
                elif my < WINDOW_H * 0.4:
                    gesture = "raise"
                else:
                    gesture = "swipe_right"
                hands.append({
                    "pos": hand_pos,
                    "gesture": gesture,
                    "rom": 0.0,
                })

            # Update game
            result = engine.update(dt, hands)
            for ev in engine.pop_slice_events():
                logger.log_rep(session_id, ev["gesture"], ev.get("rom_deg", 0.0), success=True)
            if result == "GAME_OVER":
                stats = engine.get_stats()
                if session_id is not None:
                    logger.end_session(session_id, stats)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = _safe_filename(intake.get("full_name", "patient"))
                    report_path = os.path.join("data", f"{safe_name}_report_{session_id}_{ts}.pdf")
                    generate_report_pdf(intake, stats, session_id, report_path)
                    last_report_path = report_path
                state = "RESULTS"

            # Draw game
            renderer.draw_game(engine, cam_surface, hand_data, demo_mode, dt)

        elif state == "PAUSED":
            renderer.draw_game(engine, cam_surface, hand_data, demo_mode, dt)
            renderer.draw_pause()

        elif state == "RESULTS":
            stats = engine.get_stats()
            renderer.draw_results(stats, engine.level)

        pygame.display.flip()

    # ── Cleanup ──
    cap.release()
    detector.close()
    logger.close()
    pygame.quit()
    sys.exit()
if __name__ == "__main__":
    main()
