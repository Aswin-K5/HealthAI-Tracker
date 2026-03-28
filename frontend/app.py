"""
HealthAI — Patient Health Tracking System
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="HealthAI",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auto-init DB ──────────────────────────────────────────────────────────────
try:
    from backend.database import init_db
    from backend import crud
    from backend import ai_service
    init_db()
    DB_OK = True
except Exception as _e:
    DB_OK = False
    DB_ERR = str(_e)

# ── Start background scheduler (once per session) ─────────────────────────────
if DB_OK and "scheduler_started" not in st.session_state:
    try:
        from backend.scheduler import start_scheduler
        start_scheduler()
        st.session_state.scheduler_started = True
    except Exception as _se:
        print(f"[App] Scheduler failed to start: {_se}")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.main{background:#0f1117;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#141823 0%,#0d1117 100%);border-right:1px solid #1e2330;}
.logo-wrap{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:32px 0 24px 0;}
.logo-icon{font-size:3rem;margin-bottom:6px;}
.logo-text{font-family:'Space Grotesk',sans-serif;font-size:1.8rem;font-weight:700;color:#60a5fa;letter-spacing:-0.5px;}
.logo-sub{font-size:0.72rem;color:#6b7280;letter-spacing:0.12em;text-transform:uppercase;margin-top:2px;}
.metric-card{background:linear-gradient(135deg,#1a1f2e 0%,#141823 100%);border:1px solid #252b3b;border-radius:16px;padding:20px 24px;margin-bottom:12px;}
.metric-value{font-family:'Space Grotesk',sans-serif;font-size:2.2rem;font-weight:700;color:#60a5fa;line-height:1;}
.metric-label{font-size:0.8rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.08em;margin-top:4px;}
.metric-delta{font-size:0.85rem;color:#34d399;margin-top:6px;}
.section-header{font-family:'Space Grotesk',sans-serif;font-size:1.4rem;font-weight:700;color:#e2e8f0;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #252b3b;}
.alert-critical{background:#3b0a0a;border:1px solid #ef4444;border-radius:8px;padding:10px 14px;color:#fca5a5;margin-bottom:8px;}
.alert-high{background:#2d1b09;border:1px solid #f97316;border-radius:8px;padding:10px 14px;color:#fdba74;margin-bottom:8px;}
.alert-warning{background:#1c1a05;border:1px solid #eab308;border-radius:8px;padding:10px 14px;color:#fde047;margin-bottom:8px;}
.alert-info{background:#0a1628;border:1px solid #3b82f6;border-radius:8px;padding:10px 14px;color:#93c5fd;margin-bottom:8px;}
.chat-user{background:#1e3a5f;border-radius:18px 18px 4px 18px;padding:10px 16px;margin:6px 0;color:#e2e8f0;max-width:80%;margin-left:auto;}
.chat-ai{background:#1a1f2e;border:1px solid #252b3b;border-radius:18px 18px 18px 4px;padding:10px 16px;margin:6px 0;color:#cbd5e1;max-width:85%;}
.badge-green{background:#052e16;color:#4ade80;padding:3px 10px;border-radius:20px;font-size:0.75rem;border:1px solid #166534;}
.badge-red{background:#3b0a0a;color:#f87171;padding:3px 10px;border-radius:20px;font-size:0.75rem;border:1px solid #991b1b;}
.badge-yellow{background:#1c1a05;color:#fde047;padding:3px 10px;border-radius:20px;font-size:0.75rem;border:1px solid #854d0e;}
.badge-blue{background:#0a1628;color:#93c5fd;padding:3px 10px;border-radius:20px;font-size:0.75rem;border:1px solid #1e40af;}
.normal-range{font-size:0.72rem;color:#6b7280;margin-top:2px;}
.range-ok{color:#34d399;font-weight:600;}
.range-warn{color:#f87171;font-weight:600;}
.stButton>button{background:linear-gradient(135deg,#2563eb,#1d4ed8);color:white;border:none;border-radius:10px;font-weight:600;transition:all 0.2s;}
.stButton>button:hover{background:linear-gradient(135deg,#3b82f6,#2563eb);transform:translateY(-1px);box-shadow:0 4px 15px rgba(37,99,235,0.4);}
.profile-card{background:linear-gradient(135deg,#1a1f2e,#141823);border:1px solid #252b3b;border-radius:20px;padding:28px;margin-bottom:16px;}
.user-avatar{width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,#2563eb,#7c3aed);display:flex;align-items:center;justify-content:center;font-size:1.6rem;margin-bottom:12px;}
.refill-alert{background:#2d1b09;border:1px solid #f97316;border-radius:10px;padding:12px 16px;color:#fdba74;margin-bottom:8px;}
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

VITALS_RANGES = {
    "heart_rate":               (60, 100,  "bpm"),
    "blood_pressure_systolic":  (90, 120,  "mmHg"),
    "blood_pressure_diastolic": (60, 80,   "mmHg"),
    "temperature":              (36.1, 37.2, "°C"),
    "spo2":                     (95, 100,  "%"),
    "blood_glucose":            (70, 140,  "mg/dL"),
}

def range_badge(key, value):
    if value is None:
        return ""
    lo, hi, unit = VITALS_RANGES.get(key, (0, 9999, ""))
    ok = lo <= float(value) <= hi
    cls = "range-ok" if ok else "range-warn"
    label = "✓ Normal" if ok else "⚠ Abnormal"
    return f'<span class="{cls}">{label}</span> <span style="color:#6b7280;font-size:0.7rem">({lo}–{hi} {unit})</span>'

def bmi_info(weight, height_cm):
    if not weight or not height_cm or height_cm == 0:
        return None, None
    h = height_cm / 100
    bmi = round(weight / (h * h), 1)
    if bmi < 18.5:   cat = ("Underweight", "#60a5fa")
    elif bmi < 25:   cat = ("Normal", "#34d399")
    elif bmi < 30:   cat = ("Overweight", "#fbbf24")
    else:            cat = ("Obese", "#ef4444")
    return bmi, cat

def vitals_gauge(value, label, min_val, max_val, normal_min, normal_max, unit=""):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value or 0,
        title={"text": label, "font": {"size": 12, "color": "#9ca3af"}},
        number={"suffix": f" {unit}", "font": {"size": 16, "color": "#e2e8f0"}},
        gauge={
            "axis": {"range": [min_val, max_val], "tickcolor": "#374151"},
            "bar": {"color": "#3b82f6"},
            "bgcolor": "#1a1f2e",
            "bordercolor": "#252b3b",
            "steps": [
                {"range": [min_val, normal_min], "color": "#3b1818"},
                {"range": [normal_min, normal_max], "color": "#052e16"},
                {"range": [normal_max, max_val], "color": "#3b1818"},
            ],
        },
    ))
    fig.update_layout(
        height=170, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#9ca3af"},
    )
    return fig

# ── Session State ─────────────────────────────────────────────────────────────
for key, val in [("patient", None), ("logged_in", False), ("chat_messages", []), ("auth_page", "login")]:
    if key not in st.session_state:
        st.session_state[key] = val

# ══════════════════════════════════════════════════════════════════════════════
# AUTH PAGES
# ══════════════════════════════════════════════════════════════════════════════

def show_auth():
    with st.sidebar:
        st.markdown("""
        <div class="logo-wrap">
            <div class="logo-icon">🩺</div>
            <div class="logo-text">HealthAI</div>
            <div class="logo-sub">Your Personal Health Monitor</div>
        </div>
        """, unsafe_allow_html=True)

    if not DB_OK:
        st.error(f"Database connection failed: {DB_ERR}")
        st.info("Check your .env file and PostgreSQL connection.")
        st.stop()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_reg = st.tabs(["🔐 Login", "✨ Register"])

        with tab_login:
            st.markdown("#### Welcome back!")
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login →", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error("Please fill in all fields.")
                else:
                    try:
                        patient = crud.login_patient(email, password)
                        if patient:
                            st.session_state.patient = patient
                            st.session_state.logged_in = True
                            st.session_state.chat_messages = []
                            st.toast(f"Welcome back, {patient['name']}! 👋", icon="✅")
                            st.rerun()
                        else:
                            st.error("Invalid email or password.")
                    except Exception as e:
                        st.error(f"Login error: {e}")

        with tab_reg:
            st.markdown("#### Create your account")
            with st.form("register_form"):
                c1, c2 = st.columns(2)
                name     = c1.text_input("Full Name *")
                email    = c2.text_input("Email *")
                password = c1.text_input("Password *", type="password")
                confirm  = c2.text_input("Confirm Password *", type="password")
                age      = c1.number_input("Age *", 1, 120, 25)
                gender   = c2.selectbox("Gender *", ["Male", "Female", "Other"])
                phone    = c1.text_input("Phone")
                blood_group = c2.selectbox("Blood Group", ["A+","A-","B+","B-","AB+","AB-","O+","O-","Unknown"])
                height   = c1.number_input("Height (cm)", 50.0, 250.0, 170.0, 0.5)
                emergency_contact = c2.text_input("Emergency Contact")
                allergies = st.text_area("Known Allergies", height=60, placeholder="e.g. Penicillin, Peanuts")
                chronic   = st.text_area("Chronic Conditions", height=60, placeholder="e.g. Diabetes Type 2, Hypertension")
                submitted = st.form_submit_button("Create Account →", use_container_width=True)

            if submitted:
                if not all([name, email, password, confirm]):
                    st.error("Please fill all required fields.")
                elif password != confirm:
                    st.error("Passwords do not match.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    try:
                        if crud.email_exists(email):
                            st.error("An account with this email already exists.")
                        else:
                            patient = crud.register_patient({
                                "name": name, "email": email, "password": password,
                                "age": age, "gender": gender, "phone": phone,
                                "blood_group": blood_group, "height": height,
                                "allergies": allergies, "chronic_conditions": chronic,
                                "emergency_contact": emergency_contact
                            })
                            st.session_state.patient = patient
                            st.session_state.logged_in = True
                            st.toast(f"Account created! Welcome, {name}! 🎉", icon="✅")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Registration error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

def show_app():
    patient = st.session_state.patient
    pid = str(patient["id"])

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:16px 0 8px 0;">
            <div style="font-size:0.72rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.1em;">Logged in as</div>
            <div style="font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:600;color:#e2e8f0;margin-top:2px;">
                {patient['name']}
            </div>
            <div style="font-size:0.78rem;color:#6b7280;">{patient['email']}</div>
        </div>
        """, unsafe_allow_html=True)

        try:
            unread = crud.get_unread_alert_count(pid)
            alert_label = f"🔔 Alerts ({unread})" if unread > 0 else "🔔 Alerts"
        except:
            alert_label = "🔔 Alerts"

        st.markdown("---")
        page = st.radio("Navigation", [
            "📊 Dashboard", "💓 Vitals", "🤒 Symptoms", "💊 Medications",
            "📅 Appointments", "🤖 AI Assistant", alert_label, "👤 My Profile"
        ], label_visibility="collapsed")

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            for k in ["patient", "logged_in", "chat_messages"]:
                st.session_state[k] = None if k == "patient" else (False if k == "logged_in" else [])
            st.rerun()

        st.markdown('<div style="color:#374151;font-size:0.68rem;margin-top:12px;">HealthAI v2.0 • Powered by Groq</div>', unsafe_allow_html=True)

    # ── Check expiring meds & auto alerts ─────────────────────────────────────
    try:
        expiring = crud.get_expiring_medications(pid, days=7)
        for med in expiring:
            msg = f"💊 {med['medication_name']} refill needed by {med['end_date']}"
            crud.create_alert(pid, "refill_reminder", msg, severity="warning")
    except:
        pass

    # ══════════════════════════════════════════════════════════════════════════
    # DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════
    if page == "📊 Dashboard":
        st.markdown('<div class="section-header">📊 Your Health Dashboard</div>', unsafe_allow_html=True)

        try:
            stats  = crud.get_patient_stats(pid)
            latest = crud.get_latest_vitals(pid)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="metric-card"><div class="metric-value">{stats["vitals_recorded"]}</div><div class="metric-label">Vitals Recorded</div><div class="metric-delta">💓 Total logs</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="metric-card"><div class="metric-value">{stats["active_medications"]}</div><div class="metric-label">Active Medications</div><div class="metric-delta">💊 Currently taking</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="metric-card"><div class="metric-value">{stats["upcoming_appointments"]}</div><div class="metric-label">Upcoming Appts</div><div class="metric-delta">📅 Scheduled</div></div>', unsafe_allow_html=True)
            with c4:
                color = "#ef4444" if stats["unread_alerts"] > 0 else "#60a5fa"
                st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:{color}">{stats["unread_alerts"]}</div><div class="metric-label">Unread Alerts</div><div class="metric-delta">🔔 Pending</div></div>', unsafe_allow_html=True)

            if latest and patient.get("height"):
                bmi, cat = bmi_info(latest.get("weight"), patient.get("height"))
                if bmi:
                    st.markdown(f"""
                    <div class="metric-card" style="display:flex;align-items:center;gap:20px;">
                        <div>
                            <div class="metric-value" style="color:{cat[1]}">{bmi}</div>
                            <div class="metric-label">BMI</div>
                        </div>
                        <div style="color:{cat[1]};font-size:1.1rem;font-weight:600;">{cat[0]}</div>
                        <div style="color:#6b7280;font-size:0.8rem;">Based on latest weight & your height ({patient['height']} cm)</div>
                    </div>""", unsafe_allow_html=True)

            vitals_history = crud.get_patient_vitals(pid, limit=10)
            col_a, col_b = st.columns([2, 1])

            with col_a:
                if vitals_history:
                    df = pd.DataFrame(vitals_history)
                    df["recorded_at"] = pd.to_datetime(df["recorded_at"])
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df["recorded_at"], y=df["heart_rate"],
                                             name="Heart Rate", line=dict(color="#f87171", width=2)))
                    fig.add_trace(go.Scatter(x=df["recorded_at"], y=df["spo2"],
                                             name="SpO2", line=dict(color="#60a5fa", width=2), yaxis="y2"))
                    fig.update_layout(
                        title="Recent Vitals Trend",
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#9ca3af"),
                        xaxis=dict(gridcolor="#1e2330"),
                        yaxis=dict(gridcolor="#1e2330", title="Heart Rate (bpm)"),
                        yaxis2=dict(overlaying="y", side="right", title="SpO2 (%)"),
                        legend=dict(bgcolor="rgba(0,0,0,0)"),
                        height=260, margin=dict(l=0, r=0, t=40, b=0)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No vitals recorded yet. Go to Vitals tab to add your first reading.")

            with col_b:
                st.markdown("#### 📅 Upcoming Appointments")
                try:
                    upcoming = crud.get_upcoming_appointments(pid)
                    if upcoming:
                        for a in upcoming:
                            dt = a["appointment_date"].strftime("%b %d, %H:%M") if a.get("appointment_date") else "N/A"
                            st.markdown(f'<div class="alert-info">📅 <strong>{dt}</strong><br>Dr. {a["doctor_name"]}<br><small>{a["specialty"]}</small></div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="alert-info">No upcoming appointments</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.warning(str(e))

        except Exception as e:
            st.error(f"Dashboard error: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # VITALS
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "💓 Vitals":
        st.markdown('<div class="section-header">💓 Vitals Monitor</div>', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["📊 Record & View", "📈 History & Trends"])

        with tab1:
            latest = crud.get_latest_vitals(pid)

            with st.form("record_vitals"):
                st.markdown("#### Record New Vitals")
                c1, c2, c3, c4 = st.columns(4)
                hr      = c1.number_input("Heart Rate (bpm)", 30, 250, int(latest["heart_rate"]) if latest and latest.get("heart_rate") else 72)
                bp_sys  = c2.number_input("BP Systolic", 60, 250, int(latest["blood_pressure_systolic"]) if latest and latest.get("blood_pressure_systolic") else 120)
                bp_dia  = c3.number_input("BP Diastolic", 30, 150, int(latest["blood_pressure_diastolic"]) if latest and latest.get("blood_pressure_diastolic") else 80)
                temp    = c4.number_input("Temperature (°C)", 34.0, 42.0, float(latest["temperature"]) if latest and latest.get("temperature") else 37.0, 0.1)
                spo2    = c1.number_input("SpO2 (%)", 70, 100, int(latest["spo2"]) if latest and latest.get("spo2") else 98)
                weight  = c2.number_input("Weight (kg)", 1.0, 300.0, float(latest["weight"]) if latest and latest.get("weight") else 70.0, 0.1)
                glucose = c3.number_input("Blood Glucose (mg/dL)", 40, 600, int(latest["blood_glucose"]) if latest and latest.get("blood_glucose") else 100)
                submitted = st.form_submit_button("💾 Save & Analyze", use_container_width=True)

            if submitted:
                vitals_data = {
                    "patient_id": pid, "heart_rate": hr,
                    "blood_pressure_systolic": bp_sys, "blood_pressure_diastolic": bp_dia,
                    "temperature": temp, "spo2": spo2, "weight": weight, "blood_glucose": glucose
                }
                try:
                    crud.record_vitals(vitals_data)
                    with st.spinner("🤖 AI analyzing your vitals..."):
                        analysis = ai_service.analyze_vitals(pid, vitals_data)
                    sev_color = {"normal": "#34d399", "warning": "#fbbf24", "critical": "#ef4444"}
                    color = sev_color.get(analysis["status"], "#60a5fa")
                    st.toast("✅ Vitals saved successfully!", icon="💓")
                    st.markdown(f"""
                    <div class="metric-card">
                        <div style="font-size:1.1rem;font-weight:600;color:{color}">🤖 AI Analysis — {analysis['status'].upper()}</div>
                        <div style="color:#cbd5e1;margin-top:8px">{analysis['insights']}</div>
                        <div style="color:#f87171;margin-top:6px"><strong>Anomalies:</strong> {analysis['anomalies']}</div>
                        <div style="color:#93c5fd;margin-top:6px"><strong>Advice:</strong> {analysis['advice']}</div>
                    </div>""", unsafe_allow_html=True)

                    st.markdown("#### Range Check")
                    r1, r2, r3, r4 = st.columns(4)
                    r1.markdown(f"**Heart Rate:** {hr} bpm<br>{range_badge('heart_rate', hr)}", unsafe_allow_html=True)
                    r2.markdown(f"**BP Systolic:** {bp_sys}<br>{range_badge('blood_pressure_systolic', bp_sys)}", unsafe_allow_html=True)
                    r3.markdown(f"**SpO2:** {spo2}%<br>{range_badge('spo2', spo2)}", unsafe_allow_html=True)
                    r4.markdown(f"**Glucose:** {glucose}<br>{range_badge('blood_glucose', glucose)}", unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")

            latest = crud.get_latest_vitals(pid)
            if latest:
                st.markdown("#### Current Readings")
                g1, g2, g3, g4 = st.columns(4)
                with g1: st.plotly_chart(vitals_gauge(latest.get("heart_rate"), "Heart Rate", 30, 200, 60, 100, "bpm"), use_container_width=True)
                with g2: st.plotly_chart(vitals_gauge(latest.get("spo2"), "SpO₂", 70, 100, 95, 100, "%"), use_container_width=True)
                with g3: st.plotly_chart(vitals_gauge(latest.get("temperature"), "Temperature", 34, 42, 36.1, 37.2, "°C"), use_container_width=True)
                with g4: st.plotly_chart(vitals_gauge(latest.get("blood_glucose"), "Blood Glucose", 40, 400, 70, 140, "mg/dL"), use_container_width=True)

        with tab2:
            history = crud.get_patient_vitals(pid, limit=30)
            if history:
                df = pd.DataFrame(history)
                df["recorded_at"] = pd.to_datetime(df["recorded_at"])
                metric = st.selectbox("Select Metric", ["heart_rate","spo2","temperature","blood_glucose","weight"])
                colors = {"heart_rate":"#f87171","spo2":"#60a5fa","temperature":"#fb923c","blood_glucose":"#a78bfa","weight":"#34d399"}
                fig = px.line(df, x="recorded_at", y=metric,
                              title=f"{metric.replace('_',' ').title()} Trend",
                              color_discrete_sequence=[colors.get(metric,"#60a5fa")])
                fig.add_scatter(x=df["recorded_at"], y=df[metric], mode="markers",
                                marker=dict(size=6, color="white"), showlegend=False)
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  font=dict(color="#9ca3af"), xaxis=dict(gridcolor="#1e2330"),
                                  yaxis=dict(gridcolor="#1e2330"), height=320, margin=dict(l=0,r=0,t=40,b=0))
                st.plotly_chart(fig, use_container_width=True)

                csv = df[["recorded_at","heart_rate","blood_pressure_systolic","blood_pressure_diastolic",
                           "temperature","spo2","weight","blood_glucose"]].to_csv(index=False)
                st.download_button("📥 Export as CSV", csv, "my_vitals.csv", "text/csv")

                display_df = df[["recorded_at","heart_rate","blood_pressure_systolic","blood_pressure_diastolic",
                                  "temperature","spo2","weight","blood_glucose"]].copy()
                display_df.columns = ["Time","HR","BP Sys","BP Dia","Temp","SpO2","Weight","Glucose"]
                st.dataframe(display_df.head(15), use_container_width=True)
            else:
                st.info("No vitals history yet.")

    # ══════════════════════════════════════════════════════════════════════════
    # SYMPTOMS
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "🤒 Symptoms":
        st.markdown('<div class="section-header">🤒 Symptom Checker</div>', unsafe_allow_html=True)

        with st.form("symptom_form"):
            symptoms = st.text_area("Describe your symptoms in detail", height=120,
                                    placeholder="e.g. Persistent headache for 3 days, mild fever, fatigue...")
            severity = st.select_slider("Severity", ["mild","moderate","severe","critical"])
            submitted = st.form_submit_button("🔬 Analyze with AI", use_container_width=True)

        if submitted and symptoms:
            with st.spinner("🤖 Analyzing your symptoms..."):
                try:
                    result = ai_service.analyze_symptoms(pid, symptoms)
                    crud.record_symptom({
                        "patient_id": pid, "symptoms_text": symptoms, "severity": severity,
                        "ai_analysis": result["ai_analysis"],
                        "ai_recommendation": result["ai_recommendation"],
                        "risk_level": result["risk_level"]
                    })
                    risk_colors = {"low":"#34d399","moderate":"#fbbf24","high":"#f97316","critical":"#ef4444"}
                    color = risk_colors.get(result["risk_level"], "#60a5fa")
                    st.toast("✅ Symptoms analyzed and saved!", icon="🔬")
                    st.markdown(f"""
                    <div class="metric-card">
                        <div style="font-size:1.2rem;font-weight:700;color:{color}">⚕️ Risk Level: {result['risk_level'].upper()}</div>
                        <div style="color:#cbd5e1;margin-top:10px;line-height:1.6"><strong>Analysis:</strong><br>{result['ai_analysis']}</div>
                        <div style="color:#93c5fd;margin-top:10px;line-height:1.6"><strong>Recommendations:</strong><br>{result['ai_recommendation']}</div>
                        <div style="color:#a78bfa;margin-top:8px"><strong>⏰ Urgency:</strong> {result.get('urgency','Consult a doctor')}</div>
                    </div>""", unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"AI Error: {e}")
        elif submitted:
            st.warning("Please describe your symptoms first.")

        st.markdown("---")
        st.markdown("#### 📋 Symptom History")
        try:
            history = crud.get_patient_symptoms(pid)
            if history:
                for s in history:
                    dt = s["recorded_at"].strftime("%b %d, %Y %H:%M") if s.get("recorded_at") else "N/A"
                    with st.expander(f"📅 {dt} — {s['symptoms_text'][:60]}..."):
                        c1, c2 = st.columns(2)
                        c1.markdown(f"**Severity:** {s['severity']}")
                        c1.markdown(f"**Risk Level:** {s['risk_level']}")
                        c2.markdown(f"**Analysis:** {s.get('ai_analysis','N/A')}")
                        st.markdown(f"**Recommendation:** {s.get('ai_recommendation','N/A')}")
            else:
                st.info("No symptom history yet.")
        except Exception as e:
            st.error(str(e))

    # ══════════════════════════════════════════════════════════════════════════
    # MEDICATIONS
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "💊 Medications":
        st.markdown('<div class="section-header">💊 My Medications</div>', unsafe_allow_html=True)

        try:
            expiring = crud.get_expiring_medications(pid, days=7)
            for med in expiring:
                st.markdown(f'<div class="refill-alert">⚠️ <strong>Refill Needed:</strong> {med["medication_name"]} ends on {med["end_date"]}</div>', unsafe_allow_html=True)
        except:
            pass

        tab1, tab2 = st.tabs(["📋 My Medications", "➕ Add Medication"])

        with tab1:
            show_all = st.checkbox("Show inactive medications too")
            try:
                meds = crud.get_patient_medications(pid, active_only=not show_all)
                if meds:
                    for m in meds:
                        icon = "🟢" if m["is_active"] else "🔴"
                        reminder_display = f" | ⏰ Reminder: {m['reminder_time']}" if m.get("reminder_time") else ""
                        with st.expander(f"{icon} {m['medication_name']} — {m['dosage']} | {m['frequency']}{reminder_display}"):
                            c1, c2 = st.columns(2)
                            c1.markdown(f"**Prescribed by:** {m.get('prescribed_by','N/A')}")
                            c1.markdown(f"**Start:** {m.get('start_date','N/A')}")
                            c2.markdown(f"**End:** {m.get('end_date','N/A')}")
                            c2.markdown(f"**Notes:** {m.get('notes','None')}")
                            if m.get("reminder_time"):
                                st.markdown(f'<div class="alert-info">⏰ Email reminder set for <strong>{m["reminder_time"]}</strong> daily (5 min before)</div>', unsafe_allow_html=True)
                            b1, b2 = st.columns(2)
                            toggle = "⏸ Deactivate" if m["is_active"] else "▶ Activate"
                            if b1.button(toggle, key=f"tog_{m['id']}"):
                                crud.toggle_medication(m["id"], not m["is_active"])
                                st.toast(f"{'Deactivated' if m['is_active'] else 'Activated'} {m['medication_name']}", icon="💊")
                                st.rerun()
                            if b2.button("🗑 Delete", key=f"del_{m['id']}"):
                                crud.delete_medication(m["id"])
                                st.toast(f"Deleted {m['medication_name']}", icon="🗑")
                                st.rerun()

                    if st.button("🤖 Get AI Medication Insights"):
                        with st.spinner("Analyzing your medications..."):
                            insights = ai_service.get_medication_insights(pid)
                        st.markdown(f'<div class="metric-card"><div style="font-weight:700;color:#60a5fa;margin-bottom:8px">💊 AI Medication Analysis</div><div style="color:#cbd5e1;line-height:1.7">{insights}</div></div>', unsafe_allow_html=True)
                else:
                    st.info("No medications found. Add one below.")
            except Exception as e:
                st.error(str(e))

        with tab2:
            st.markdown("#### ➕ Add New Medication")

            # Frequency → how many time slots to show
            FREQ_COUNT = {
                "Once daily": 1, "Twice daily": 2, "Three times daily": 3,
                "Every 8 hours": 3, "Every 12 hours": 2, "As needed": 1, "Weekly": 1,
            }
            DEFAULT_TIMES = {
                1: ["08:00"],
                2: ["08:00", "20:00"],
                3: ["08:00", "14:00", "19:00"],
            }

            # Frequency picker OUTSIDE form so time inputs update dynamically
            freq_col, _ = st.columns([1, 1])
            frequency = freq_col.selectbox(
                "Frequency *",
                list(FREQ_COUNT.keys()),
                key="add_med_freq"
            )
            n_times = FREQ_COUNT[frequency]
            defaults = DEFAULT_TIMES.get(n_times, ["08:00"])

            st.markdown(
                f'<div class="alert-info">📧 {n_times} email reminder(s) will be sent daily, '
                f'5 minutes before each scheduled time.</div>',
                unsafe_allow_html=True
            )

            # Time inputs dynamically based on frequency
            st.markdown(f"**⏰ Set {n_times} reminder time(s):**")
            time_cols = st.columns(n_times)
            reminder_times = []
            labels = ["Morning", "Afternoon", "Evening"] if n_times == 3 else \
                    ["Morning", "Evening"] if n_times == 2 else ["Daily"]

            for i in range(n_times):
                default_h, default_m = map(int, defaults[i].split(":"))
                t = time_cols[i].time_input(
                    f"⏰ {labels[i]}",
                    value=datetime.now().replace(hour=default_h, minute=default_m, second=0).time(),
                    key=f"reminder_t_{i}"
                )
                reminder_times.append(t.strftime("%H:%M"))

            # Rest of the form
            with st.form("add_med"):
                c1, c2 = st.columns(2)
                med_name      = c1.text_input("Medication Name *")
                dosage        = c2.text_input("Dosage (e.g. 500mg)")
                prescribed_by = c1.text_input("Prescribed By")
                start_date    = c2.date_input("Start Date", date.today())
                end_date      = c1.date_input("End Date", date.today() + timedelta(days=30))
                notes         = st.text_area("Notes", height=70)

                if st.form_submit_button("💾 Add Medication", use_container_width=True):
                    if not med_name:
                        st.error("Medication name is required.")
                    else:
                        try:
                            crud.add_medication({
                                "patient_id":      pid,
                                "medication_name": med_name,
                                "dosage":          dosage,
                                "frequency":       frequency,
                                "start_date":      start_date,
                                "end_date":        end_date,
                                "prescribed_by":   prescribed_by,
                                "reminder_times":  reminder_times,
                                "notes":           notes,
                            })
                            times_str = " | ".join(reminder_times)
                            st.toast(
                                f"✅ {med_name} added! Reminders set for {times_str}",
                                icon="💊"
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

    # ══════════════════════════════════════════════════════════════════════════
    # APPOINTMENTS
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "📅 Appointments":
        st.markdown('<div class="section-header">📅 My Appointments</div>', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["📋 My Appointments", "➕ Schedule New"])

        with tab1:
            try:
                appts = crud.get_patient_appointments(pid)
                if appts:
                    upcoming = [a for a in appts if a.get("appointment_date") and a["appointment_date"] >= datetime.now() and a["status"] == "scheduled"]
                    past     = [a for a in appts if a not in upcoming]

                    if upcoming:
                        st.markdown("#### 📅 Upcoming")
                        for a in upcoming:
                            dt = a["appointment_date"].strftime("%B %d, %Y at %H:%M") if a.get("appointment_date") else "N/A"
                            with st.expander(f"📅 {dt} — Dr. {a.get('doctor_name','N/A')} ({a.get('specialty','')})"):
                                c1, c2 = st.columns(2)
                                c1.markdown(f"**Reason:** {a.get('reason','N/A')}")
                                c2.markdown(f"**Notes:** {a.get('notes','None')}")
                                st.markdown('<div class="alert-info">📧 Email reminders will be sent 1 day before and 1 hour before this appointment.</div>', unsafe_allow_html=True)
                                b1, b2 = st.columns(2)
                                if b1.button("✅ Mark Completed", key=f"done_{a['id']}"):
                                    crud.update_appointment_status(a["id"], "completed")
                                    st.toast("Appointment marked as completed!", icon="✅")
                                    st.rerun()
                                if b2.button("❌ Cancel", key=f"cancel_{a['id']}"):
                                    crud.update_appointment_status(a["id"], "cancelled")
                                    st.toast("Appointment cancelled.", icon="❌")
                                    st.rerun()

                    if past:
                        st.markdown("#### 🕐 Past")
                        for a in past[:5]:
                            dt = a["appointment_date"].strftime("%B %d, %Y") if a.get("appointment_date") else "N/A"
                            status_color = {"completed":"#34d399","cancelled":"#f87171","no-show":"#fbbf24"}.get(a["status"],"#6b7280")
                            st.markdown(f'<div class="alert-info">📅 {dt} — Dr. {a.get("doctor_name","N/A")} &nbsp; <span style="color:{status_color}">({a["status"]})</span></div>', unsafe_allow_html=True)
                else:
                    st.info("No appointments yet. Schedule your first one!")
            except Exception as e:
                st.error(str(e))

        with tab2:
            st.markdown('<div class="alert-info">📧 You will automatically receive email reminders <strong>1 day before</strong> and <strong>1 hour before</strong> your appointment.</div>', unsafe_allow_html=True)
            with st.form("schedule_appt"):
                c1, c2 = st.columns(2)
                doctor    = c1.text_input("Doctor Name *")
                specialty = c2.selectbox("Specialty", ["General Medicine","Cardiology","Endocrinology","Neurology","Orthopedics","Pulmonology","Gastroenterology","Psychiatry","Dermatology","Other"])
                appt_date = c1.date_input("Date", date.today() + timedelta(days=1))
                appt_time = c2.time_input("Time", datetime.now().replace(hour=10, minute=0).time())
                reason    = st.text_area("Reason for Visit", height=80)
                notes     = st.text_area("Additional Notes", height=60)
                if st.form_submit_button("📅 Schedule Appointment", use_container_width=True):
                    if not doctor:
                        st.error("Doctor name is required.")
                    else:
                        try:
                            crud.schedule_appointment({
                                "patient_id": pid, "doctor_name": doctor, "specialty": specialty,
                                "appointment_date": datetime.combine(appt_date, appt_time),
                                "reason": reason, "notes": notes
                            })
                            st.toast(f"✅ Appointment with Dr. {doctor} scheduled! Email reminders set.", icon="📅")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

    # ══════════════════════════════════════════════════════════════════════════
    # AI ASSISTANT
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "🤖 AI Assistant":
        st.markdown('<div class="section-header">🤖 Your AI Health Assistant</div>', unsafe_allow_html=True)

        col1, col2 = st.columns([4, 1])
        col1.markdown("Ask me anything about your health, medications, or symptoms.")
        if col2.button("🗑 Clear Chat"):
            crud.clear_chat_history(pid)
            st.session_state.chat_messages = []
            st.rerun()

        try:
            if not st.session_state.chat_messages:
                st.session_state.chat_messages = crud.get_chat_history(pid, limit=40)
        except:
            pass

        st.markdown("**Suggested Questions:**")
        sq = st.columns(4)
        suggestions = ["Summarize my health", "Review my medications", "What do my vitals mean?", "Any health risks?"]
        for i, (col, q) in enumerate(zip(sq, suggestions)):
            if col.button(q, key=f"sq_{i}"):
                st.session_state._quick = q

        st.markdown("---")
        for msg in st.session_state.chat_messages[-20:]:
            role    = msg.get("role", "user")
            content = msg.get("message", "")
            if role == "user":
                st.markdown(f'<div class="chat-user">👤 {content}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-ai">🤖 {content}</div>', unsafe_allow_html=True)

        user_input = st.chat_input("Ask your health assistant...")
        if hasattr(st.session_state, "_quick") and st.session_state._quick:
            user_input = st.session_state._quick
            del st.session_state._quick

        if user_input:
            try:
                crud.save_chat_message(pid, "user", user_input)
                st.session_state.chat_messages.append({"role": "user", "message": user_input})
                with st.spinner("🤖 Thinking..."):
                    history  = crud.get_chat_history(pid, limit=20)
                    response = ai_service.chat_with_ai(pid, user_input, history)
                crud.save_chat_message(pid, "assistant", response)
                st.session_state.chat_messages.append({"role": "assistant", "message": response})
                st.rerun()
            except Exception as e:
                st.error(f"AI Error: {e}")

        st.markdown("---")
        if st.button("📋 Generate My Health Summary"):
            with st.spinner("Generating your health report..."):
                try:
                    summary = ai_service.generate_health_summary(pid)
                    st.markdown(f'<div class="metric-card"><div style="font-weight:700;color:#60a5fa;font-size:1.1rem;margin-bottom:10px">📋 Your Health Summary</div><div style="color:#cbd5e1;line-height:1.8;white-space:pre-wrap">{summary}</div></div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(str(e))

    # ══════════════════════════════════════════════════════════════════════════
    # ALERTS
    # ══════════════════════════════════════════════════════════════════════════
    elif "Alerts" in page:
        st.markdown('<div class="section-header">🔔 Health Alerts</div>', unsafe_allow_html=True)

        col1, col2 = st.columns([4, 1])
        show_unread = col1.checkbox("Show unread only", value=True)
        if col2.button("✅ Mark All Read"):
            crud.mark_all_alerts_read(pid)
            st.toast("All alerts marked as read!", icon="✅")
            st.rerun()

        try:
            alerts = crud.get_patient_alerts(pid, unread_only=show_unread)
            if alerts:
                for alert in alerts:
                    sev      = alert.get("severity", "info")
                    is_read  = alert.get("is_read", False)
                    dt       = alert["created_at"].strftime("%b %d, %H:%M") if alert.get("created_at") else ""
                    c1, c2   = st.columns([5, 1])
                    with c1:
                        read_dot = "" if is_read else "🔴 "
                        st.markdown(f'<div class="alert-{sev}">{read_dot}<strong>{alert.get("alert_type","Alert").replace("_"," ").title()}</strong><br>{alert["message"]}<br><small style="color:#6b7280">{dt}</small></div>', unsafe_allow_html=True)
                    with c2:
                        if not is_read:
                            if st.button("Read", key=f"r_{alert['id']}"):
                                crud.mark_alert_read(alert["id"])
                                st.rerun()
            else:
                st.markdown('<div class="alert-info">✅ You have no alerts!</div>', unsafe_allow_html=True)
        except Exception as e:
            st.error(str(e))

    # ══════════════════════════════════════════════════════════════════════════
    # MY PROFILE
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "👤 My Profile":
        st.markdown('<div class="section-header">👤 My Profile</div>', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["✏️ Edit Profile", "🔒 Change Password"])

        with tab1:
            with st.form("edit_profile"):
                c1, c2 = st.columns(2)
                name      = c1.text_input("Full Name", value=patient.get("name",""))
                email     = c2.text_input("Email", value=patient.get("email",""), disabled=True)
                age       = c1.number_input("Age", 1, 120, int(patient.get("age", 25)))
                gender    = c2.selectbox("Gender", ["Male","Female","Other"],
                                         index=["Male","Female","Other"].index(patient.get("gender","Male")))
                phone     = c1.text_input("Phone", value=patient.get("phone","") or "")
                blood_group = c2.selectbox("Blood Group", ["A+","A-","B+","B-","AB+","AB-","O+","O-","Unknown"],
                                            index=["A+","A-","B+","B-","AB+","AB-","O+","O-","Unknown"].index(patient.get("blood_group","Unknown")))
                height    = c1.number_input("Height (cm)", 50.0, 250.0, float(patient.get("height") or 170.0), 0.5)
                emergency = c2.text_input("Emergency Contact", value=patient.get("emergency_contact","") or "")
                allergies = st.text_area("Known Allergies", value=patient.get("allergies","") or "", height=70)
                chronic   = st.text_area("Chronic Conditions", value=patient.get("chronic_conditions","") or "", height=70)
                if st.form_submit_button("💾 Save Changes", use_container_width=True):
                    try:
                        updated = crud.update_patient(pid, {
                            "name": name, "age": age, "gender": gender, "phone": phone,
                            "blood_group": blood_group, "height": height,
                            "allergies": allergies, "chronic_conditions": chronic,
                            "emergency_contact": emergency
                        })
                        st.session_state.patient = updated
                        st.toast("✅ Profile updated successfully!", icon="👤")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        with tab2:
            with st.form("change_password"):
                current  = st.text_input("Current Password", type="password")
                new_pass = st.text_input("New Password", type="password")
                confirm  = st.text_input("Confirm New Password", type="password")
                if st.form_submit_button("🔒 Update Password", use_container_width=True):
                    if not all([current, new_pass, confirm]):
                        st.error("Please fill all fields.")
                    elif new_pass != confirm:
                        st.error("New passwords do not match.")
                    elif len(new_pass) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        try:
                            check = crud.login_patient(patient["email"], current)
                            if check:
                                crud.update_password(pid, new_pass)
                                st.toast("✅ Password updated successfully!", icon="🔒")
                            else:
                                st.error("Current password is incorrect.")
                        except Exception as e:
                            st.error(str(e))

# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.logged_in and st.session_state.patient:
    show_app()
else:
    show_auth()