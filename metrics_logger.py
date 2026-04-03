"""
modules/metrics_logger.py
SQLite-based session and rep logging for rehabilitation outcome tracking.

Schema:
  sessions  → per-session summary
  reps      → per-rep gesture + ROM data
"""

import sqlite3
import json
import os
from datetime import datetime


class MetricsLogger:
    def __init__(self, db_path="data/rehab_sessions.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        print(f"[DB] Connected to {db_path}")

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id      TEXT    NOT NULL,
                full_name       TEXT,
                age             INTEGER,
                gender          TEXT,
                condition       TEXT,
                affected_side   TEXT,
                surgery_date    TEXT,
                doctor_name     TEXT,
                prev_therapy    TEXT,
                prev_therapy_weeks INTEGER,
                pain_before     INTEGER,
                session_goal    TEXT,
                therapist_name  TEXT,
                target_reps     INTEGER,
                therapist_notes TEXT,
                start_time      TEXT    NOT NULL,
                end_time        TEXT,
                difficulty      INTEGER DEFAULT 1,
                day_index       INTEGER DEFAULT 1,
                completed       INTEGER DEFAULT 0,
                score           INTEGER DEFAULT 0,
                level_reached   INTEGER DEFAULT 1,
                accuracy_pct    REAL    DEFAULT 0,
                sliced_count    INTEGER DEFAULT 0,
                missed_count    INTEGER DEFAULT 0,
                max_combo       INTEGER DEFAULT 0,
                duration_sec    REAL    DEFAULT 0,
                avg_rom_deg     REAL    DEFAULT 0,
                gesture_summary TEXT    DEFAULT '{}',
                notes           TEXT
            );

            CREATE TABLE IF NOT EXISTS reps (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER NOT NULL,
                timestamp   TEXT    NOT NULL,
                gesture     TEXT    NOT NULL,
                rom_angle   REAL    DEFAULT 0,
                success     INTEGER DEFAULT 1,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
        """)
        self.conn.commit()
        self._ensure_columns()

    def _ensure_columns(self):
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(sessions)")
        cols = [row[1] for row in cur.fetchall()]
        def add_col(name, ddl):
            if name not in cols:
                cur.execute(f"ALTER TABLE sessions ADD COLUMN {ddl}")
        add_col("full_name", "full_name TEXT")
        add_col("age", "age INTEGER")
        add_col("gender", "gender TEXT")
        add_col("condition", "condition TEXT")
        add_col("affected_side", "affected_side TEXT")
        add_col("surgery_date", "surgery_date TEXT")
        add_col("doctor_name", "doctor_name TEXT")
        add_col("prev_therapy", "prev_therapy TEXT")
        add_col("prev_therapy_weeks", "prev_therapy_weeks INTEGER")
        add_col("pain_before", "pain_before INTEGER")
        add_col("session_goal", "session_goal TEXT")
        add_col("therapist_name", "therapist_name TEXT")
        add_col("target_reps", "target_reps INTEGER")
        add_col("therapist_notes", "therapist_notes TEXT")
        if "day_index" not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN day_index INTEGER DEFAULT 1")
        if "completed" not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN completed INTEGER DEFAULT 0")
        self.conn.commit()

    # ──────────────────────────────────────────────────────────────────────────
    def start_session(self, patient_id="P001", difficulty=1, day_index=1, intake=None):
        """Create a new session record, return session_id."""
        intake = intake or {}
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO sessions
            (patient_id, full_name, age, gender, condition, affected_side, surgery_date,
             doctor_name, prev_therapy, prev_therapy_weeks, pain_before, session_goal,
             therapist_name, target_reps, therapist_notes, start_time, difficulty, day_index, completed)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                patient_id,
                intake.get("full_name"),
                intake.get("age"),
                intake.get("gender"),
                intake.get("condition"),
                intake.get("affected_side"),
                intake.get("surgery_date"),
                intake.get("doctor_name"),
                intake.get("prev_therapy"),
                intake.get("prev_therapy_weeks"),
                intake.get("pain_before"),
                intake.get("session_goal"),
                intake.get("therapist_name"),
                intake.get("target_reps"),
                intake.get("therapist_notes"),
                datetime.now().isoformat(),
                difficulty,
                int(day_index),
                0
            )
        )
        self.conn.commit()
        sid = cur.lastrowid
        print(f"[DB] Session {sid} started for {patient_id}")
        return sid

    # ──────────────────────────────────────────────────────────────────────────
    def log_rep(self, session_id, gesture, rom_angle, success=True):
        """Log a single repetition (gesture + ROM measurement)."""
        if gesture is None or gesture == "neutral":
            return
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO reps (session_id, timestamp, gesture, rom_angle, success) VALUES (?,?,?,?,?)",
            (session_id, datetime.now().isoformat(), gesture, float(rom_angle), int(success))
        )
        # Batch commit every 10 reps for performance
        if cur.lastrowid % 10 == 0:
            self.conn.commit()

    # ──────────────────────────────────────────────────────────────────────────
    def end_session(self, session_id, stats):
        """Update session record with final statistics."""
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE sessions SET
                end_time        = ?,
                score           = ?,
                level_reached   = ?,
                accuracy_pct    = ?,
                sliced_count    = ?,
                missed_count    = ?,
                max_combo       = ?,
                duration_sec    = ?,
                avg_rom_deg     = ?,
                gesture_summary = ?,
                completed       = 1
            WHERE id = ?
        """, (
            datetime.now().isoformat(),
            stats.get("score", 0),
            stats.get("level_reached", 1),
            stats.get("accuracy_pct", 0),
            stats.get("sliced", 0),
            stats.get("missed", 0),
            stats.get("max_combo", 0),
            stats.get("duration_sec", 0),
            stats.get("avg_rom_deg", 0),
            json.dumps(stats.get("gesture_counts", {})),
            session_id
        ))
        self.conn.commit()
        print(f"[DB] Session {session_id} saved. Score: {stats.get('score',0)}")

    # ──────────────────────────────────────────────────────────────────────────
    def get_patient_history(self, patient_id):
        """Return all sessions for a patient as list of dicts."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM sessions WHERE patient_id=? ORDER BY start_time DESC",
            (patient_id,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_week_progress(self, patient_id, days=7):
        """Return list of booleans for day completion."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT day_index, MAX(completed) FROM sessions WHERE patient_id=? GROUP BY day_index",
            (patient_id,)
        )
        rows = cur.fetchall()
        done = {int(day): int(comp) for day, comp in rows if day is not None}
        return [bool(done.get(i, 0)) for i in range(1, days + 1)]

    # ──────────────────────────────────────────────────────────────────────────
    def export_csv(self, patient_id, output_path="data/export.csv"):
        """Export session data to CSV for analysis / paper graphs."""
        import csv
        history = self.get_patient_history(patient_id)
        if not history:
            print("[DB] No data to export.")
            return
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=history[0].keys())
            writer.writeheader()
            writer.writerows(history)
        print(f"[DB] Exported {len(history)} sessions to {output_path}")

    # ──────────────────────────────────────────────────────────────────────────
    def close(self):
        self.conn.commit()
        self.conn.close()
