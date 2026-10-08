from datetime import datetime, date
from functools import wraps
from pathlib import Path
from uuid import uuid4
import json

from flask import Flask, render_template, redirect, url_for, request, flash, abort, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, Length, NumberRange
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import Config
from models import *
from services.ai_service import detect_recovery_deviation_service
from services.escalation_service import explain_escalation

login_manager = LoginManager()
csrf = CSRFProtect()

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")

class RegisterForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    role = SelectField("Role", choices=[("patient","Patient"),("care_team","Care team")])
    submit = SubmitField("Create account")

class ConcernForm(FlaskForm):
    category = SelectField("Concern type", choices=[
        ("Pain / Recovery","Pain / Recovery"),("Exercise","Exercise"),
        ("Nutrition","Nutrition"),("Medication question","Medication question"),
        ("General recovery","General recovery")
    ], validators=[DataRequired()])
    text = TextAreaField("Describe your concern")
    voice_transcript = TextAreaField("Voice transcript")
    priority = SelectField("Initial priority", choices=[("GREEN","Routine"),("YELLOW","Needs monitoring"),("RED","Doctor review")])
    submit = SubmitField("Send concern")

class NoteForm(FlaskForm):
    note = TextAreaField("Professional note", validators=[DataRequired(), Length(min=5)])
    submit = SubmitField("Save note")

class EscalationForm(FlaskForm):
    level = SelectField("Escalation level", choices=[("YELLOW","YELLOW — Needs monitoring/review"),("RED","RED — Doctor review required"),("URGENT","URGENT — Follow hospital/emergency protocol")])
    reason = TextAreaField("Reason", validators=[DataRequired(), Length(min=10)])
    submit = SubmitField("Escalate to doctor")

class DecisionForm(FlaskForm):
    action = SelectField("Doctor action", choices=[("Continue plan","Continue plan"),("Follow-up review","Follow-up review"),("Update recovery plan","Update recovery plan"),("Resolve","Resolve")])
    decision_note = TextAreaField("Decision note", validators=[DataRequired(), Length(min=5)])
    submit = SubmitField("Record decision")

class HandoverForm(FlaskForm):
    shift = SelectField("Shift", choices=[("Morning","Morning"),("Evening","Evening"),("Night","Night")])
    summary = TextAreaField("Handover summary", validators=[DataRequired(), Length(min=5)])
    pending_items = TextAreaField("Pending items")
    submit = SubmitField("Save handover")

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(Path(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///",""))).parent.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    def role_required(*roles):
        def deco(fn):
            @wraps(fn)
            @login_required
            def wrapped(*args, **kwargs):
                if current_user.role not in roles:
                    abort(403)
                return fn(*args, **kwargs)
            return wrapped
        return deco

    def patient_for_user():
        pp = PatientProfile.query.filter_by(user_id=current_user.id).first()
        if not pp: abort(403)
        return pp

    def log_event(patient_id, event_type, title, description, creator=None):
        db.session.add(TimelineEvent(patient_id=patient_id, event_type=event_type, title=title,
                                     description=description, created_by=(creator or current_user.id)))

    @app.context_processor
    def inject_globals():
        return {"today": date.today(), "app_name":"RecoverLink"}

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("landing.html")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.role == "patient": return redirect(url_for("patient_dashboard"))
        if current_user.role == "care_team": return redirect(url_for("care_dashboard"))
        if current_user.role == "doctor": return redirect(url_for("doctor_dashboard"))
        return redirect(url_for("admin_dashboard"))

    @app.route("/login", methods=["GET","POST"])
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            u = User.query.filter_by(email=form.email.data.lower().strip()).first()
            if u and check_password_hash(u.password_hash, form.password.data):
                login_user(u)
                flash("Welcome back to RecoverLink.", "success")
                return redirect(url_for("dashboard"))
            flash("Email or password is incorrect.", "danger")
        return render_template("login.html", form=form)

    @app.route("/register", methods=["GET","POST"])
    def register():
        form = RegisterForm()
        if form.validate_on_submit():
            email=form.email.data.lower().strip()
            if User.query.filter_by(email=email).first():
                flash("An account with this email already exists.", "danger")
            else:
                u=User(name=form.name.data, email=email, password_hash=generate_password_hash(form.password.data), role=form.role.data)
                db.session.add(u); db.session.flush()
                if u.role=="patient":
                    db.session.add(PatientProfile(user_id=u.id, contact_information="Update your contact information"))
                db.session.commit()
                flash("Account created. You can now sign in.", "success")
                return redirect(url_for("login"))
        return render_template("register.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user(); return redirect(url_for("index"))

    @app.route("/patient/dashboard")
    @role_required("patient")
    def patient_dashboard():
        # Use explicit queries here so optional/missing recovery records (especially
        # photos) can never prevent the patient dashboard from opening.
        p = patient_for_user()
        plan = RecoveryPlan.query.filter_by(patient_id=p.id).order_by(RecoveryPlan.created_at.desc()).first()
        surgery = Surgery.query.filter_by(patient_id=p.id).order_by(Surgery.surgery_date.desc()).first()
        tasks = RecoveryTask.query.filter_by(patient_id=p.id).order_by(RecoveryTask.due_date.asc()).all()
        meds = Medication.query.filter_by(patient_id=p.id).all()
        appointments = Appointment.query.filter_by(patient_id=p.id).order_by(Appointment.date_time.asc()).all()
        concerns = PatientConcern.query.filter_by(patient_id=p.id).order_by(PatientConcern.created_at.desc()).limit(4).all()
        photos = WoundPhoto.query.filter_by(patient_id=p.id).order_by(WoundPhoto.uploaded_at.desc()).limit(6).all()
        observations = RecoveryObservation.query.filter_by(patient_id=p.id, indicator="Pain").order_by(RecoveryObservation.recorded_at.asc()).all()
        events = TimelineEvent.query.filter_by(patient_id=p.id).order_by(TimelineEvent.created_at.desc()).limit(8).all()
        schedules = TreatmentSchedule.query.filter_by(patient_id=p.id).order_by(TreatmentSchedule.scheduled_for.asc()).all()
        trajectory = detect_recovery_deviation_service(p)
        today=date.today()
        overdue_tasks=[t for t in tasks if t.status!="Completed" and t.due_date and t.due_date < today]
        due_tasks=[t for t in tasks if t.status!="Completed" and t.due_date == today]
        return render_template("patient/dashboard.html", patient=p, plan=plan, surgery=surgery,
                               tasks=tasks, meds=meds, appointments=appointments, schedules=schedules, concerns=concerns,
                               photos=photos, events=events, observations=observations, trajectory=trajectory,
                               overdue_tasks=overdue_tasks, due_tasks=due_tasks)

    @app.route("/patient/profile", methods=["GET", "POST"])
    @role_required("patient")
    def patient_profile():
        patient = patient_for_user()
        if request.method == "POST":
            patient.phone_number = (request.form.get("phone_number") or "").strip()[:40]
            patient.contact_information = (request.form.get("contact_information") or "").strip()[:255]
            patient.emergency_contact = (request.form.get("emergency_contact") or "").strip()[:255]
            patient.date_of_birth = (request.form.get("date_of_birth") or "").strip()[:20]
            log_event(patient.id, "Profile", "Patient contact details updated",
                      "Patient updated their contact/emergency contact details.")
            db.session.commit()
            flash("Your patient details have been saved.", "success")
            return redirect(url_for("patient_profile"))
        return render_template("patient/profile.html", patient=patient)

    @app.route("/patient/recovery-plan")
    @role_required("patient")
    def patient_recovery_plan():
        p=patient_for_user()
        return render_template("patient/recovery_plan.html", patient=p, plan=p.recovery_plans[-1] if p.recovery_plans else None)

    @app.route("/patient/medications", methods=["GET","POST"])
    @role_required("patient")
    def patient_medications():
        p=patient_for_user()
        if request.method=="POST":
            mid=request.form.get("medication_id"); status=request.form.get("status")
            m=Medication.query.filter_by(id=mid,patient_id=p.id).first_or_404()
            db.session.add(MedicationLog(medication_id=m.id,patient_id=p.id,status=status))
            log_event(p.id,"Medication",f"Medication marked {status.lower()}",m.name)
            db.session.commit(); flash("Medication record saved.","success")
            return redirect(url_for("patient_medications"))
        return render_template("patient/medications.html",patient=p)

    @app.route("/patient/tasks", methods=["GET","POST"])
    @role_required("patient")
    def patient_tasks():
        p=patient_for_user()
        if request.method=="POST":
            t=RecoveryTask.query.filter_by(id=request.form.get("task_id"),patient_id=p.id).first_or_404()
            if t.status != "Completed":
                t.status="Completed"
                log_event(p.id,"Task","Recovery task completed",t.title)
                db.session.commit()
                flash("Task completed and saved to your recovery record.","success")
            else:
                flash("This task is already completed.","info")
            return redirect(url_for("patient_tasks"))
        return render_template("patient/tasks.html",patient=p)

    @app.route("/patient/appointments")
    @role_required("patient")
    def patient_appointments():
        return render_template("patient/appointments.html",patient=patient_for_user())

    @app.route("/patient/treatment-schedule")
    @role_required("patient")
    def patient_treatment_schedule():
        p=patient_for_user()
        schedules=TreatmentSchedule.query.filter_by(patient_id=p.id).order_by(TreatmentSchedule.scheduled_for.asc()).all()
        return render_template("patient/treatment_schedule.html", patient=p, schedules=schedules)

    @app.route("/patient/messages", methods=["GET", "POST"])
    @role_required("patient")
    def patient_messages():
        p = patient_for_user()
        plan = RecoveryPlan.query.filter_by(patient_id=p.id).order_by(RecoveryPlan.created_at.desc()).first()
        recipients = []
        if plan and plan.doctor:
            recipients.append(plan.doctor)
        for assignment in CareTeamAssignment.query.filter_by(patient_id=p.id, active=True).all():
            if assignment.care_team_user and assignment.care_team_user not in recipients:
                recipients.append(assignment.care_team_user)
        if request.method == "POST":
            recipient = User.query.filter(User.id == request.form.get("recipient_id"), User.id.in_([u.id for u in recipients])).first()
            body = (request.form.get("body") or "").strip()
            if not recipient or not body or len(body) > 3000:
                flash("Choose a member of your care team and enter a message (maximum 3,000 characters).", "danger")
            else:
                db.session.add(SecureMessage(patient_id=p.id, sender_id=current_user.id, recipient_id=recipient.id, body=body))
                log_event(p.id, "Message", "Patient sent a care-team message", f"Message sent to {recipient.name}.")
                db.session.commit()
                flash("Message sent to your care team.", "success")
                return redirect(url_for("patient_messages"))
        messages = SecureMessage.query.filter_by(patient_id=p.id).order_by(SecureMessage.created_at.desc()).all()
        notes = sorted(p.care_notes, key=lambda x:x.created_at, reverse=True)
        return render_template("patient/messages.html", patient=p, notes=notes, messages=messages, recipients=recipients)

    @app.route("/care-messages", methods=["GET", "POST"])
    @role_required("doctor", "care_team")
    def care_messages():
        if current_user.role == "doctor":
            patients = [x for x in PatientProfile.query.all() if any(plan.doctor_id == current_user.id for plan in x.recovery_plans)]
        else:
            assigned_ids = [a.patient_id for a in CareTeamAssignment.query.filter_by(care_team_user_id=current_user.id, active=True).all()]
            patients = PatientProfile.query.filter(PatientProfile.id.in_(assigned_ids)).all() if assigned_ids else []
        patient_ids = [p.id for p in patients]
        if request.method == "POST":
            patient = PatientProfile.query.filter(PatientProfile.id == request.form.get("patient_id"), PatientProfile.id.in_(patient_ids)).first()
            body = (request.form.get("body") or "").strip()
            if not patient or not body or len(body) > 3000:
                flash("Choose an assigned patient and enter a message (maximum 3,000 characters).", "danger")
            else:
                db.session.add(SecureMessage(patient_id=patient.id, sender_id=current_user.id,
                                             recipient_id=patient.user_id, body=body))
                log_event(patient.id, "Message", "Care-team reply sent", f"Message sent to {patient.user.name}.")
                db.session.commit()
                flash("Reply sent to the patient.", "success")
                return redirect(url_for("care_messages"))
        messages = SecureMessage.query.filter(SecureMessage.patient_id.in_(patient_ids)).order_by(SecureMessage.created_at.desc()).all() if patient_ids else []
        return render_template("care_team/messages.html", patients=patients, messages=messages)

    @app.route("/patient/documents", methods=["GET", "POST"])
    @role_required("patient")
    def patient_documents():
        p = patient_for_user()
        if request.method == "POST":
            uploaded = request.files.get("document")
            kind = (request.form.get("document_type") or "Recovery document").strip()[:80]
            if not uploaded or not uploaded.filename:
                flash("Choose a PDF or image document to upload.", "danger")
            else:
                original = secure_filename(uploaded.filename)
                ext = Path(original).suffix.lower()
                if ext not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
                    flash("Only PDF, PNG, JPG and WEBP files are allowed.", "danger")
                else:
                    stored = f"doc_{p.id}_{uuid4().hex}{ext}"
                    uploaded.save(Path(app.config["UPLOAD_FOLDER"]) / stored)
                    db.session.add(PatientDocument(patient_id=p.id, uploaded_by=current_user.id,
                                                   original_name=original, stored_name=stored, document_type=kind))
                    log_event(p.id, "Document", "Recovery document uploaded", f"{kind}: {original}")
                    db.session.commit()
                    flash("Document uploaded to your recovery record.", "success")
                    return redirect(url_for("patient_documents"))
        documents = PatientDocument.query.filter_by(patient_id=p.id).order_by(PatientDocument.uploaded_at.desc()).all()
        return render_template("patient/documents.html", patient=p, documents=documents)

    @app.route("/patient/documents/<int:document_id>/download")
    @role_required("patient")
    def patient_document_download(document_id):
        p = patient_for_user()
        document = PatientDocument.query.filter_by(id=document_id, patient_id=p.id).first_or_404()
        return send_from_directory(app.config["UPLOAD_FOLDER"], document.stored_name,
                                   as_attachment=True, download_name=document.original_name)

    @app.route("/patient/concern", methods=["GET","POST"])
    @role_required("patient")
    def patient_concern():
        p = patient_for_user()
        form = ConcernForm()
        if form.validate_on_submit():
            c = PatientConcern(patient_id=p.id, category=form.category.data, text=form.text.data,
                               voice_transcript=form.voice_transcript.data, priority=form.priority.data)
            db.session.add(c)
            db.session.flush()

            # Optional photo can be attached to the concern so the care team sees
            # the wound/recovery image together with the patient's report.
            f = request.files.get("photo")
            if f and f.filename:
                ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
                if ext not in app.config["ALLOWED_IMAGE_EXTENSIONS"]:
                    db.session.rollback()
                    flash("Only JPG, JPEG, PNG or WEBP images are allowed.", "danger")
                    return render_template("patient/concern.html", form=form)
                name = f"{uuid4().hex}.{ext}"
                f.save(Path(app.config["UPLOAD_FOLDER"]) / name)
                db.session.add(WoundPhoto(patient_id=p.id, file_path=name,
                                          patient_note=(form.text.data or form.voice_transcript.data or "")[:500],
                                          ai_flag=False,
                                          ai_explanation="Photo is provided to the assigned care team for professional review."))
                db.session.add(ConcernAttachment(concern_id=c.id, file_path=name, file_type=ext))

            log_event(p.id, "Patient concern", "New concern submitted",
                      f"{c.category}: {(c.text or c.voice_transcript or '')[:240]}")
            db.session.commit()
            flash("Your concern and any attached photo have been sent to the assigned care team.", "success")
            return redirect(url_for("patient_dashboard"))
        return render_template("patient/concern.html", form=form)

    @app.route("/patient/upload-photo", methods=["POST"])
    @role_required("patient")
    def upload_photo():
        p=patient_for_user(); f=request.files.get("photo")
        if not f or not f.filename:
            flash("Choose an image first.","danger"); return redirect(url_for("patient_dashboard"))
        ext=f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
        if ext not in app.config["ALLOWED_IMAGE_EXTENSIONS"]:
            flash("Only JPG, JPEG, PNG or WEBP images are allowed.","danger"); return redirect(url_for("patient_dashboard"))
        name=f"{uuid4().hex}.{ext}"
        f.save(Path(app.config["UPLOAD_FOLDER"])/name)
        photo=WoundPhoto(patient_id=p.id,file_path=name,patient_note=request.form.get("patient_note",""),
                         ai_flag=False,ai_explanation="Optional decision-support comparison is not enabled in this demo.")
        db.session.add(photo); log_event(p.id,"Photo","Recovery photo uploaded","Photo added to recovery history."); db.session.commit()
        flash("Photo added to your recovery history.","success")
        return redirect(url_for("patient_dashboard"))

    @app.route("/patient/timeline")
    @role_required("patient")
    def patient_timeline():
        p=patient_for_user()
        return render_template("patient/timeline.html",patient=p,events=sorted(p.timeline_events,key=lambda x:x.created_at,reverse=True))

    def user_patient_for_call(uid):
        pp=PatientProfile.query.filter_by(user_id=uid).first()
        return pp

    def can_call_user(target_id):
        target=User.query.get_or_404(target_id)
        if target.id == current_user.id or target.role == "admin":
            return None
        if current_user.role == "patient":
            p=patient_for_user()
            linked_doctor=any(r.doctor_id == target.id for r in p.recovery_plans)
            linked_care=any(a.care_team_user_id == target.id and a.active for a in p.assignments)
            return p if linked_doctor or linked_care else None
        if current_user.role == "doctor":
            pp=user_patient_for_call(target.id)
            return pp if pp and any(r.doctor_id == current_user.id for r in pp.recovery_plans) else None
        if current_user.role == "care_team":
            pp=user_patient_for_call(target.id)
            return pp if pp and any(a.care_team_user_id == current_user.id and a.active for a in pp.assignments) else None
        return None

    @app.route("/call/start/<int:target_id>/<mode>")
    @role_required("patient","care_team","doctor")
    def start_call(target_id, mode):
        if mode not in ("audio","video"): abort(400)
        patient=can_call_user(target_id)
        if not patient: abort(403)
        target=User.query.get_or_404(target_id)
        # Reuse an active ringing/connected call between the same users.
        active=CallSession.query.filter(
            ((CallSession.caller_id==current_user.id)&(CallSession.callee_id==target.id)) |
            ((CallSession.caller_id==target.id)&(CallSession.callee_id==current_user.id)),
            CallSession.status.in_(["Ringing","Connected"])
        ).order_by(CallSession.created_at.desc()).first()
        if active:
            return redirect(url_for("call_room",token=active.call_token))
        token=uuid4().hex
        call=CallSession(call_token=token,caller_id=current_user.id,callee_id=target.id,patient_id=patient.id,mode=mode)
        db.session.add(call)
        log_event(patient.id,"Call",f"{mode.title()} call started",f"Call invitation sent to {target.name}.")
        db.session.commit()
        return redirect(url_for("call_room",token=token))

    @app.route("/call/<token>")
    @role_required("patient","care_team","doctor")
    def call_room(token):
        call=CallSession.query.filter_by(call_token=token).first_or_404()
        if current_user.id not in (call.caller_id,call.callee_id): abort(403)
        other=call.callee if current_user.id==call.caller_id else call.caller
        return render_template("call.html",call=call,other=other,csrf_token_value=generate_csrf())

    @app.route("/call/<token>/join", methods=["POST"])
    @role_required("patient","care_team","doctor")
    def join_call(token):
        call=CallSession.query.filter_by(call_token=token).first_or_404()
        if current_user.id not in (call.caller_id,call.callee_id): abort(403)
        if current_user.id == call.callee_id and call.status == "Ringing":
            call.status="Connected"; call.answered_at=datetime.utcnow()
            log_event(call.patient_id,"Call",f"{call.mode.title()} call connected",f"Connected with {call.caller.name}.")
            db.session.commit()
        return jsonify(ok=True,status=call.status)

    @app.route("/call/<token>/signal", methods=["GET","POST"])
    @role_required("patient","care_team","doctor")
    def call_signal(token):
        call=CallSession.query.filter_by(call_token=token).first_or_404()
        if current_user.id not in (call.caller_id,call.callee_id): abort(403)
        if request.method=="POST":
            data=request.get_json(silent=True) or {}
            signal_type=data.get("type")
            payload=data.get("payload")
            if signal_type not in ("offer","answer","ice","hangup") or payload is None: abort(400)
            db.session.add(CallSignal(session_id=call.id,sender_id=current_user.id,signal_type=signal_type,payload=json.dumps(payload)))
            if signal_type=="hangup":
                call.status="Ended"; call.ended_at=datetime.utcnow()
            db.session.commit()
            return jsonify(ok=True)
        after=int(request.args.get("after",0))
        rows=CallSignal.query.filter(CallSignal.session_id==call.id,CallSignal.id>after,CallSignal.sender_id!=current_user.id).order_by(CallSignal.id.asc()).limit(30).all()
        return jsonify(signals=[{"id":x.id,"type":x.signal_type,"payload":json.loads(x.payload)} for x in rows],status=call.status)

    @app.route("/call/incoming")
    @role_required("patient","care_team","doctor")
    def incoming_calls():
        calls=CallSession.query.filter_by(callee_id=current_user.id,status="Ringing").order_by(CallSession.created_at.desc()).limit(5).all()
        return jsonify(calls=[{"token":c.call_token,"caller":c.caller.name,"mode":c.mode} for c in calls])

    @app.route("/call/<token>/end", methods=["POST"])
    @role_required("patient","care_team","doctor")
    def end_call(token):
        call=CallSession.query.filter_by(call_token=token).first_or_404()
        if current_user.id not in (call.caller_id,call.callee_id): abort(403)
        call.status="Ended"; call.ended_at=datetime.utcnow()
        db.session.add(CallSignal(session_id=call.id,sender_id=current_user.id,signal_type="hangup",payload=json.dumps({})))
        log_event(call.patient_id,"Call",f"{call.mode.title()} call ended",f"Call with {call.caller.name if current_user.id==call.callee_id else call.callee.name} ended.")
        db.session.commit()
        return jsonify(ok=True)

    @app.route("/uploads/<path:name>")
    @login_required
    def uploads(name):
        # Recovery photos are sensitive health information: verify access against
        # the patient record before serving a file.
        photo = WoundPhoto.query.filter_by(file_path=name).first()
        attachment = ConcernAttachment.query.filter_by(file_path=name).first()
        patient_id = photo.patient_id if photo else None
        if patient_id is None and attachment:
            concern = PatientConcern.query.get(attachment.concern_id)
            patient_id = concern.patient_id if concern else None
        if patient_id is None:
            abort(404)
        allowed = False
        if current_user.role == "patient":
            own = PatientProfile.query.filter_by(user_id=current_user.id).first()
            allowed = bool(own and own.id == patient_id)
        elif current_user.role == "care_team":
            allowed = patient_id in assigned_patient_ids()
        elif current_user.role == "doctor":
            allowed = RecoveryPlan.query.filter_by(patient_id=patient_id, doctor_id=current_user.id).first() is not None
        elif current_user.role == "admin":
            allowed = True
        if not allowed:
            abort(403)
        return send_from_directory(app.config["UPLOAD_FOLDER"], name)

    def assigned_patient_ids():
        return [a.patient_id for a in CareTeamAssignment.query.filter_by(care_team_user_id=current_user.id,active=True).all()]

    @app.route("/care-team/dashboard")
    @role_required("care_team")
    def care_dashboard():
        ids=assigned_patient_ids()
        patients=PatientProfile.query.filter(PatientProfile.id.in_(ids)).all() if ids else []
        concerns=PatientConcern.query.filter(PatientConcern.patient_id.in_(ids),PatientConcern.status!="Resolved").order_by(PatientConcern.created_at.desc()).all() if ids else []
        esc=Escalation.query.filter(Escalation.patient_id.in_(ids),Escalation.status=="Open").order_by(Escalation.created_at.desc()).all() if ids else []
        overdue_tasks=RecoveryTask.query.filter(RecoveryTask.patient_id.in_(ids),RecoveryTask.status!="Completed",RecoveryTask.due_date < date.today()).all() if ids else []
        due_tasks=RecoveryTask.query.filter(RecoveryTask.patient_id.in_(ids),RecoveryTask.status!="Completed",RecoveryTask.due_date==date.today()).all() if ids else []
        return render_template("care_team/dashboard.html",patients=patients,concerns=concerns,escalations=esc,overdue_tasks=overdue_tasks,due_tasks=due_tasks)

    @app.route("/care-team/patients")
    @role_required("care_team")
    def care_patients():
        ids=assigned_patient_ids()
        patients=PatientProfile.query.filter(PatientProfile.id.in_(ids)).all() if ids else []
        return render_template("care_team/patients.html",patients=patients)

    @app.route("/care-team/patient/<int:pid>", methods=["GET","POST"])
    @role_required("care_team")
    def care_patient(pid):
        if pid not in assigned_patient_ids(): abort(403)
        p=PatientProfile.query.get_or_404(pid)
        note_form=NoteForm()
        esc_form=EscalationForm()
        if request.method=="POST" and request.form.get("action")=="note" and note_form.validate_on_submit():
            cid=request.form.get("concern_id")
            db.session.add(CareTeamNote(patient_id=pid,care_team_user_id=current_user.id,concern_id=cid or None,note=note_form.note.data))
            if cid:
                c=PatientConcern.query.get(cid)
                if c: c.status="Under review"
            log_event(pid,"Care-team note","Care-team note added",note_form.note.data[:300])
            db.session.commit(); flash("Professional note saved.","success"); return redirect(url_for("care_patient",pid=pid))
        if request.method=="POST" and request.form.get("action")=="escalate" and esc_form.validate_on_submit():
            cid=request.form.get("concern_id"); c=PatientConcern.query.get(cid) if cid else None
            doctor=RecoveryPlan.query.filter_by(patient_id=pid).order_by(RecoveryPlan.created_at.desc()).first()
            if not doctor: flash("No doctor is linked to this recovery plan yet.","danger")
            else:
                reason=esc_form.reason.data
                db.session.add(Escalation(patient_id=pid,concern_id=cid or None,created_by=current_user.id,doctor_id=doctor.doctor_id,
                                          level=esc_form.level.data,reason=reason,status="Open"))
                if c: c.status="Escalated"
                log_event(pid,"Escalation","Concern escalated to doctor",reason[:300]); db.session.commit()
                flash("Escalation sent to the doctor.","success")
            return redirect(url_for("care_patient",pid=pid))
        monitor=detect_recovery_deviation_service(p)
        surgery=Surgery.query.filter_by(patient_id=pid).order_by(Surgery.surgery_date.desc()).first()
        plan=RecoveryPlan.query.filter_by(patient_id=pid).order_by(RecoveryPlan.created_at.desc()).first()
        concerns=PatientConcern.query.filter_by(patient_id=pid).order_by(PatientConcern.created_at.desc()).all()
        photos=WoundPhoto.query.filter_by(patient_id=pid).order_by(WoundPhoto.uploaded_at.desc()).all()
        notes=CareTeamNote.query.filter_by(patient_id=pid).order_by(CareTeamNote.created_at.desc()).all()
        events=TimelineEvent.query.filter_by(patient_id=pid).order_by(TimelineEvent.created_at.desc()).all()
        return render_template("care_team/patient.html",patient=p,monitor=monitor,note_form=note_form,esc_form=esc_form,
                               surgery=surgery,plan=plan,concerns=concerns,photos=photos,notes=notes,events=events)

    @app.route("/care-team/concerns")
    @role_required("care_team")
    def care_concerns():
        ids=assigned_patient_ids()
        concerns=PatientConcern.query.filter(PatientConcern.patient_id.in_(ids)).order_by(PatientConcern.created_at.desc()).all() if ids else []
        return render_template("care_team/concerns.html",concerns=concerns)

    @app.route("/care-team/escalations")
    @role_required("care_team")
    def care_escalations():
        ids=assigned_patient_ids()
        escalations=Escalation.query.filter(Escalation.patient_id.in_(ids)).order_by(Escalation.created_at.desc()).all() if ids else []
        return render_template("care_team/escalations.html",escalations=escalations)

    @app.route("/care-team/handover", methods=["GET","POST"])
    @role_required("care_team")
    def care_handover():
        ids=assigned_patient_ids()
        form=HandoverForm()
        if form.validate_on_submit():
            pid=request.form.get("patient_id")
            if int(pid) not in ids: abort(403)
            db.session.add(ShiftHandover(patient_id=pid,created_by=current_user.id,shift=form.shift.data,
                                         summary=form.summary.data,pending_items=form.pending_items.data))
            log_event(pid,"Shift handover","Shift handover recorded",form.summary.data[:300]); db.session.commit()
            flash("Shift handover saved.","success"); return redirect(url_for("care_handover"))
        handovers=ShiftHandover.query.filter(ShiftHandover.patient_id.in_(ids)).order_by(ShiftHandover.created_at.desc()).all() if ids else []
        patients=PatientProfile.query.filter(PatientProfile.id.in_(ids)).all() if ids else []
        return render_template("care_team/handover.html",form=form,handovers=handovers,patients=patients)

    @app.route("/care-team/handover/<int:hid>/acknowledge", methods=["POST"])
    @role_required("care_team")
    def acknowledge_handover(hid):
        handover = ShiftHandover.query.get_or_404(hid)
        if handover.patient_id not in assigned_patient_ids():
            abort(403)
        existing = HandoverAcknowledgement.query.filter_by(
            handover_id=handover.id, acknowledged_by=current_user.id
        ).first()
        if not existing:
            note = (request.form.get("acknowledgement_note") or "").strip()[:500]
            db.session.add(HandoverAcknowledgement(
                handover_id=handover.id, acknowledged_by=current_user.id, note=note
            ))
            log_event(handover.patient_id, "Handover acknowledgement",
                      "Care handover acknowledged",
                      f"{current_user.name} acknowledged the {handover.shift.lower()} shift handover.")
            db.session.commit()
            flash("Handover acknowledgement recorded.", "success")
        else:
            flash("You have already acknowledged this handover.", "info")
        return redirect(url_for("care_handover"))

    @app.route("/doctor/dashboard")
    @role_required("doctor")
    def doctor_dashboard():
        patients=[x for x in PatientProfile.query.all() if any(p.doctor_id==current_user.id for p in x.recovery_plans)]
        escalations=Escalation.query.filter_by(doctor_id=current_user.id).order_by(Escalation.created_at.desc()).all()
        patient_ids=[p.id for p in patients]
        active_concerns=PatientConcern.query.filter(PatientConcern.patient_id.in_(patient_ids), PatientConcern.status!="Resolved").all() if patient_ids else []
        workflows={w.concern_id:w for w in ConcernWorkflow.query.filter(ConcernWorkflow.concern_id.in_([c.id for c in active_concerns])).all()} if active_concerns else {}
        now=datetime.utcnow()
        care_gaps=[]
        for concern in active_concerns:
            workflow=workflows.get(concern.id)
            valid_owner=bool(workflow and workflow.owner_id and User.query.filter_by(id=workflow.owner_id,role="care_team").first())
            if not valid_owner or (workflow.deadline and workflow.deadline < now and workflow.status!="Resolved"):
                care_gaps.append(concern)
        overdue_tasks=RecoveryTask.query.filter(RecoveryTask.patient_id.in_(patient_ids), RecoveryTask.status!="Completed", RecoveryTask.due_date < date.today()).all() if patient_ids else []
        flagged_patients=[(patient,detect_recovery_deviation_service(patient)) for patient in patients]
        deviation_count=sum(1 for _,result in flagged_patients if result.flag)
        return render_template("doctor/dashboard.html",patients=patients,escalations=escalations,care_gaps=care_gaps,overdue_tasks=overdue_tasks,deviation_count=deviation_count)

    @app.route("/doctor/patients")
    @role_required("doctor")
    def doctor_patients():
        patients=[x for x in PatientProfile.query.all() if any(p.doctor_id==current_user.id for p in x.recovery_plans)]
        return render_template("doctor/patients.html",patients=patients)

    @app.route("/doctor/patient/<int:pid>")
    @role_required("doctor")
    def doctor_patient(pid):
        # Use explicit queries so a missing optional relationship can never break the case page.
        p=PatientProfile.query.get_or_404(pid)
        plans=RecoveryPlan.query.filter_by(patient_id=pid,doctor_id=current_user.id).order_by(RecoveryPlan.created_at.desc()).all()
        if not plans: abort(403)
        surgery=Surgery.query.filter_by(patient_id=pid).order_by(Surgery.surgery_date.desc()).first()
        escalations=Escalation.query.filter_by(patient_id=pid,doctor_id=current_user.id).order_by(Escalation.created_at.desc()).all()
        events=TimelineEvent.query.filter_by(patient_id=pid).order_by(TimelineEvent.created_at.desc()).all()
        tasks=RecoveryTask.query.filter_by(patient_id=pid).order_by(RecoveryTask.due_date.asc()).all()
        appointments=Appointment.query.filter_by(patient_id=pid).order_by(Appointment.date_time.asc()).all()
        monitor=detect_recovery_deviation_service(p)
        return render_template("doctor/patient.html",patient=p,plan=plans[0],surgery=surgery,monitor=monitor,
                               escalations=escalations,events=events,tasks=tasks,appointments=appointments)

    @app.route("/doctor/escalations", methods=["GET","POST"])
    @role_required("doctor")
    def doctor_escalations():
        escalations=Escalation.query.filter_by(doctor_id=current_user.id).order_by(Escalation.created_at.desc()).all()
        return render_template("doctor/escalations.html",escalations=escalations,decision_form=DecisionForm())

    @app.route("/doctor/escalation/<int:eid>/decision", methods=["POST"])
    @role_required("doctor")
    def doctor_decision(eid):
        e=Escalation.query.filter_by(id=eid,doctor_id=current_user.id).first_or_404()
        form=DecisionForm()
        if form.validate_on_submit():
            db.session.add(DoctorDecision(escalation_id=e.id,doctor_id=current_user.id,
                                          decision_note=form.decision_note.data,action=form.action.data))
            e.status="Resolved" if form.action.data=="Resolve" else "Reviewed"
            e.resolved_at=datetime.utcnow() if e.status=="Resolved" else None
            log_event(e.patient_id,"Doctor decision","Doctor decision recorded",form.decision_note.data[:300])
            db.session.commit(); flash("Doctor decision recorded and added to the timeline.","success")
        return redirect(url_for("doctor_escalations"))

    @app.route("/doctor/recovery-monitor")
    @role_required("doctor")
    def doctor_monitor():
        patients=[x for x in PatientProfile.query.all() if any(p.doctor_id==current_user.id for p in x.recovery_plans)]
        rows=[(p,detect_recovery_deviation_service(p)) for p in patients]
        return render_template("doctor/monitor.html",rows=rows)

    @app.route("/doctor/continuity", methods=["GET", "POST"])
    @role_required("doctor")
    def doctor_continuity():
        patients = [x for x in PatientProfile.query.all() if any(p.doctor_id == current_user.id for p in x.recovery_plans)]
        patient_ids = [p.id for p in patients]
        concerns = PatientConcern.query.filter(PatientConcern.patient_id.in_(patient_ids)).order_by(PatientConcern.created_at.desc()).all() if patient_ids else []
        if request.method == "POST":
            concern = PatientConcern.query.filter(PatientConcern.id == request.form.get("concern_id"), PatientConcern.patient_id.in_(patient_ids)).first_or_404()
            workflow = ConcernWorkflow.query.filter_by(concern_id=concern.id).first()
            if workflow is None:
                workflow = ConcernWorkflow(concern_id=concern.id)
                db.session.add(workflow)
            owner_raw = (request.form.get("owner_id") or "").strip()
            owner = User.query.filter_by(id=owner_raw, role="care_team").first() if owner_raw else None
            workflow.owner_id = owner.id if owner else None
            deadline_raw = (request.form.get("deadline") or "").strip()
            try:
                workflow.deadline = datetime.strptime(deadline_raw, "%Y-%m-%dT%H:%M") if deadline_raw else None
            except ValueError:
                flash("Please enter a valid deadline.", "danger")
                return redirect(url_for("doctor_continuity"))
            action = request.form.get("workflow_action", "save")
            if action == "acknowledge":
                workflow.acknowledged_at = datetime.utcnow()
                workflow.status = "Acknowledged"
                log_title = f"Concern #{concern.id} acknowledged"
                log_description = f"Acknowledged by {current_user.name}. Current owner: {owner.name if owner else 'Unassigned'}"
            elif action == "resolve":
                note = (request.form.get("resolution_notes") or "").strip()
                if not note:
                    flash("Add a resolution note before marking this concern resolved.", "danger")
                    return redirect(url_for("doctor_continuity"))
                workflow.status = "Resolved"
                workflow.resolved_at = datetime.utcnow()
                workflow.resolution_notes = note[:1000]
                concern.status = "Resolved"
                log_title = f"Concern #{concern.id} resolved"
                log_description = f"Resolved by {current_user.name}. Outcome: {workflow.resolution_notes}"
            elif action == "escalate":
                existing = Escalation.query.filter_by(concern_id=concern.id, status="Open").first()
                if existing:
                    flash("This concern already has an open escalation.", "warning")
                    return redirect(url_for("doctor_continuity"))
                reason = (request.form.get("escalation_reason") or "Care gap flagged for clinician follow-up.").strip()
                db.session.add(Escalation(patient_id=concern.patient_id, concern_id=concern.id,
                                          created_by=current_user.id, doctor_id=current_user.id,
                                          level="YELLOW", reason=reason[:1000], status="Open"))
                workflow.status = "Escalated"
                log_title = f"Concern #{concern.id} escalated"
                log_description = f"Escalation created by {current_user.name}: {reason[:500]}"
            else:
                workflow.status = "Assigned" if workflow.owner_id else "Open"
                concern.status = "Under review" if workflow.owner_id else concern.status
                log_title = f"Concern #{concern.id} workflow updated"
                log_description = f"Status: {workflow.status}; owner: {owner.name if owner else 'Unassigned'}; deadline: {workflow.deadline or 'Not set'}"
            log_event(concern.patient_id, "Concern workflow", log_title, log_description)
            db.session.commit()
            flash("Concern workflow saved.", "success")
            return redirect(url_for("doctor_continuity"))
        team = User.query.filter_by(role="care_team").order_by(User.name.asc()).all()
        workflows = {w.concern_id: w for w in ConcernWorkflow.query.filter(ConcernWorkflow.concern_id.in_([c.id for c in concerns])).all()} if concerns else {}
        now = datetime.utcnow()
        gaps = []
        gap_reasons = {}
        for c in concerns:
            w = workflows.get(c.id)
            if c.status == "Resolved" or (w and w.status == "Resolved"):
                continue
            reasons = []
            owner_is_valid = bool(w and w.owner_id and User.query.filter_by(id=w.owner_id, role="care_team").first())
            if not owner_is_valid:
                reasons.append("No owner assigned")
            if w and w.deadline and w.deadline < now:
                reasons.append("Deadline overdue")
            if reasons:
                gaps.append(c)
                gap_reasons[c.id] = reasons
        events = TimelineEvent.query.filter(TimelineEvent.patient_id.in_(patient_ids)).order_by(TimelineEvent.created_at.desc()).limit(100).all() if patient_ids else []
        return render_template("doctor/continuity.html", concerns=concerns, workflows=workflows, team=team, gaps=gaps, gap_reasons=gap_reasons, events=events, now=now)

    @app.route("/doctor/care-team")
    @role_required("doctor")
    def doctor_care_team():
        patients=[x for x in PatientProfile.query.all() if any(p.doctor_id==current_user.id for p in x.recovery_plans)]
        team=User.query.filter_by(role="care_team").all()
        assignments=CareTeamAssignment.query.filter(CareTeamAssignment.patient_id.in_([p.id for p in patients])).all() if patients else []
        return render_template("doctor/care_team.html",patients=patients,team=team,assignments=assignments)

    @app.route("/doctor/appointments")
    @role_required("doctor")
    def doctor_appointments():
        appts=Appointment.query.filter_by(doctor_id=current_user.id).order_by(Appointment.date_time).all()
        return render_template("doctor/appointments.html",appointments=appts)

    @app.route("/admin/dashboard")
    @role_required("admin")
    def admin_dashboard():
        return render_template("admin/dashboard.html",users=User.query.all(),patients=PatientProfile.query.all(),
                               escalations=Escalation.query.filter_by(status="Open").all())

    @app.route("/admin/users")
    @role_required("admin")
    def admin_users():
        return render_template("admin/users.html",users=User.query.order_by(User.created_at.desc()).all())

    @app.errorhandler(403)
    def forbidden(e): return render_template("errors/403.html"),403
    @app.errorhandler(404)
    def not_found(e): return render_template("errors/404.html"),404
    @app.errorhandler(413)
    def too_large(e): return render_template("errors/413.html"),413
    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"),500

    return app

app=create_app()
if __name__=="__main__":
    with app.app_context():
        db.create_all()
    app.run(host="127.0.0.1",port=5000,debug=False)
