# RecoverLink 2.0

RecoverLink is a Flask + SQLite post-surgical recovery coordination demo for a human-in-the-loop care workflow.

## Run on Windows

```powershell
python -m pip install -r requirements.txt
python seed.py
python app.py
```

Open `http://127.0.0.1:5000`.


## Demo story

Doctor defines recovery pathways and assigns the care team. Patients see a simple recovery dashboard with daily tasks, medication information from the doctor plan, next appointment, treatment schedule, timeline, and concern/photo reporting. Care Team sees assigned patients, concerns, recovery context, professional notes, photos, escalation and handover. Doctors see the recovery command center, trajectory monitoring, escalations and decisions. Admin sees hospital operations.

The system is decision-support only. It does not diagnose, prescribe, or change treatment automatically.


Demo includes exactly three seeded patient cases. Doctor and assigned care-team users can view patient contact details and use phone/email/audio/video contact actions.


## RecoverLink Enhanced package notes

This enhanced copy preserves the original role dashboards and adds:
- Patient profile editing for date of birth, phone, contact information and emergency contact.
- Shift-handover acknowledgement records, with an explicit pending/acknowledged state.
- Authorization checks before recovery-photo files are served to a logged-in user.
- Audio/video WebRTC consultation demo workflow already included in this project.

### Important prototype limitations
- Audio/video calling requires both participants to sign in and open the same call link. This development version uses a public STUN server and may not connect across every network; a production deployment needs a managed TURN/signalling setup, HTTPS, security review and monitoring.
- Recovery deviation signals are decision-support only, not diagnosis or emergency triage. A qualified healthcare professional must review concerns.
- Demo records and demo credentials are fictional. Do not upload real patient health information to a public or unreviewed deployment.
- `python seed.py` resets the local demo database. Do not run it if you need to preserve locally entered demo records.


## Recovery Continuity additions (prototype)

The doctor navigation includes **Recovery Continuity**, a coordination workspace for concerns linked to the doctor's patients. It supports assigning a care-team owner, setting a deadline, acknowledging a concern, marking it resolved with a note, highlighting missing ownership/overdue work, and viewing recent timeline events. A separate `ConcernWorkflow` table stores this metadata so existing demo database tables do not need new columns. `db.create_all()` creates the new table on startup.

The existing Recovery Monitor uses rule-based signals from recorded observations and available recovery-plan milestones. It is decision support only, not a diagnosis or a substitute for clinical review. The escalation and audit/timeline records should be verified against your intended real-world workflow before deployment.

This is a local demonstration project, not a production clinical system. Before real patient use, add and test stronger access controls, deployment security, backups, consent/privacy controls, notification delivery, and clinical governance.

## Recovery Continuity upgrade notes

The Recovery Continuity workspace now supports:
- assigning a concern to a care-team owner and setting a deadline;
- recording acknowledgement and requiring a resolution note before closing a concern;
- creating a tracked escalation for a concern (duplicate open escalations are prevented);
- identifying unassigned and overdue concerns in the care-gap panel;
- adding workflow and escalation actions to the patient timeline for audit review.

Recovery deviation flags are rule-based decision-support prompts using available recorded observations and clinician plan references. They are not diagnoses and should be reviewed by a qualified clinician. The escalation workflow records items in the local database; production notifications, deployment security, and clinical validation are separate work still required.

After extracting this ZIP, install dependencies with `python -m pip install -r requirements.txt`, then start with `python start_recoverlink.py`. Do not run `seed.py` if you need to preserve the demo data you have already entered in this copy.


## RecoverLink Continuity Upgrade (local demo)

This copy adds saved patient document metadata/uploads, authenticated patient-to-care-team messages, explicit care-gap reason labels, care-gap/task analytics for the doctor dashboard, and due/overdue task reminders for patient and care-team dashboards. The patient dashboard already brings surgery, recovery plan, tasks, concerns, observations, appointments and timeline into one view.

### Demo care-gap examples

When you run `python seed.py`, the demo data includes two visible care gaps: (1) Meena Raj's concern has an assigned nurse but a deadline in the past; (2) Rahul S's concern has no owner assigned. Saving an owner/deadline or resolving a concern changes the care-gap calculation based on the saved records.

**Important:** `seed.py` resets the local demo database (`db.drop_all()` then `db.create_all()`). Do not run it if you need to preserve data entered in this copy. To create the two sample care gaps in a fresh demo database, back up the database first, then run the seed script intentionally.

### Documents and messaging

Patients can upload PDF/PNG/JPG/WEBP recovery documents and download their own saved files. The patient messages page can send a message to the doctor or active assigned care-team members. Access is authenticated and recipient choices are restricted to the patient's care team. This is a local prototype, not a production-secure medical records or emergency messaging service.

### Future integrations

FHIR interoperability and external AI services are roadmap items only. No live hospital/EHR integration or external AI API is enabled by this upgrade. Recovery deviation signals remain decision support and must be reviewed by qualified professionals.
