"""
Standalone reminder script — runs via GitHub Actions every 5 minutes.
Works completely independent of Streamlit app being active or not.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime

print(f"[Reminders] ⏰ Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

try:
    from backend.scheduler import check_medication_reminders, check_appointment_reminders
    check_medication_reminders()
    check_appointment_reminders()
    print("[Reminders] ✅ Done.")
except Exception as e:
    print(f"[Reminders] ❌ Error: {e}")
    sys.exit(1)