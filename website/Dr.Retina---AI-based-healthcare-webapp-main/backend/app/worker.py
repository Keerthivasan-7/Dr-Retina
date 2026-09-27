import asyncio
import logging
from uuid import uuid4

from psycopg.types.json import Jsonb

from . import storage
from .config import settings
from .db import all_rows, close_pool, one, open_pool, transaction
from .pipeline import PredictionOutput, QualityOutput, call_model, explainability_bytes
from .runtime import loop_factory
from .workflow import assign_doctor, transition

logger = logging.getLogger("retina.worker")


async def claim():
    async with transaction() as conn:
        row = await one(
            conn,
            """select * from retina.jobs where
          (state='QUEUED' or (state='RUNNING' and lease_until<now())) and attempts<3
          and exists(select 1 from retina.organizations o where o.id=org_id and o.active)
          order by created_at for update skip locked limit 1""",
        )
        if not row:
            return None
        token = uuid4()
        await conn.execute(
            """update retina.jobs set state='RUNNING',attempts=attempts+1,
          lease_token=%s,lease_until=now()+(%s*interval '1 second') where id=%s""",
            (token, settings().worker_lease_seconds, row["id"]),
        )
        row["lease_token"] = token
        return row


async def locked(conn, job):
    current = await one(conn, "select * from retina.jobs where id=%s for update", (job["id"],))
    if current["lease_token"] != job["lease_token"] or current["state"] != "RUNNING":
        raise RuntimeError("LEASE_LOST")
    return await one(conn, "select * from retina.screenings where id=%s for update", (job["screening_id"],))


async def process(job):
    async with transaction() as conn:
        screen = await locked(conn, job)
        img = await one(conn, "select * from retina.images where screening_id=%s", (screen["id"],))
        quality = await one(
            conn, "select * from retina.quality_results where screening_id=%s", (screen["id"],)
        )
        if screen["status"] == "IMAGE_UPLOADED":
            await transition(conn, screen, "QUALITY_CHECKING")
    data = await storage.download(img["object_path"])
    if not quality:
        result = QualityOutput.model_validate_json(await call_model("quality", data, img["mime"], job["id"]))
        async with transaction() as conn:
            screen = await locked(conn, job)
            await conn.execute(
                """insert into retina.quality_results(org_id,screening_id,score,accepted,reasons,model_version)
              values(%s,%s,%s,%s,%s,%s)""",
                (
                    screen["org_id"],
                    screen["id"],
                    result.score,
                    result.accepted,
                    Jsonb(result.reasons),
                    result.model_version,
                ),
            )
            await transition(conn, screen, "READY_FOR_ANALYSIS" if result.accepted else "QUALITY_REJECTED")
            if not result.accepted:
                await conn.execute(
                    "update retina.jobs set state='DONE',lease_until=null where id=%s", (job["id"],)
                )
                await conn.execute(
                    """insert into retina.notifications(org_id,user_id,screening_id,message)
                  values(%s,%s,%s,'Image quality was rejected. Please capture a new image.')""",
                    (screen["org_id"], screen["created_by"], screen["id"]),
                )
                return
    elif not quality["accepted"]:
        async with transaction() as conn:
            await locked(conn, job)
            await conn.execute(
                "update retina.jobs set state='DONE',lease_until=null where id=%s", (job["id"],)
            )
        return
    async with transaction() as conn:
        screen = await locked(conn, job)
        await conn.execute(
            "update retina.jobs set lease_until=now()+(%s*interval '1 second') where id=%s",
            (settings().worker_lease_seconds, job["id"]),
        )
        if screen["status"] == "READY_FOR_ANALYSIS":
            await transition(conn, screen, "AI_PROCESSING")
    result = PredictionOutput.model_validate_json(await call_model("predict", data, img["mime"], job["id"]))
    if result.model_version != settings().ai_model_version:
        raise ValueError("MODEL_VERSION_MISMATCH")
    overlay = explainability_bytes(result)
    path = None
    if overlay:
        path = f"{screen['org_id']}/{screen['id']}/explanations/{uuid4()}.png"
        await storage.upload(path, overlay, "image/png")
    async with transaction() as conn:
        screen = await locked(conn, job)
        await conn.execute(
            """insert into retina.ai_results(org_id,screening_id,severity,confidence,
          probabilities,model_version,explainability_path,findings) values(%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                screen["org_id"],
                screen["id"],
                result.severity,
                result.confidence,
                Jsonb(result.probabilities),
                result.model_version,
                path,
                Jsonb(result.findings),
            ),
        )
        await transition(conn, screen, "REPORT_READY")
        await assign_doctor(conn, screen)
        await conn.execute(
            "update retina.jobs set state='DONE',error_code=null,lease_until=null where id=%s", (job["id"],)
        )


async def recover_and_assign():
    async with transaction() as conn:
        # Also recover an assignment that raced with membership revocation.
        await conn.execute("""update retina.screenings s set assigned_doctor_id=null, assigned_at=null,
          assignment_status='QUEUED' where s.status in ('SENT_TO_DOCTOR','DOCTOR_REVIEWING')
          and s.assigned_doctor_id is not null and not exists(select 1 from retina.members m
            where m.user_id=s.assigned_doctor_id and m.org_id=s.org_id and m.active and m.role='DOCTOR')""")
        await conn.execute("""update retina.jobs set state='FAILED',error_code='RETRY_EXHAUSTED'
          where state='RUNNING' and lease_until<now() and attempts>=3""")
        rows = await all_rows(
            conn,
            """select s.* from retina.screenings s join retina.organizations o on o.id=s.org_id
          where o.active and s.assignment_status='QUEUED'
          and s.status in ('REPORT_READY','SENT_TO_DOCTOR','DOCTOR_REVIEWING')
          order by s.created_at limit 20 for update of s skip locked""",
        )
        for row in rows:
            await assign_doctor(conn, row)


async def run():
    await open_pool("retina_worker")
    try:
        while True:
            await recover_and_assign()
            job = await claim()
            if not job:
                await asyncio.sleep(settings().worker_poll_seconds)
                continue
            try:
                await process(job)
            except Exception as exc:
                # Never log image bytes, provider response bodies, credentials or clinical input.
                code = "AI_NOT_CONFIGURED" if str(exc) == "AI_NOT_CONFIGURED" else "ANALYSIS_UNAVAILABLE"
                logger.warning("Screening job failed: %s", code)
                async with transaction() as conn:
                    await conn.execute(
                        """update retina.jobs set state='FAILED',error_code=%s,lease_until=null
                      where id=%s and lease_token=%s and state='RUNNING'""",
                        (code, job["id"], job["lease_token"]),
                    )
    finally:
        await close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(), loop_factory=loop_factory)
