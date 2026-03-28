"""
AI Service - Uses Groq API for health intelligence (fast & free)
"""
import os
from groq import Groq
from backend.crud import (
    get_patient, get_latest_vitals, get_patient_medications,
    get_patient_symptoms, create_alert
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"


def _build_patient_context(patient_id: str) -> str:
    patient = get_patient(patient_id)
    if not patient:
        return "No patient information available."
    vitals = get_latest_vitals(patient_id)
    meds = get_patient_medications(patient_id, active_only=True)
    recent_symptoms = get_patient_symptoms(patient_id, limit=5)
    context = f"""
PATIENT PROFILE:
- Name: {patient['name']}, Age: {patient['age']}, Gender: {patient['gender']}
- Blood Group: {patient.get('blood_group', 'Unknown')}
- Allergies: {patient.get('allergies', 'None known')}
- Chronic Conditions: {patient.get('chronic_conditions', 'None')}
"""
    if vitals:
        context += f"""
LATEST VITALS (recorded {vitals['recorded_at']}):
- Heart Rate: {vitals.get('heart_rate')} bpm
- Blood Pressure: {vitals.get('blood_pressure_systolic')}/{vitals.get('blood_pressure_diastolic')} mmHg
- Temperature: {vitals.get('temperature')} C
- SpO2: {vitals.get('spo2')}%
- Weight: {vitals.get('weight')} kg
- Blood Glucose: {vitals.get('blood_glucose')} mg/dL
"""
    if meds:
        med_list = ", ".join([f"{m['medication_name']} ({m['dosage']})" for m in meds])
        context += f"\nACTIVE MEDICATIONS: {med_list}"
    if recent_symptoms:
        sym_list = "; ".join([s['symptoms_text'] for s in recent_symptoms[:3]])
        context += f"\nRECENT SYMPTOMS: {sym_list}"
    return context


def _chat(system: str, user: str, max_tokens: int = 600) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    )
    return response.choices[0].message.content


def analyze_symptoms(patient_id: str, symptoms_text: str) -> dict:
    patient_context = _build_patient_context(patient_id)
    system = "You are an expert AI medical assistant. Analyze patient symptoms and respond in the exact format requested."
    user = f"""Analyze the following symptoms for a patient.

{patient_context}

REPORTED SYMPTOMS: {symptoms_text}

Provide a structured analysis in this EXACT format:
ANALYSIS: [Brief clinical analysis of the symptoms, 2-3 sentences]
RISK_LEVEL: [exactly one of: low / moderate / high / critical]
RECOMMENDATION: [Specific actionable recommendations, 2-3 bullet points using bullet]
URGENCY: [Timeframe for seeking care: immediately / within 24 hours / within a week / monitor at home]

Be professional, empathetic, and thorough. Always recommend consulting a doctor for serious concerns."""

    text = _chat(system, user, max_tokens=600)
    result = {"ai_analysis": "", "ai_recommendation": "", "risk_level": "low", "urgency": "monitor at home"}
    for line in text.split("\n"):
        if line.startswith("ANALYSIS:"):
            result["ai_analysis"] = line.replace("ANALYSIS:", "").strip()
        elif line.startswith("RISK_LEVEL:"):
            level = line.replace("RISK_LEVEL:", "").strip().lower()
            result["risk_level"] = level if level in ["low", "moderate", "high", "critical"] else "low"
        elif line.startswith("RECOMMENDATION:"):
            result["ai_recommendation"] = line.replace("RECOMMENDATION:", "").strip()
        elif line.startswith("URGENCY:"):
            result["urgency"] = line.replace("URGENCY:", "").strip()
    if not result["ai_analysis"]:
        result["ai_analysis"] = text[:300]
    if not result["ai_recommendation"]:
        result["ai_recommendation"] = "Please consult your healthcare provider."
    if result["risk_level"] in ["high", "critical"]:
        create_alert(patient_id, "symptom_risk",
                     f"WARNING {result['risk_level'].upper()} RISK: {symptoms_text[:100]}",
                     severity=result["risk_level"])
    return result


def analyze_vitals(patient_id: str, vitals: dict) -> dict:
    patient = get_patient(patient_id)
    if not patient:
        return {"status": "unknown", "insights": "Patient not found"}
    system = "You are a clinical AI assistant. Analyze patient vitals and respond in the exact format requested."
    user = f"""Analyze these patient vitals.

Patient: {patient['name']}, Age: {patient['age']}, Gender: {patient['gender']}
Chronic Conditions: {patient.get('chronic_conditions', 'None')}

VITALS:
- Heart Rate: {vitals.get('heart_rate')} bpm
- Blood Pressure: {vitals.get('blood_pressure_systolic')}/{vitals.get('blood_pressure_diastolic')} mmHg
- Temperature: {vitals.get('temperature')} C
- SpO2: {vitals.get('spo2')}%
- Blood Glucose: {vitals.get('blood_glucose')} mg/dL
- Weight: {vitals.get('weight')} kg

Respond in this format:
STATUS: [normal / warning / critical]
INSIGHTS: [2-3 sentence clinical interpretation]
ANOMALIES: [List any concerning values, or None detected]
ADVICE: [One clear action item]"""

    text = _chat(system, user, max_tokens=400)
    result = {"status": "normal", "insights": "", "anomalies": "None", "advice": ""}
    for line in text.split("\n"):
        if line.startswith("STATUS:"):
            s = line.replace("STATUS:", "").strip().lower()
            result["status"] = s if s in ["normal", "warning", "critical"] else "normal"
        elif line.startswith("INSIGHTS:"):
            result["insights"] = line.replace("INSIGHTS:", "").strip()
        elif line.startswith("ANOMALIES:"):
            result["anomalies"] = line.replace("ANOMALIES:", "").strip()
        elif line.startswith("ADVICE:"):
            result["advice"] = line.replace("ADVICE:", "").strip()
    if not result["insights"]:
        result["insights"] = text[:300]
    if result["status"] == "critical":
        create_alert(patient_id, "vitals_critical",
                     f"Critical vitals detected! {result['anomalies']}", severity="critical")
    elif result["status"] == "warning":
        create_alert(patient_id, "vitals_warning",
                     f"Abnormal vitals: {result['anomalies']}", severity="warning")
    return result


def chat_with_ai(patient_id: str, user_message: str, chat_history: list) -> str:
    patient_context = _build_patient_context(patient_id)
    system = f"""You are HealthAI, a compassionate and knowledgeable AI health assistant.
You help patients understand their health, medications, and wellness.

CURRENT PATIENT CONTEXT:
{patient_context}

Guidelines:
- Be warm, empathetic, and clear
- Use simple language the patient can understand
- Always recommend consulting a doctor for medical decisions
- Reference the patient specific health data when relevant
- Never diagnose definitively, provide information and guidance
- Keep responses concise (2-4 paragraphs max)"""

    messages = [{"role": "system", "content": system}]
    for msg in chat_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["message"]})
    messages.append({"role": "user", "content": user_message})
    response = client.chat.completions.create(model=MODEL, max_tokens=600, messages=messages)
    return response.choices[0].message.content


def generate_health_summary(patient_id: str) -> str:
    patient_context = _build_patient_context(patient_id)
    system = "You are a medical AI that generates clear, professional health summary reports."
    user = f"""Generate a comprehensive health summary report for this patient.

{patient_context}

Include:
1. Overall health status assessment
2. Key health metrics review
3. Medication adherence notes
4. Risk factors identified
5. Recommended next steps

Format as a professional but readable health report. Be specific and actionable."""
    return _chat(system, user, max_tokens=800)


def get_medication_insights(patient_id: str) -> str:
    patient = get_patient(patient_id)
    meds = get_patient_medications(patient_id, active_only=True)
    if not meds:
        return "No active medications to analyze."
    med_list = "\n".join([f"- {m['medication_name']}: {m['dosage']} {m['frequency']}" for m in meds])
    system = "You are a clinical pharmacist AI. Provide clear, patient-friendly medication guidance."
    user = f"""Patient: {patient['name']}, Age: {patient['age']}
Allergies: {patient.get('allergies', 'None')}
Chronic Conditions: {patient.get('chronic_conditions', 'None')}

ACTIVE MEDICATIONS:
{med_list}

Provide:
1. Brief overview of medication purposes
2. Any potential interactions to watch for
3. General adherence tips
4. When to contact doctor

Keep it patient-friendly and informative."""
    return _chat(system, user, max_tokens=500)