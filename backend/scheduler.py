import threading
import time
import json
from datetime import datetime, timedelta
from backend.database import execute_query
from backend.email_service import send_medication_reminder, send_appointment_reminder

_sent_cache: set = set()

FREQ_REMINDER_COUNT = {
    "Once daily":        1,
    "Twice daily":       2,
    "Three times daily": 3,
    "Every 8 hours":     3,
    "Every 12 hours":    2,
    "As needed":         1,
    "Weekly":            1,
}


def _check_medication_reminders():
    now          = datetime.now()
    window_start = (now + timedelta(minutes=4, seconds=30)).strftime("%H:%M")
    window_end   = (now + timedelta(minutes=5, seconds=30)).strftime("%H:%M")

    try:
        rows = execute_query("""
            SELECT m.id, m.medication_name, m.dosage, m.frequency,
                   m.reminder_times, p.name, p.email
            FROM medications m
            JOIN patients p ON p.id = m.patient_id
            WHERE m.is_active = TRUE
              AND m.reminder_times IS NOT NULL
        """, ())

        for row in rows:
            try:
                times = json.loads(row["reminder_times"]) if row["reminder_times"] else []
            except Exception:
                continue

            for t in times:
                # t is stored as "HH:MM"
                if not (window_start <= t <= window_end):
                    continue
                cache_key = f"med_{row['id']}_{now.strftime('%Y-%m-%d')}_{t}"
                if cache_key in _sent_cache:
                    continue
                print(f"[Scheduler] 💊 Medication reminder → {row['email']} at {t}")
                send_medication_reminder(
                    to_email     = row["email"],
                    patient_name = row["name"],
                    med_name     = row["medication_name"],
                    dosage       = row.get("dosage") or "",
                    frequency    = row.get("frequency") or "",
                )
                _sent_cache.add(cache_key)

    except Exception as e:
        print(f"[Scheduler] Medication check error: {e}")


def _check_appointment_reminders():
    now = datetime.now()
    windows = [
        ("1 day before",
         now + timedelta(hours=23, minutes=55),
         now + timedelta(hours=24, minutes=5)),
        ("1 hour before",
         now + timedelta(minutes=55),
         now + timedelta(hours=1,  minutes=5)),
    ]

    for label, win_start, win_end in windows:
        try:
            rows = execute_query("""
                SELECT a.id, a.doctor_name, a.specialty, a.appointment_date,
                       p.name, p.email
                FROM appointments a
                JOIN patients p ON p.id = a.patient_id
                WHERE a.status = 'scheduled'
                  AND a.appointment_date BETWEEN %s AND %s
            """, (win_start, win_end))

            for row in rows:
                cache_key = f"appt_{row['id']}_{label}"
                if cache_key in _sent_cache:
                    continue
                appt_str = row["appointment_date"].strftime("%B %d, %Y at %H:%M")
                print(f"[Scheduler] 📅 Appointment reminder ({label}) → {row['email']}")
                send_appointment_reminder(
                    to_email     = row["email"],
                    patient_name = row["name"],
                    doctor       = row["doctor_name"] or "Your Doctor",
                    specialty    = row.get("specialty") or "",
                    appt_dt      = appt_str,
                    timeframe    = label,
                )
                _sent_cache.add(cache_key)

        except Exception as e:
            print(f"[Scheduler] Appointment check error ({label}): {e}")


def _scheduler_loop():
    print("[Scheduler] ✅ Background reminder service running.")
    while True:
        _check_medication_reminders()
        _check_appointment_reminders()
        time.sleep(60)


def start_scheduler():
    t = threading.Thread(target=_scheduler_loop, daemon=True)
    t.start()