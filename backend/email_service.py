import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")


def send_email(to_email: str, subject: str, body: str):
    if not SMTP_USER or not SMTP_PASS:
        print(f"[EmailService] SMTP not configured. Skipping email to {to_email}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"HealthAI <{SMTP_USER}>"
        msg["To"]      = to_email

        html = f"""
        <html>
        <body style="font-family:Arial,sans-serif;background:#0f1117;color:#e2e8f0;padding:24px;">
          <div style="max-width:520px;margin:auto;background:#1a1f2e;border-radius:16px;
                      padding:28px;border:1px solid #252b3b;">
            <div style="text-align:center;margin-bottom:20px;">
              <span style="font-size:2.5rem;">🩺</span>
              <h1 style="color:#60a5fa;margin:8px 0 0 0;font-size:1.5rem;">HealthAI</h1>
            </div>
            <p style="line-height:1.7;color:#cbd5e1;font-size:1rem;">{body}</p>
            <hr style="border:none;border-top:1px solid #252b3b;margin:20px 0;">
            <p style="font-size:0.75rem;color:#6b7280;text-align:center;">
              This is an automated reminder from HealthAI. Do not reply to this email.
            </p>
          </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        print(f"[EmailService] ✅ Sent '{subject}' → {to_email}")
        return True

    except Exception as e:
        print(f"[EmailService] ❌ Failed: {e}")
        return False


def send_medication_reminder(to_email: str, patient_name: str,
                              med_name: str, dosage: str, frequency: str,
                              reminder_times: list = None):
    subject = f"💊 Time to take {med_name}!"
    times_html = ""
    if reminder_times:
        times_list = "".join([f"<li style='color:#93c5fd;'>{t}</li>" for t in reminder_times])
        times_html = f"<p style='color:#9ca3af;margin-top:8px;'>Your scheduled times today:<ul>{times_list}</ul></p>"

    body = (
        f"Hi <strong>{patient_name}</strong>,<br><br>"
        f"This is your <strong>5-minute reminder</strong> to take your medication:<br><br>"
        f"<div style='background:#0a1628;border:1px solid #3b82f6;border-radius:10px;"
        f"padding:16px;margin:12px 0;'>"
        f"<span style='font-size:1.4rem;'>💊</span><br>"
        f"<strong style='color:#60a5fa;font-size:1.2rem;'>{med_name}</strong><br>"
        f"<span style='color:#9ca3af;'>Dosage: {dosage or 'As prescribed'}</span><br>"
        f"<span style='color:#9ca3af;'>Frequency: {frequency or ''}</span>"
        f"{times_html}"
        f"</div>"
        f"Please take it now and stay on track with your health routine! 💪<br><br>"
        f"<em style='color:#6b7280;font-size:0.9rem;'>Never skip a dose without consulting your doctor.</em>"
    )
    return send_email(to_email, subject, body)


def send_appointment_reminder(to_email: str, patient_name: str, doctor: str,
                               specialty: str, appt_dt: str, timeframe: str):
    subject = f"📅 Appointment Reminder — Dr. {doctor} ({timeframe})"
    body = (
        f"Hi <strong>{patient_name}</strong>,<br><br>"
        f"You have an upcoming appointment <strong>{timeframe}</strong>:<br><br>"
        f"<div style='background:#0a1628;border:1px solid #3b82f6;border-radius:10px;"
        f"padding:16px;margin:12px 0;'>"
        f"<span style='font-size:1.4rem;'>👨‍⚕️</span><br>"
        f"<strong style='color:#60a5fa;font-size:1.15rem;'>Dr. {doctor}</strong><br>"
        f"<span style='color:#9ca3af;'>{specialty}</span><br><br>"
        f"<span style='font-size:1.3rem;'>📅</span> "
        f"<strong style='color:#e2e8f0;'>{appt_dt}</strong>"
        f"</div>"
        f"<strong>Please remember to:</strong><br>"
        f"<ul style='color:#cbd5e1;line-height:1.9;'>"
        f"<li>Carry your medical records and reports</li>"
        f"<li>List any new symptoms or concerns</li>"
        f"<li>Bring your current medication list</li>"
        f"<li>Arrive 10 minutes early</li>"
        f"</ul>"
    )
    return send_email(to_email, subject, body)