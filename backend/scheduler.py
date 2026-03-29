import os
import json
import threading
from datetime import datetime, timedelta

_scheduler = None
_lock = threading.Lock()
SENT_LOG_TABLE_READY = False


def _ensure_sent_log_table():
    global SENT_LOG_TABLE_READY
    if SENT_LOG_TABLE_READY:
        return
    try:
        from backend.database import execute_query
        execute_query("""
            CREATE TABLE IF NOT EXISTS reminder_logs (
                id        SERIAL PRIMARY KEY,
                cache_key VARCHAR(200) UNIQUE NOT NULL,
                sent_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """, fetch=False)
        # Clean up logs older than 2 days
        execute_query("""
            DELETE FROM reminder_logs
            WHERE sent_at < NOW() - INTERVAL '2 days'
        """, fetch=False)
        SENT_LOG_TABLE_READY = True
        print("[Scheduler] ✅ reminder_logs table ready.")
    except Exception as e:
        print(f"[Scheduler] Log table error: {e}")


def _already_sent(cache_key: str) -> bool:
    try:
        from backend.database import execute_query
        rows = execute_query(
            "SELECT 1 FROM reminder_logs WHERE cache_key = %s",
            (cache_key,)
        )
        return len(rows) > 0
    except:
        return False


def _mark_sent(cache_key: str):
    try:
        from backend.database import execute_query
        execute_query(
            "INSERT INTO reminder_logs (cache_key) VALUES (%s) ON CONFLICT DO NOTHING",
            (cache_key,),
            fetch=False
        )
    except Exception as e:
        print(f"[Scheduler] Mark sent error: {e}")


def check_medication_reminders():
    """
    Called every 5 minutes by GitHub Actions.
    Checks a 7-minute window to catch any reminder within the 5-min cron gap.
    """
    _ensure_sent_log_table()
    from backend.database import execute_query
    from backend.email_service import send_medication_reminder

    now          = datetime.now()
    window_start = (now + timedelta(minutes=4)).strftime("%H:%M")
    window_end   = (now + timedelta(minutes=11)).strftime("%H:%M")

    print(f"[Scheduler] 💊 Checking medications | window {window_start} → {window_end}")

    try:
        rows = execute_query("""
            SELECT m.id, m.medication_name, m.dosage, m.frequency,
                   m.reminder_times, p.name, p.email
            FROM medications m
            JOIN patients p ON p.id = m.patient_id
            WHERE m.is_active  = TRUE
              AND m.reminder_times IS NOT NULL
              AND m.end_date  >= CURRENT_DATE
        """, ())

        if not rows:
            print("[Scheduler] No active medications found.")
            return

        for row in rows:
            try:
                times = json.loads(row["reminder_times"]) if row["reminder_times"] else []
            except Exception:
                continue

            for t in times:
                # Handle both "HH:MM" and "HH:MM:SS"
                t_short = t[:5]
                if not (window_start <= t_short <= window_end):
                    continue

                cache_key = f"med_{row['id']}_{now.strftime('%Y-%m-%d')}_{t_short}"
                if _already_sent(cache_key):
                    print(f"[Scheduler] Already sent {cache_key}, skipping.")
                    continue

                print(f"[Scheduler] 💊 Sending → {row['email']} | {row['medication_name']} at {t_short}")
                ok = send_medication_reminder(
                    to_email       = row["email"],
                    patient_name   = row["name"],
                    med_name       = row["medication_name"],
                    dosage         = row.get("dosage") or "",
                    frequency      = row.get("frequency") or "",
                    reminder_times = times,
                )
                if ok:
                    _mark_sent(cache_key)

    except Exception as e:
        print(f"[Scheduler] Medication check error: {e}")


def check_appointment_reminders():
    """
    Called every 5 minutes by GitHub Actions.
    Sends reminders 1 day before and 1 hour before appointments.
    """
    _ensure_sent_log_table()
    from backend.database import execute_query
    from backend.email_service import send_appointment_reminder

    now = datetime.now()

    windows = [
        (
            "1 day before",
            now + timedelta(hours=23, minutes=55),
            now + timedelta(hours=24, minutes=10),
        ),
        (
            "1 hour before",
            now + timedelta(minutes=55),
            now + timedelta(hours=1, minutes=10),
        ),
    ]

    for label, win_start, win_end in windows:
        print(f"[Scheduler] 📅 Checking appointments | {label}")
        try:
            rows = execute_query("""
                SELECT a.id, a.doctor_name, a.specialty, a.appointment_date,
                       p.name, p.email
                FROM appointments a
                JOIN patients p ON p.id = a.patient_id
                WHERE a.status = 'scheduled'
                  AND a.appointment_date BETWEEN %s AND %s
            """, (win_start, win_end))

            if not rows:
                print(f"[Scheduler] No appointments in window for {label}.")
                continue

            for row in rows:
                cache_key = f"appt_{row['id']}_{label}"
                if _already_sent(cache_key):
                    print(f"[Scheduler] Already sent {cache_key}, skipping.")
                    continue

                appt_str = row["appointment_date"].strftime("%B %d, %Y at %H:%M")
                print(f"[Scheduler] 📅 Sending ({label}) → {row['email']}")
                ok = send_appointment_reminder(
                    to_email     = row["email"],
                    patient_name = row["name"],
                    doctor       = row["doctor_name"] or "Your Doctor",
                    specialty    = row.get("specialty") or "",
                    appt_dt      = appt_str,
                    timeframe    = label,
                )
                if ok:
                    _mark_sent(cache_key)

        except Exception as e:
            print(f"[Scheduler] Appointment check error ({label}): {e}")


def start_scheduler():
    """
    Called from app.py — runs a lightweight background thread
    only as a fallback while the Streamlit app is active.
    The real scheduling is handled by GitHub Actions.
    """
    global _scheduler

    with _lock:
        if _scheduler is not None and _scheduler.is_alive():
            print("[Scheduler] Already running — skipping.")
            return

        import threading
        import time

        def _loop():
            print("[Scheduler] ✅ Fallback scheduler thread started.")
            while True:
                check_medication_reminders()
                check_appointment_reminders()
                time.sleep(300)  # every 5 minutes

        _scheduler = threading.Thread(target=_loop, daemon=True)
        _scheduler.start()