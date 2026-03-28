"""
CRUD operations for all health tracking entities
"""
import hashlib
from datetime import datetime, date
from backend.database import execute_query, execute_one, execute_insert


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ── AUTH ──────────────────────────────────────────────────────────────────────

def register_patient(data: dict):
    data["password_hash"] = hash_password(data.pop("password"))
    query = """
        INSERT INTO patients (name, age, gender, email, password_hash, phone,
                              blood_group, height, allergies, chronic_conditions, emergency_contact)
        VALUES (%(name)s, %(age)s, %(gender)s, %(email)s, %(password_hash)s, %(phone)s,
                %(blood_group)s, %(height)s, %(allergies)s, %(chronic_conditions)s, %(emergency_contact)s)
        RETURNING *
    """
    return execute_insert(query, data)


def login_patient(email: str, password: str):
    password_hash = hash_password(password)
    return execute_one(
        "SELECT * FROM patients WHERE email = %s AND password_hash = %s",
        (email, password_hash)
    )


def email_exists(email: str) -> bool:
    result = execute_one("SELECT id FROM patients WHERE email = %s", (email,))
    return result is not None


# ── PATIENTS ──────────────────────────────────────────────────────────────────

def get_patient(patient_id: str):
    return execute_one("SELECT * FROM patients WHERE id = %s", (patient_id,))


def update_patient(patient_id: str, data: dict):
    data["id"] = patient_id
    data["updated_at"] = datetime.now()
    query = """
        UPDATE patients SET name=%(name)s, age=%(age)s, gender=%(gender)s,
            phone=%(phone)s, blood_group=%(blood_group)s, height=%(height)s,
            allergies=%(allergies)s, chronic_conditions=%(chronic_conditions)s,
            emergency_contact=%(emergency_contact)s, updated_at=%(updated_at)s
        WHERE id=%(id)s RETURNING *
    """
    return execute_insert(query, data)


def update_password(patient_id: str, new_password: str):
    password_hash = hash_password(new_password)
    execute_query(
        "UPDATE patients SET password_hash = %s WHERE id = %s",
        (password_hash, patient_id), fetch=False
    )


# ── VITALS ────────────────────────────────────────────────────────────────────

def record_vitals(data: dict):
    query = """
        INSERT INTO vitals (patient_id, heart_rate, blood_pressure_systolic,
                            blood_pressure_diastolic, temperature, spo2, weight, blood_glucose)
        VALUES (%(patient_id)s, %(heart_rate)s, %(blood_pressure_systolic)s,
                %(blood_pressure_diastolic)s, %(temperature)s, %(spo2)s, %(weight)s, %(blood_glucose)s)
        RETURNING *
    """
    return execute_insert(query, data)


def get_patient_vitals(patient_id: str, limit: int = 30):
    return execute_query(
        "SELECT * FROM vitals WHERE patient_id = %s ORDER BY recorded_at DESC LIMIT %s",
        (patient_id, limit)
    )


def get_latest_vitals(patient_id: str):
    return execute_one(
        "SELECT * FROM vitals WHERE patient_id = %s ORDER BY recorded_at DESC LIMIT 1",
        (patient_id,)
    )


# ── SYMPTOMS ──────────────────────────────────────────────────────────────────

def record_symptom(data: dict):
    query = """
        INSERT INTO symptoms (patient_id, symptoms_text, severity, ai_analysis,
                              ai_recommendation, risk_level)
        VALUES (%(patient_id)s, %(symptoms_text)s, %(severity)s, %(ai_analysis)s,
                %(ai_recommendation)s, %(risk_level)s)
        RETURNING *
    """
    return execute_insert(query, data)


def get_patient_symptoms(patient_id: str, limit: int = 20):
    return execute_query(
        "SELECT * FROM symptoms WHERE patient_id = %s ORDER BY recorded_at DESC LIMIT %s",
        (patient_id, limit)
    )


# ── MEDICATIONS ───────────────────────────────────────────────────────────────

def add_medication(data: dict):
    import json
    return execute_insert("""
        INSERT INTO medications
            (patient_id, medication_name, dosage, frequency,
             start_date, end_date, prescribed_by, reminder_times, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (
        data["patient_id"],
        data["medication_name"],
        data.get("dosage"),
        data.get("frequency"),
        data.get("start_date"),
        data.get("end_date"),
        data.get("prescribed_by"),
        json.dumps(data.get("reminder_times", [])),
        data.get("notes"),
    ))


def get_patient_medications(patient_id: str, active_only: bool = False):
    query = "SELECT * FROM medications WHERE patient_id = %s"
    if active_only:
        query += " AND is_active = TRUE"
    query += " ORDER BY created_at DESC"
    return execute_query(query, (patient_id,))


def get_expiring_medications(patient_id: str, days: int = 7):
    query = """
        SELECT * FROM medications
        WHERE patient_id = %s AND is_active = TRUE
        AND end_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '%s days'
    """
    return execute_query(query, (patient_id, days))


def toggle_medication(med_id: str, is_active: bool):
    return execute_insert(
        "UPDATE medications SET is_active = %s WHERE id = %s RETURNING *",
        (is_active, med_id)
    )


def delete_medication(med_id: str):
    execute_query("DELETE FROM medications WHERE id = %s", (med_id,), fetch=False)


# ── APPOINTMENTS ──────────────────────────────────────────────────────────────

def schedule_appointment(data: dict):
    query = """
        INSERT INTO appointments (patient_id, doctor_name, specialty,
                                  appointment_date, reason, notes)
        VALUES (%(patient_id)s, %(doctor_name)s, %(specialty)s,
                %(appointment_date)s, %(reason)s, %(notes)s)
        RETURNING *
    """
    return execute_insert(query, data)


def get_patient_appointments(patient_id: str):
    return execute_query(
        "SELECT * FROM appointments WHERE patient_id = %s ORDER BY appointment_date ASC",
        (patient_id,)
    )


def get_upcoming_appointments(patient_id: str):
    return execute_query(
        """SELECT * FROM appointments WHERE patient_id = %s
           AND status = 'scheduled' AND appointment_date >= NOW()
           ORDER BY appointment_date ASC LIMIT 5""",
        (patient_id,)
    )


def update_appointment_status(appt_id: str, status: str):
    return execute_insert(
        "UPDATE appointments SET status = %s WHERE id = %s RETURNING *",
        (status, appt_id)
    )


def delete_appointment(appt_id: str):
    execute_query("DELETE FROM appointments WHERE id = %s", (appt_id,), fetch=False)


# ── AI CHAT ───────────────────────────────────────────────────────────────────

def save_chat_message(patient_id: str, role: str, message: str):
    return execute_insert(
        "INSERT INTO ai_chat_history (patient_id, role, message) VALUES (%s, %s, %s) RETURNING *",
        (patient_id, role, message)
    )


def get_chat_history(patient_id: str, limit: int = 50):
    return execute_query(
        "SELECT * FROM ai_chat_history WHERE patient_id = %s ORDER BY created_at ASC LIMIT %s",
        (patient_id, limit)
    )


def clear_chat_history(patient_id: str):
    execute_query("DELETE FROM ai_chat_history WHERE patient_id = %s", (patient_id,), fetch=False)


# ── ALERTS ────────────────────────────────────────────────────────────────────

def create_alert(patient_id: str, alert_type: str, message: str, severity: str = "info"):
    return execute_insert(
        "INSERT INTO health_alerts (patient_id, alert_type, message, severity) VALUES (%s, %s, %s, %s) RETURNING *",
        (patient_id, alert_type, message, severity)
    )


def get_patient_alerts(patient_id: str, unread_only: bool = False):
    query = "SELECT * FROM health_alerts WHERE patient_id = %s"
    if unread_only:
        query += " AND is_read = FALSE"
    query += " ORDER BY created_at DESC LIMIT 20"
    return execute_query(query, (patient_id,))


def mark_alert_read(alert_id: str):
    execute_query("UPDATE health_alerts SET is_read = TRUE WHERE id = %s", (alert_id,), fetch=False)


def mark_all_alerts_read(patient_id: str):
    execute_query(
        "UPDATE health_alerts SET is_read = TRUE WHERE patient_id = %s", (patient_id,), fetch=False
    )


def get_unread_alert_count(patient_id: str) -> int:
    result = execute_one(
        "SELECT COUNT(*) as count FROM health_alerts WHERE patient_id = %s AND is_read = FALSE",
        (patient_id,)
    )
    return result["count"] if result else 0


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

def get_patient_stats(patient_id: str):
    vitals_count = execute_one("SELECT COUNT(*) as count FROM vitals WHERE patient_id = %s", (patient_id,))
    upcoming = execute_one(
        "SELECT COUNT(*) as count FROM appointments WHERE patient_id = %s AND status='scheduled' AND appointment_date >= NOW()",
        (patient_id,)
    )
    unread = execute_one(
        "SELECT COUNT(*) as count FROM health_alerts WHERE patient_id = %s AND is_read = FALSE",
        (patient_id,)
    )
    active_meds = execute_one(
        "SELECT COUNT(*) as count FROM medications WHERE patient_id = %s AND is_active = TRUE",
        (patient_id,)
    )
    return {
        "vitals_recorded": vitals_count["count"] if vitals_count else 0,
        "upcoming_appointments": upcoming["count"] if upcoming else 0,
        "unread_alerts": unread["count"] if unread else 0,
        "active_medications": active_meds["count"] if active_meds else 0,
    }
