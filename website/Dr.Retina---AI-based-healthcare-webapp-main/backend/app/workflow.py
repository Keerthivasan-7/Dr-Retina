from fastapi import HTTPException

TRANSITIONS = {
    "PATIENT_REGISTERED": {"IMAGE_UPLOADED"},
    "IMAGE_UPLOADED": {"QUALITY_CHECKING"},
    "QUALITY_CHECKING": {"QUALITY_REJECTED", "READY_FOR_ANALYSIS"},
    "READY_FOR_ANALYSIS": {"AI_PROCESSING"},
    "AI_PROCESSING": {"REPORT_READY"},
    "REPORT_READY": {"SENT_TO_DOCTOR"},
    "SENT_TO_DOCTOR": {"DOCTOR_REVIEWING"},
    "DOCTOR_REVIEWING": {"VERIFIED", "ADDITIONAL_ANALYSIS_REQUIRED"},
    "VERIFIED": {"COMPLETED"},
}


def validate_transition(old, new):
    if new not in TRANSITIONS.get(old, set()):
        raise HTTPException(409, f"Cannot transition from {old} to {new}")


async def transition(conn, screening, new, actor=None):
    validate_transition(screening["status"], new)
    await conn.execute(
        "update retina.screenings set status=%s, updated_at=now() where id=%s", (new, screening["id"])
    )
    await conn.execute(
        """insert into retina.screening_events(org_id, screening_id, actor_id, status)
                         values (%s,%s,%s,%s)""",
        (screening["org_id"], screening["id"], actor, new),
    )
    screening["status"] = new


async def assign_doctor(conn, screening, doctor_id=None):
    # Organization lock serializes assignment counts without exposing other tenants.
    await conn.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (str(screening["org_id"]),))
    doctor = await (
        await conn.execute(
            """
        select m.user_id from retina.members m
        where m.org_id=%s and m.role='DOCTOR' and m.active and m.available
        and (%s::uuid is null or m.user_id=%s)
        order by (select count(*) from retina.screenings s
                  where s.assigned_doctor_id=m.user_id and s.status in ('SENT_TO_DOCTOR','DOCTOR_REVIEWING')),
                  m.user_id limit 1
    """,
            (screening["org_id"], doctor_id, doctor_id),
        )
    ).fetchone()
    if doctor_id and not doctor:
        raise HTTPException(409, "Doctor must be active and available in this organization")
    if not doctor:
        await conn.execute(
            "update retina.screenings set assignment_status='QUEUED' where id=%s", (screening["id"],)
        )
        return
    await conn.execute(
        """update retina.screenings set assigned_doctor_id=%s, assigned_at=now(),
                          assignment_status='ASSIGNED' where id=%s""",
        (doctor["user_id"], screening["id"]),
    )
    if screening["status"] == "REPORT_READY":
        await transition(conn, screening, "SENT_TO_DOCTOR")
    await conn.execute(
        """insert into retina.notifications(org_id,user_id,screening_id,message)
                          values(%s,%s,%s,'A screening is ready for clinical review')""",
        (screening["org_id"], doctor["user_id"], screening["id"]),
    )
