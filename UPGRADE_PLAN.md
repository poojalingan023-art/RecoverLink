# RecoverLink Upgrade Plan

## Implemented in this separate copy
- Care-gap detection uses saved concern/workflow data; unresolved concerns without a valid care-team owner or with past deadlines are shown with the relevant reason.
- Existing concern assignment, deadline, acknowledgement, escalation, resolution-note and timeline workflow retained.
- Existing patient dashboard combines surgery, recovery plan, observations, tasks, concerns, appointments, treatment schedule, photos and timeline.
- Due-today and overdue task reminders on patient and care-team dashboards; overdue task and care-gap metrics on doctor dashboard.
- Doctor recovery analytics summary based on the existing rule-based recovery monitor.
- Patient document upload/download for PDF, PNG, JPG, JPEG and WEBP with metadata saved in SQLite.
- Patient messages to the doctor or active assigned care-team member, plus a doctor/care-team inbox with replies to assigned patients; messages are saved in SQLite and reflected in the recovery timeline.
- Seed demo examples: Meena Raj has an assigned but overdue concern; Rahul S has an unassigned concern.
- Launcher checks imports before attempting dependency installation and seeds only if the local database does not exist.

## Future roadmap (not implemented)
- FHIR / live hospital EHR integration.
- External AI API integration.
- Production email/SMS/push notifications.
- Production-grade medical document security, hosting, audit/compliance review and clinical validation.

## Important
`python seed.py` resets the local demo database. The launcher runs it only when there is no database. Do not run it manually if you need to preserve locally entered data.

## Verification status
Python syntax compilation passed for `app.py`, `models.py`, `seed.py` and `start_recoverlink.py`. Full runtime tests were not completed in the build environment because Flask packages were unavailable and package installation could not reach the package index. Please test login, care-gap updates, message submission and document upload on the Windows machine before relying on the changes.
