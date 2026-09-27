import hashlib
import json
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Jsonb

from . import storage
from .auth import Identity, context, identity, require
from .config import settings
from .db import all_rows, close_pool, one, open_pool, transaction
from .images import validate_image
from .limits import UploadLimit
from .schemas import AssignmentIn, AvailabilityIn, InviteIn, MemberUpdate, OrganizationIn, PatientIn, ReviewIn
from .workflow import assign_doctor, transition


@asynccontextmanager
async def lifespan(app):
    await open_pool()
    yield
    await close_pool()


app = FastAPI(title="Dr.Retina Clinical API", version="1.0.0", lifespan=lifespan)
app.add_middleware(UploadLimit)


@app.middleware("http")
async def privacy_headers(request, call_next):
    # The reverse proxy must also cap request bodies before multipart parsing.
    size = request.headers.get("content-length", "")
    if size.isdigit() and int(size) > 27 * 1024 * 1024:
        return JSONResponse({"message": "Upload is too large"}, status_code=413)
    response = await call_next(request)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse({"message": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def input_error(request, exc):
    # Never echo submitted passwords, tokens, or clinical data in validation errors.
    return JSONResponse({"message": "Invalid request fields"}, status_code=422)


@app.exception_handler(UniqueViolation)
async def duplicate_error(request, exc):
    return JSONResponse({"message": "This record already exists"}, status_code=409)


@app.exception_handler(ForeignKeyViolation)
async def reference_error(request, exc):
    return JSONResponse({"message": "Related record is unavailable"}, status_code=409)


async def audit(conn, member, action, resource=None):
    await conn.execute(
        """insert into retina.audit_events(org_id,actor_id,action,resource_id)
                          values(%s,%s,%s,%s)""",
        (member["org_id"], member["user_id"], action, resource),
    )


async def screening_row(conn, sid, lock=False):
    row = await one(
        conn, "select * from retina.screenings where id=%s" + (" for update" if lock else ""), (sid,)
    )
    if not row:
        raise HTTPException(404, "Screening not found")
    return row


def patient_out(row):
    return {
        "id": row["id"],
        "mrn": row["mrn"],
        "fullName": row["full_name"],
        "age": row["age"],
        "gender": row["gender"],
        "campLocation": row["camp_location"],
        "createdAt": row["created_at"],
        "knownDiabetic": row["known_diabetic"],
        "diabetesDurationYears": row["diabetes_duration_years"],
        "clinicalHistory": row["clinical_history"],
    }


async def idempotent(conn, member, key, operation, fingerprint):
    await conn.execute(
        "select pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"{member['org_id']}:{member['user_id']}:{key}:{operation}",),
    )
    record = await one(
        conn,
        """select * from retina.idempotency
        where org_id=%s and user_id=%s and key=%s and operation=%s""",
        (member["org_id"], member["user_id"], key, operation),
    )
    if record and record["fingerprint"] != fingerprint:
        raise HTTPException(409, "Idempotency key was already used for different content")
    return record["response"] if record else None


async def remember(conn, member, key, operation, fingerprint, response):
    serializable = json.loads(json.dumps(response, default=str))
    await conn.execute(
        """insert into retina.idempotency(org_id,user_id,key,operation,fingerprint,response)
        values(%s,%s,%s,%s,%s,%s)""",
        (member["org_id"], member["user_id"], key, operation, fingerprint, Jsonb(serializable)),
    )
    return serializable


@app.get("/health/live")
async def live():
    return {"status": "up"}


@app.get("/health/ready")
async def ready():
    async with transaction() as conn:
        await conn.execute("select 1")
    return {"status": "ready"}


@app.get("/api/v1/me")
async def me(ctx=Depends(context)):
    conn, member, who = ctx
    org = await one(conn, "select name from retina.organizations where id=%s", (member["org_id"],))
    return {
        "userId": who.user_id,
        "email": who.email,
        "role": member["role"],
        "orgId": member["org_id"],
        "orgName": org["name"],
    }


@app.post("/api/v1/organizations", status_code=201)
async def onboard(payload: OrganizationIn, who: Identity = Depends(identity)):
    async with transaction(who.user_id, who.session_id) as conn:
        await conn.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (str(who.user_id),))
        if await one(conn, "select user_id from retina.members where user_id=%s", (who.user_id,)):
            raise HTTPException(409, "Account already belongs to an organization")
        org = await one(
            conn,
            """insert into retina.organizations
          (name,type,address,contact_email,contact_phone,identifier,created_by)
          values(%s,%s,%s,%s,%s,%s,%s) returning *""",
            (
                payload.name,
                payload.type,
                payload.address,
                str(payload.contactEmail),
                payload.contactPhone,
                payload.identifier,
                who.user_id,
            ),
        )
        await conn.execute(
            """insert into retina.members(user_id,org_id,email,full_name,role)
          values(%s,%s,%s,%s,'ORG_ADMIN')""",
            (who.user_id, org["id"], who.email, who.email),
        )
        await audit(conn, {"org_id": org["id"], "user_id": who.user_id}, "ORGANIZATION_CREATED", org["id"])
        return {"data": org}


@app.get("/api/v1/organizations")
async def organizations(ctx=Depends(context)):
    conn, member, _ = ctx
    rows = await all_rows(conn, "select id,name,type,address as location from retina.organizations")
    return {"data": rows}


@app.get("/api/v1/organization")
async def organization(ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "ORG_ADMIN")
    return {"data": await one(conn, "select * from retina.organizations where id=%s", (member["org_id"],))}


@app.patch("/api/v1/organization")
async def update_org(payload: OrganizationIn, ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "ORG_ADMIN")
    await conn.execute(
        """update retina.organizations set name=%s,type=%s,address=%s,contact_email=%s,
      contact_phone=%s,identifier=%s where id=%s""",
        (
            payload.name,
            payload.type,
            payload.address,
            str(payload.contactEmail),
            payload.contactPhone,
            payload.identifier,
            member["org_id"],
        ),
    )
    await audit(conn, member, "ORGANIZATION_UPDATED", member["org_id"])
    return {"ok": True}


@app.get("/api/v1/users")
async def users(ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "ORG_ADMIN")
    return {"data": await all_rows(conn, "select * from retina.members order by full_name")}


@app.post("/api/v1/users/invite", status_code=201)
async def invite(payload: InviteIn, ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "ORG_ADMIN")
    cfg = settings()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{cfg.supabase_url}/auth/v1/invite",
            params={"redirect_to": f"{cfg.app_url}/auth/callback?next=/account/password"},
            headers={
                "apikey": cfg.supabase_service_role_key.get_secret_value(),
                "Authorization": f"Bearer {cfg.supabase_service_role_key.get_secret_value()}",
            },
            json={"email": str(payload.email)},
        )
    if response.is_error:
        raise HTTPException(409, "Invitation could not be created; check whether this account already exists")
    uid = UUID(response.json()["id"])
    await conn.execute(
        """insert into retina.members(user_id,org_id,email,full_name,role)
      values(%s,%s,%s,%s,%s)""",
        (uid, member["org_id"], str(payload.email), payload.fullName, payload.role),
    )
    await audit(conn, member, "USER_INVITED", uid)
    return {"ok": True}


@app.patch("/api/v1/users/{uid}")
async def update_user(uid: UUID, payload: MemberUpdate, ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "ORG_ADMIN")
    target = await one(conn, "select * from retina.members where user_id=%s for update", (uid,))
    if not target or target["role"] == "ORG_ADMIN":
        raise HTTPException(404, "Managed user not found")
    if target["role"] == "DOCTOR" and (not payload.active or payload.role != "DOCTOR"):
        cases = await all_rows(
            conn,
            """select * from retina.screenings where assigned_doctor_id=%s
           and status in ('SENT_TO_DOCTOR','DOCTOR_REVIEWING') for update""",
            (uid,),
        )
        for case in cases:
            # Administrative unassignment is recorded; AI and reviews remain untouched.
            await conn.execute(
                """update retina.screenings set assigned_doctor_id=null,
              assigned_at=null,assignment_status='QUEUED' where id=%s""",
                (case["id"],),
            )
    await conn.execute(
        "update retina.members set active=%s,role=%s,available=%s where user_id=%s",
        (payload.active, payload.role, payload.available, uid),
    )
    await audit(conn, member, "USER_ACCESS_UPDATED", uid)
    return {"ok": True}


@app.post("/api/v1/users/{uid}/reset-password")
async def reset_user(uid: UUID, ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "ORG_ADMIN")
    target = await one(
        conn, "select email from retina.members where user_id=%s and role<>'ORG_ADMIN'", (uid,)
    )
    if not target:
        raise HTTPException(404, "Managed user not found")
    cfg = settings()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{cfg.supabase_url}/auth/v1/recover",
            params={"redirect_to": f"{cfg.app_url}/auth/callback?next=/account/password"},
            headers={"apikey": cfg.supabase_publishable_key},
            json={"email": target["email"]},
        )
    if response.is_error:
        raise HTTPException(503, "Password recovery is unavailable")
    await audit(conn, member, "PASSWORD_RECOVERY_REQUESTED", uid)
    return {"ok": True}


@app.patch("/api/v1/me/availability")
async def availability(payload: AvailabilityIn, ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "DOCTOR")
    await conn.execute(
        "update retina.members set available=%s where user_id=%s", (payload.available, member["user_id"])
    )
    return {"ok": True}


@app.get("/api/v1/patients")
async def patients(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str = Query("", max_length=120),
    ctx=Depends(context),
):
    conn, _, _ = ctx
    rows = await all_rows(
        conn,
        """select * from retina.patients where full_name ilike %s or mrn ilike %s
      order by created_at desc limit %s offset %s""",
        (f"%{q}%", f"%{q}%", limit, offset),
    )
    return {"data": [patient_out(r) for r in rows]}


@app.post("/api/v1/patients", status_code=201)
async def create_patient(payload: PatientIn, idempotency_key: UUID = Header(), ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "LAB_TECHNICIAN")
    fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    cached = await idempotent(conn, member, idempotency_key, "patient", fingerprint)
    if cached:
        return cached
    uid = uuid4()
    row = await one(
        conn,
        """insert into retina.patients(id,org_id,mrn,full_name,age,gender,
      contact_number,diabetes_duration_years,known_diabetic,camp_location,date_of_birth,address,
      clinical_history,registered_by) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *""",
        (
            uid,
            member["org_id"],
            f"DR-{uid.hex[:12].upper()}",
            payload.fullName,
            payload.age,
            payload.gender,
            payload.contactNumber,
            payload.diabetesDurationYears,
            payload.knownDiabetic,
            payload.campLocation,
            payload.dateOfBirth,
            payload.address,
            payload.clinicalHistory,
            member["user_id"],
        ),
    )
    await audit(conn, member, "PATIENT_REGISTERED", uid)
    return await remember(conn, member, idempotency_key, "patient", fingerprint, {"data": patient_out(row)})


@app.get("/api/v1/patients/{pid}/history")
async def history(
    pid: UUID, limit: int = Query(200, ge=1, le=200), offset: int = Query(0, ge=0), ctx=Depends(context)
):
    conn, member, _ = ctx
    patient = await one(conn, "select * from retina.patients where id=%s", (pid,))
    if not patient:
        raise HTTPException(404, "Patient not found")
    await audit(conn, member, "PATIENT_HISTORY_VIEWED", pid)
    return {
        "patient": patient_out(patient),
        "screenings": await list_screenings(conn, limit, offset, patient_id=pid),
    }


@app.post("/api/v1/screenings/analyze", status_code=202)
async def analyze(
    patientId: UUID = Form(),
    eye: str = Form(),
    image: UploadFile = File(),
    parentScreeningId: UUID | None = Form(None),
    idempotency_key: UUID = Header(),
    ctx=Depends(context),
):
    conn, member, _ = ctx
    require(member, "LAB_TECHNICIAN")
    if eye not in ("OD", "OS"):
        raise HTTPException(422, "Choose one eye per image")
    patient = await one(conn, "select id from retina.patients where id=%s", (patientId,))
    if not patient:
        raise HTTPException(404, "Patient not found")
    if parentScreeningId:
        parent = await screening_row(conn, parentScreeningId, True)
        if parent["patient_id"] != patientId or parent["status"] not in (
            "QUALITY_REJECTED",
            "ADDITIONAL_ANALYSIS_REQUIRED",
        ):
            raise HTTPException(409, "This screening is not eligible for repeat acquisition")
    data = await image.read(settings().max_upload_bytes + 1)
    if len(data) > settings().max_upload_bytes:
        raise HTTPException(413, "Image exceeds 25 MB")
    mime, width, height = validate_image(data)
    digest = hashlib.sha256(data).hexdigest()
    fingerprint = f"{patientId}:{eye}:{parentScreeningId}:{digest}"
    cached = await idempotent(conn, member, idempotency_key, "screening", fingerprint)
    if cached:
        return cached
    sid = uuid4()
    path = f"{member['org_id']}/{sid}/{uuid4()}.{'jpg' if mime == 'image/jpeg' else 'png'}"
    # Unique path, no upsert, and no delete: the original remains preserved.
    await storage.upload(path, data, mime)
    row = await one(
        conn,
        """insert into retina.screenings(id,org_id,patient_id,created_by,eye,parent_screening_id)
        values(%s,%s,%s,%s,%s,%s) returning *""",
        (sid, member["org_id"], patientId, member["user_id"], eye, parentScreeningId),
    )
    await conn.execute(
        """insert into retina.images(org_id,screening_id,object_path,sha256,mime,width,height)
        values(%s,%s,%s,%s,%s,%s,%s)""",
        (member["org_id"], sid, path, digest, mime, width, height),
    )
    await transition(conn, row, "IMAGE_UPLOADED", member["user_id"])
    job = await one(
        conn,
        "insert into retina.jobs(org_id,screening_id) values(%s,%s) returning id",
        (member["org_id"], sid),
    )
    await audit(conn, member, "SCREENING_SUBMITTED", sid)
    return await remember(
        conn,
        member,
        idempotency_key,
        "screening",
        fingerprint,
        {"jobId": job["id"], "screeningId": sid, "status": "QUEUED"},
    )


async def list_screenings(conn, limit=100, offset=0, patient_id=None, doctor_id=None, statuses=None):
    rows = await all_rows(
        conn,
        """select s.*,p.full_name,p.mrn,p.age,p.gender,p.camp_location,
      a.severity,a.confidence,a.findings,r.decision,r.comments,r.reason,r.final_assessment
      from retina.screenings s join retina.patients p on p.id=s.patient_id
      left join retina.ai_results a on a.screening_id=s.id
      left join retina.reviews r on r.screening_id=s.id
      where (%s::uuid is null or s.patient_id=%s)
      and (%s::uuid is null or s.assigned_doctor_id=%s)
      and (%s::text[] is null or s.status::text=any(%s::text[]))
      order by s.created_at desc limit %s offset %s""",
        (patient_id, patient_id, doctor_id, doctor_id, statuses, statuses, limit, offset),
    )
    return [
        {
            "id": r["id"],
            "patientId": r["patient_id"],
            "patientName": r["full_name"],
            "fullName": r["full_name"],
            "mrn": r["mrn"],
            "age": r["age"],
            "gender": r["gender"],
            "campLocation": r["camp_location"],
            "eye": r["eye"],
            "aiSeverity": r["severity"],
            "severity": r["severity"] or "Not yet available",
            "aiConfidence": float(r["confidence"]) * 100 if r["confidence"] is not None else None,
            "status": r["status"],
            "assignedDoctorId": r["assigned_doctor_id"],
            "assignmentStatus": r["assignment_status"],
            "createdAt": r["created_at"],
            "screeningDate": r["created_at"],
            "time": r["created_at"],
            "findings": r["findings"] or [],
            "dmeRisk": "Not assessed",
            "priorityStatus": "High Priority"
            if r["severity"] in ("Severe NPDR", "Proliferative DR")
            else "Moderate"
            if r["severity"] == "Moderate NPDR"
            else "Routine",
            "reviewerVerdict": r["decision"],
            "reviewComments": r["comments"],
            "reviewReason": r["reason"],
            "finalAssessment": r["final_assessment"],
        }
        for r in rows
    ]


@app.get("/api/v1/screenings")
async def screenings(
    limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0), ctx=Depends(context)
):
    return {"data": await list_screenings(ctx[0], limit, offset)}


@app.get("/api/v1/doctor/patients")
async def doctor_queue(tab: str = "recent", ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "DOCTOR")
    statuses = None
    if tab == "followups":
        statuses = ["ADDITIONAL_ANALYSIS_REQUIRED"]
    elif tab != "recent":
        statuses = ["SENT_TO_DOCTOR", "DOCTOR_REVIEWING"]
    rows = await list_screenings(conn, 200, doctor_id=member["user_id"], statuses=statuses)
    return {"data": rows}


@app.get("/api/v1/screenings/jobs/{jid}")
async def job_status(jid: UUID, ctx=Depends(context)):
    conn, _, _ = ctx
    row = await one(conn, "select * from retina.jobs where id=%s", (jid,))
    if not row:
        raise HTTPException(404, "Job not found")
    screen = await screening_row(conn, row["screening_id"])
    return {
        "jobId": jid,
        "screeningId": row["screening_id"],
        "status": {"QUEUED": "QUEUED", "RUNNING": "PROCESSING", "DONE": "COMPLETED", "FAILED": "FAILED"}[
            row["state"]
        ],
        "screeningStatus": screen["status"],
        "errorCode": row["error_code"],
    }


@app.get("/api/v1/screenings/{sid}")
async def screening_detail(sid: UUID, ctx=Depends(context)):
    conn, member, _ = ctx
    screen = await screening_row(conn, sid)
    patient = await one(conn, "select * from retina.patients where id=%s", (screen["patient_id"],))
    ai = await one(conn, "select * from retina.ai_results where screening_id=%s", (sid,))
    if ai:
        ai.pop("explainability_path", None)
    quality = await one(conn, "select * from retina.quality_results where screening_id=%s", (sid,))
    review = await one(conn, "select * from retina.reviews where screening_id=%s", (sid,))
    events = await all_rows(
        conn,
        "select status,created_at from retina.screening_events where screening_id=%s order by created_at",
        (sid,),
    )
    await audit(conn, member, "SCREENING_VIEWED", sid)
    return {
        "screening": screen,
        "patient": patient_out(patient),
        "ai": ai,
        "quality": quality,
        "review": review,
        "events": events,
    }


@app.get("/api/v1/screenings/{sid}/image")
async def image_bytes(sid: UUID, kind: str = "original", ctx=Depends(context)):
    conn, member, _ = ctx
    await screening_row(conn, sid)
    if kind == "original":
        row = await one(
            conn, "select object_path as path,mime from retina.images where screening_id=%s", (sid,)
        )
    elif kind == "explainability":
        row = await one(
            conn,
            "select explainability_path as path,'image/png' as mime from retina.ai_results where screening_id=%s",
            (sid,),
        )
    else:
        raise HTTPException(422, "Unknown image kind")
    if not row or not row["path"]:
        raise HTTPException(404, "Image unavailable")
    await audit(conn, member, "IMAGE_VIEWED", sid)
    return Response(await storage.download(row["path"]), media_type=row["mime"])


@app.post("/api/v1/screenings/{sid}/start-review")
async def start_review(sid: UUID, ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "DOCTOR")
    row = await screening_row(conn, sid, True)
    if row["assigned_doctor_id"] != member["user_id"]:
        raise HTTPException(403, "This report is not assigned to you")
    if row["status"] == "SENT_TO_DOCTOR":
        await transition(conn, row, "DOCTOR_REVIEWING", member["user_id"])
    elif row["status"] != "DOCTOR_REVIEWING":
        raise HTTPException(409, "Report is not available for review")
    return {"ok": True}


@app.post("/api/v1/screenings/{sid}/reviews")
async def review(sid: UUID, payload: ReviewIn, idempotency_key: UUID = Header(), ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "DOCTOR")
    fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    cached = await idempotent(conn, member, idempotency_key, f"review:{sid}", fingerprint)
    if cached:
        return cached
    row = await screening_row(conn, sid, True)
    if row["assigned_doctor_id"] != member["user_id"]:
        raise HTTPException(403, "This report is not assigned to you")
    if row["status"] != "DOCTOR_REVIEWING":
        raise HTTPException(409, "Start reviewing this report first")
    if not await one(conn, "select id from retina.ai_results where screening_id=%s", (sid,)):
        raise HTTPException(409, "AI report is not ready")
    await conn.execute(
        """insert into retina.reviews(org_id,screening_id,doctor_id,decision,final_assessment,comments,reason)
       values(%s,%s,%s,%s,%s,%s,%s)""",
        (
            member["org_id"],
            sid,
            member["user_id"],
            payload.decision,
            payload.finalAssessment,
            payload.comments,
            payload.reason,
        ),
    )
    await transition(conn, row, payload.decision, member["user_id"])
    if payload.decision == "ADDITIONAL_ANALYSIS_REQUIRED":
        await conn.execute(
            """insert into retina.notifications(org_id,user_id,screening_id,message)
          values(%s,%s,%s,'Additional screening has been requested by the doctor')""",
            (member["org_id"], row["created_by"], sid),
        )
    await audit(conn, member, payload.decision, sid)
    return await remember(conn, member, idempotency_key, f"review:{sid}", fingerprint, {"ok": True})


@app.post("/api/v1/screenings/{sid}/complete")
async def complete(sid: UUID, ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "DOCTOR")
    row = await screening_row(conn, sid, True)
    if row["assigned_doctor_id"] != member["user_id"]:
        raise HTTPException(403, "Not your assigned report")
    await transition(conn, row, "COMPLETED", member["user_id"])
    await audit(conn, member, "REPORT_COMPLETED", sid)
    return {"ok": True}


@app.post("/api/v1/screenings/{sid}/assign")
async def reassign(sid: UUID, payload: AssignmentIn, ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "ORG_ADMIN")
    row = await screening_row(conn, sid, True)
    if row["status"] not in ("REPORT_READY", "SENT_TO_DOCTOR", "DOCTOR_REVIEWING"):
        raise HTTPException(409, "Only reports awaiting a final decision can be reassigned")
    await assign_doctor(conn, row, payload.doctorId)
    await audit(conn, member, "DOCTOR_ASSIGNED", sid)
    return {"ok": True}


@app.get("/api/v1/notifications")
async def notifications(ctx=Depends(context)):
    conn, member, _ = ctx
    return {
        "data": await all_rows(
            conn,
            """select id,screening_id,message,created_at,read_at from retina.notifications
       where user_id=%s order by created_at desc limit 100""",
            (member["user_id"],),
        )
    }


@app.get("/api/v1/analytics/dashboard")
async def stats(ctx=Depends(context)):
    conn, member, _ = ctx
    p = await one(conn, "select count(*) as count from retina.patients")
    counts = await one(
        conn,
        """select count(*) as total,
       count(*) filter(where created_at::date=current_date) as today,
       count(*) filter(where status in ('IMAGE_UPLOADED','QUALITY_CHECKING','READY_FOR_ANALYSIS','AI_PROCESSING')) as pending,
       count(*) filter(where status='COMPLETED') as completed,
       count(*) filter(where status in ('SENT_TO_DOCTOR','DOCTOR_REVIEWING')) as review,
       count(*) filter(where status='ADDITIONAL_ANALYSIS_REQUIRED') as additional
       from retina.screenings where (%s<>'DOCTOR' or assigned_doctor_id=%s)""",
        (member["role"], member["user_id"]),
    )
    staff = await one(
        conn,
        """select count(*) filter(where role='DOCTOR' and active) as doctors,
       count(*) filter(where role='LAB_TECHNICIAN' and active) as technicians from retina.members""",
    )
    activity = (
        await all_rows(
            conn,
            """select id,created_at as time,action,actor_id as "user"
       from retina.audit_events order by created_at desc limit 10""",
        )
        if member["role"] == "ORG_ADMIN"
        else []
    )
    severity = await all_rows(conn, "select severity,count(*) as n from retina.ai_results group by severity")
    distribution = {r["severity"]: r["n"] for r in severity}
    volumes = await all_rows(
        conn,
        """select date_trunc('month',created_at) as month,count(*) as n
        from retina.screenings where created_at>=date_trunc('month',now())-interval '5 months'
        group by 1 order by 1""",
    )
    return {
        "data": {
            "totalPatients": p["count"],
            "recentPatientsCount": p["count"],
            "totalScreenings": counts["total"],
            "screenedToday": counts["today"],
            "pendingAnalysis": counts["pending"],
            "completedScreenings": counts["completed"],
            "awaitingReview": counts["review"],
            "additionalAnalysis": counts["additional"],
            "highPriorityCases": distribution.get("Severe NPDR", 0) + distribution.get("Proliferative DR", 0),
            "activeDoctors": staff["doctors"],
            "activeLabTechnicians": staff["technicians"],
            "activeCamps": 0,
            "recentActivity": activity,
            "screeningVolume": [r["n"] for r in volumes],
            "severityDistribution": dict(
                zip(
                    ["noDR", "mildNPDR", "moderateNPDR", "severeNPDR", "proliferativeDR"],
                    [
                        distribution.get(k, 0)
                        for k in ["No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR"]
                    ],
                )
            ),
        }
    }


@app.get("/api/v1/camps")
async def camps(ctx=Depends(context)):
    return {"data": []}


@app.post("/api/v1/screenings/{sid}/retry")
async def retry_job(sid: UUID, ctx=Depends(context)):
    conn, member, _ = ctx
    require(member, "LAB_TECHNICIAN")
    row = await screening_row(conn, sid, True)
    if row["status"] not in ("IMAGE_UPLOADED", "QUALITY_CHECKING", "READY_FOR_ANALYSIS", "AI_PROCESSING"):
        raise HTTPException(409, "This screening cannot be retried")
    job = await one(conn, "select * from retina.jobs where screening_id=%s for update", (sid,))
    if not job or job["state"] != "FAILED":
        raise HTTPException(409, "Analysis is not in a failed state")
    await conn.execute(
        "update retina.jobs set state='QUEUED',attempts=0,error_code=null where id=%s", (job["id"],)
    )
    await audit(conn, member, "ANALYSIS_RETRIED", sid)
    return {"ok": True}
