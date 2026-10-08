from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False)  # doctor, care_team, patient, admin
    professional_role = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PatientProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    date_of_birth = db.Column(db.String(20))
    contact_information = db.Column(db.String(255))
    phone_number = db.Column(db.String(40))
    emergency_contact = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref=db.backref("patient_profile", uselist=False))

class Surgery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    surgery_type = db.Column(db.String(180), nullable=False)
    surgery_date = db.Column(db.Date, nullable=False)
    discharge_date = db.Column(db.Date)
    hospital = db.Column(db.String(180))
    surgeon = db.Column(db.String(180))
    notes = db.Column(db.Text)
    patient = db.relationship("PatientProfile", backref="surgeries")

class RecoveryPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    instructions = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    patient = db.relationship("PatientProfile", backref="recovery_plans")
    doctor = db.relationship("User", foreign_keys=[doctor_id])

class RecoveryMilestone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recovery_plan_id = db.Column(db.Integer, db.ForeignKey("recovery_plan.id"), nullable=False)
    day_week = db.Column(db.String(40), nullable=False)
    indicator = db.Column(db.String(100), nullable=False)
    expected_value = db.Column(db.String(80))
    expected_range = db.Column(db.String(80))
    notes = db.Column(db.Text)
    recovery_plan = db.relationship("RecoveryPlan", backref="milestones")

class CareTeamAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    care_team_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    role = db.Column(db.String(80), nullable=False)
    start_date = db.Column(db.Date, default=datetime.utcnow)
    end_date = db.Column(db.Date)
    active = db.Column(db.Boolean, default=True)
    patient = db.relationship("PatientProfile", backref="assignments")
    care_team_user = db.relationship("User", foreign_keys=[care_team_user_id])
    assigner = db.relationship("User", foreign_keys=[assigned_by])

class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    prescribed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    dosage = db.Column(db.String(160), nullable=False)
    frequency = db.Column(db.String(160), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    instructions = db.Column(db.Text)
    patient = db.relationship("PatientProfile", backref="medications")

class MedicationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey("medication.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    status = db.Column(db.String(30), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    medication = db.relationship("Medication")

class RecoveryTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)
    frequency = db.Column(db.String(120))
    due_date = db.Column(db.Date)
    status = db.Column(db.String(30), default="Pending")
    patient = db.relationship("PatientProfile", backref="tasks")

class SymptomRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    symptom = db.Column(db.String(180), nullable=False)
    severity = db.Column(db.Integer)
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship("PatientProfile", backref="symptoms")

class WoundPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient_note = db.Column(db.Text)
    ai_flag = db.Column(db.Boolean, default=False)
    ai_explanation = db.Column(db.Text)
    patient = db.relationship("PatientProfile", backref="photos")

class PatientConcern(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    text = db.Column(db.Text)
    voice_transcript = db.Column(db.Text)
    priority = db.Column(db.String(30), default="GREEN")
    status = db.Column(db.String(30), default="New")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship("PatientProfile", backref="concerns")

class ConcernAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    concern_id = db.Column(db.Integer, db.ForeignKey("patient_concern.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    concern = db.relationship("PatientConcern", backref="attachments")

class CareTeamNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    care_team_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    concern_id = db.Column(db.Integer, db.ForeignKey("patient_concern.id"))
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship("PatientProfile", backref="care_notes")
    author = db.relationship("User")
    concern = db.relationship("PatientConcern")

class Escalation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    concern_id = db.Column(db.Integer, db.ForeignKey("patient_concern.id"))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    level = db.Column(db.String(30), default="YELLOW")
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="Open")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    patient = db.relationship("PatientProfile", backref="escalations")
    creator = db.relationship("User", foreign_keys=[created_by])
    doctor = db.relationship("User", foreign_keys=[doctor_id])
    concern = db.relationship("PatientConcern")

class DoctorDecision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    escalation_id = db.Column(db.Integer, db.ForeignKey("escalation.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    decision_note = db.Column(db.Text, nullable=False)
    action = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    escalation = db.relationship("Escalation", backref="decisions")
    doctor = db.relationship("User")

class ShiftHandover(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    shift = db.Column(db.String(40), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    pending_items = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship("PatientProfile", backref="handovers")
    author = db.relationship("User")

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date_time = db.Column(db.DateTime, nullable=False)
    purpose = db.Column(db.String(180), nullable=False)
    status = db.Column(db.String(40), default="Scheduled")
    patient = db.relationship("PatientProfile", backref="appointments")
    doctor = db.relationship("User")

class TreatmentSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    scheduled_for = db.Column(db.DateTime, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    details = db.Column(db.Text)
    status = db.Column(db.String(40), default="Scheduled")
    patient = db.relationship("PatientProfile", backref="treatment_schedules")

class RecoveryObservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    indicator = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(40))
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship("PatientProfile", backref="observations")
    recorder = db.relationship("User")

class TimelineEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    event_type = db.Column(db.String(60), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship("PatientProfile", backref="timeline_events")
    creator = db.relationship("User")


class CallSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    call_token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    caller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    callee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    mode = db.Column(db.String(20), nullable=False, default="video")
    status = db.Column(db.String(30), nullable=False, default="Ringing")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    answered_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    caller = db.relationship("User", foreign_keys=[caller_id])
    callee = db.relationship("User", foreign_keys=[callee_id])
    patient = db.relationship("PatientProfile")

class CallSignal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("call_session.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    signal_type = db.Column(db.String(30), nullable=False)
    payload = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    session = db.relationship("CallSession", backref=db.backref("signals", lazy=True, cascade="all, delete-orphan"))
    sender = db.relationship("User")


class HandoverAcknowledgement(db.Model):
    """Records who acknowledged a shift handover and when."""
    id = db.Column(db.Integer, primary_key=True)
    handover_id = db.Column(db.Integer, db.ForeignKey("shift_handover.id"), nullable=False, index=True)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    note = db.Column(db.String(500))
    acknowledged_at = db.Column(db.DateTime, default=datetime.utcnow)
    handover = db.relationship("ShiftHandover", backref=db.backref("acknowledgements", lazy=True, cascade="all, delete-orphan"))
    user = db.relationship("User")


class ConcernWorkflow(db.Model):
    """Coordination metadata for a concern; separate table avoids altering existing demo tables."""
    id = db.Column(db.Integer, primary_key=True)
    concern_id = db.Column(db.Integer, db.ForeignKey("patient_concern.id"), unique=True, nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    deadline = db.Column(db.DateTime)
    status = db.Column(db.String(30), default="Open", nullable=False)
    acknowledged_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    resolution_notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    concern = db.relationship("PatientConcern", backref=db.backref("workflow", uselist=False))
    owner = db.relationship("User")


class PatientDocument(db.Model):
    """Patient recovery documents stored with metadata; files stay inside uploads."""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False, index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False, unique=True)
    document_type = db.Column(db.String(80), default="Recovery document")
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship("PatientProfile", backref=db.backref("documents", lazy=True))
    uploader = db.relationship("User")


class SecureMessage(db.Model):
    """Authenticated patient/care-team messages for the local demo workflow."""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime)
    patient = db.relationship("PatientProfile", backref=db.backref("secure_messages", lazy=True))
    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])
