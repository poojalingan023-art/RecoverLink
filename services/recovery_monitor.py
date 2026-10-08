from models import RecoveryObservation

def detect_recovery_deviation_service(patient):
    observations = RecoveryObservation.query.filter_by(patient_id=patient.id, indicator="Pain").order_by(RecoveryObservation.recorded_at.asc()).all()
    values = [float(x.value) for x in observations]
    reasons = []
    if len(values) >= 2 and values[-1] > values[-2]:
        reasons.append(f"Pain increased from {values[-2]:g}/10 to {values[-1]:g}/10")
    if len(values) >= 3 and values[-1] > values[-3]:
        reasons.append("Recent pain is above the earlier recovery trend")
    # Demo pathway comparison: use the latest expected milestone as a soft reference.
    expected = []
    for plan in patient.recovery_plans:
        for m in plan.milestones:
            if m.indicator.lower() == "pain" and m.expected_value:
                try: expected.append(float(m.expected_value.split('/')[0]))
                except Exception: pass
    if values and expected and values[-1] > max(expected[-2:] or expected) + 1:
        reasons.append("Observed recovery differs from the doctor-defined expected pathway")
    flag = bool(reasons)
    return {
        "flag": flag,
        "level": "YELLOW" if flag else "GREEN",
        "message": "Recovery trajectory requires professional review." if flag else "Recovery is currently on track.",
        "reasons": reasons or ["No current deviation signal identified from recorded recovery data."],
        "values": values,
    }
