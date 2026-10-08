def explain_escalation(patient, concern, monitor_result):
    reasons = list(monitor_result.get("reasons", []))
    reasons.append("New concern reported" if concern else "Care-team review requested")
    if getattr(patient, "photos", []):
        reasons.append("Recent recovery photo available")
    return reasons
