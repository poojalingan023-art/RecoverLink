from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash
from app import create_app
from models import *
app=create_app(); PASSWORD="RecoverLink@123"
with app.app_context():
    db.drop_all(); db.create_all()
    def user(name,email,role,professional_role=None):
        u=User(name=name,email=email,password_hash=generate_password_hash(PASSWORD),role=role,professional_role=professional_role); db.session.add(u); db.session.flush(); return u
    doctor=user("Dr. Meera Shah","doctor@example.com","doctor","Orthopaedic Doctor")
    nurse=user("Priya Nair","nurse@example.com","care_team","Nurse")
    physio=user("Kumar Ravi","physio@example.com","care_team","Physiotherapist")
    admin=user("Hospital Admin","admin@example.com","admin","Hospital Operations")
    cases=[
      ("Arun Kumar","patient@example.com","Knee Replacement","Knee replacement recovery","GREEN",[6,5,4,3],"Stable recovery; tasks progressing normally."),
      ("Meena Raj","meena@example.com","Gallbladder Surgery","Laparoscopic gallbladder recovery","YELLOW",[6,5,6,7],"Pain trend increased; professional review recommended."),
      ("Rahul S","rahul@example.com","Hernia Repair","Hernia repair recovery","RED",[5,5,6,8],"New recovery concern submitted with a photo; professional review required."),
    ]
    for idx,(name,email,surgery_name,plan_title,level,pains,summary) in enumerate(cases):
        pu=user(name,email,"patient")
        phones=["+91 98765 43210","+91 91234 56780","+91 99887 66554"]
        emergencies=["Anita Kumar · +91 98765 43211","Ravi Raj · +91 91234 56781","Suresh S · +91 99887 66555"]
        pp=PatientProfile(user_id=pu.id,date_of_birth=f"200{idx+1}-04-12",contact_information=f"{phones[idx]} · {email}",phone_number=phones[idx],emergency_contact=emergencies[idx])
        db.session.add(pp); db.session.flush()
        surg=Surgery(patient_id=pp.id,surgery_type=surgery_name,surgery_date=date.today()-timedelta(days=7+idx),discharge_date=date.today()-timedelta(days=5+idx),hospital="RecoverLink Demo Hospital",surgeon="Dr. Meera Shah",notes="Hackathon demo recovery pathway.")
        db.session.add(surg)
        plan=RecoveryPlan(patient_id=pp.id,doctor_id=doctor.id,title=plan_title,instructions="Follow the doctor-approved recovery plan and contact the assigned care team for concerns.");db.session.add(plan);db.session.flush()
        for day,val in [("Day 1","6/10"),("Day 3","4/10"),("Day 5","3/10"),("Day 7","2/10")]: db.session.add(RecoveryMilestone(recovery_plan_id=plan.id,day_week=day,indicator="Pain",expected_value=val,notes="Demo expected downward recovery pathway."))
        db.session.add_all([CareTeamAssignment(patient_id=pp.id,care_team_user_id=nurse.id,assigned_by=doctor.id,role="Nurse",start_date=date.today()-timedelta(days=7)),CareTeamAssignment(patient_id=pp.id,care_team_user_id=physio.id,assigned_by=doctor.id,role="Physiotherapist",start_date=date.today()-timedelta(days=7))])
        db.session.add_all([Medication(patient_id=pp.id,prescribed_by=doctor.id,name="Doctor-prescribed recovery medicine",dosage="As prescribed",frequency="As directed",start_date=date.today()-timedelta(days=5),end_date=date.today()+timedelta(days=2),instructions="Follow the doctor's prescription exactly."),RecoveryTask(patient_id=pp.id,created_by=doctor.id,title="Complete recovery exercises",description="Complete today's exercises from your approved recovery plan.",frequency="Daily",due_date=date.today(),status="Completed" if idx==0 else "Pending"),RecoveryTask(patient_id=pp.id,created_by=doctor.id,title="Recovery check-in",description="Record your pain level and note any new recovery concern.",frequency="Daily",due_date=date.today(),status="Pending"),RecoveryTask(patient_id=pp.id,created_by=doctor.id,title="Recovery walk / mobility",description="Follow the mobility activity in your approved plan.",frequency="Daily",due_date=date.today(),status="Pending")])
        for n,pain in enumerate(pains): db.session.add(RecoveryObservation(patient_id=pp.id,recorded_by=pu.id,indicator="Pain",value=pain,unit="/10",recorded_at=datetime.combine(date.today()-timedelta(days=7-n*2),datetime.min.time())))
        db.session.add(Appointment(patient_id=pp.id,doctor_id=doctor.id,date_time=datetime.now()+timedelta(days=2+idx),purpose="Post-surgery recovery review",status="Scheduled"))
        db.session.add(TreatmentSchedule(patient_id=pp.id,scheduled_for=datetime.now()+timedelta(days=1+idx),title="Physiotherapy / recovery review",details="Next scheduled recovery activity under the approved plan.",status="Scheduled"))
        for et,title,desc in [("Surgery","Surgery completed",f"{surgery_name} pathway started."),("Discharge","Discharged home","Doctor-approved recovery plan activated."),("Task","Recovery tasks assigned","Daily recovery checklist is available.")]: db.session.add(TimelineEvent(patient_id=pp.id,event_type=et,title=title,description=desc,created_by=doctor.id))
        if idx>0:
            concern=PatientConcern(patient_id=pp.id,category="Pain / Recovery" if idx==1 else "Wound / Recovery",text=summary,priority=level,status="New" if idx==2 else "Escalated");db.session.add(concern);db.session.flush()
            if idx==1:
                db.session.add(CareTeamNote(patient_id=pp.id,care_team_user_id=nurse.id,concern_id=concern.id,note="Reviewed pain trend against the expected pathway. Professional review requested."));db.session.add(Escalation(patient_id=pp.id,concern_id=concern.id,created_by=nurse.id,doctor_id=doctor.id,level="YELLOW",reason="Pain trend increased compared with the expected recovery pathway.",status="Open"))
            if idx==1:
                # Demo care gap: assigned but deadline deliberately in the past.
                db.session.add(ConcernWorkflow(concern_id=concern.id, owner_id=nurse.id,
                    deadline=datetime.now()-timedelta(hours=3), status="Escalated"))
            if idx==2:
                # Demo care gap: no owner assigned, so it remains visible until ownership is saved.
                db.session.add(ConcernWorkflow(concern_id=concern.id, owner_id=None,
                    deadline=datetime.now()+timedelta(days=1), status="Open"))
                db.session.add(WoundPhoto(patient_id=pp.id,file_path="",patient_note="Demo photo placeholder; patient can attach a real recovery photo.",ai_flag=False,ai_explanation="Photo is for professional review only."))
                db.session.add(CareTeamNote(patient_id=pp.id,care_team_user_id=nurse.id,concern_id=concern.id,note="New concern received. Review the patient context and any attached recovery photo."))
    db.session.commit();print("RecoverLink 2.0 demo database seeded.");print("Demo password for all accounts:",PASSWORD);print("Patients: patient@example.com, meena@example.com, rahul@example.com")
