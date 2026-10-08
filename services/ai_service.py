from services.recovery_monitor import detect_recovery_deviation_service as _detect_recovery_deviation_service

def generate_recovery_summary(patient):
    result = detect_recovery_deviation_service(patient)
    return {
        "summary": result["message"],
        "reasons": result["reasons"],
        "mode": "Rule-based decision support"
    }

def detect_recovery_deviation_service(patient):
    return _detect_recovery_deviation_service(patient)

def summarize_patient_concern(concern):
    text = (concern.text or concern.voice_transcript or "").strip()
    return text[:500] if text else "Patient concern submitted without text."

def generate_handover_summary(patient):
    latest = sorted(patient.concerns, key=lambda x: x.created_at, reverse=True)[:3]
    return "Recent concerns: " + "; ".join((c.text or c.voice_transcript or c.category)[:100] for c in latest)
