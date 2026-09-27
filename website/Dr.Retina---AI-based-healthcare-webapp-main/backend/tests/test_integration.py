"""Real PostgreSQL schema + HTTP API + worker. Supabase identity, object storage and model are test doubles."""

import json
import os
from contextlib import asynccontextmanager
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import httpx
import psycopg
import pytest
from PIL import Image
from psycopg.rows import dict_row

from app import db, main, worker
from app.auth import Identity, identity

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Run npm run test:integration")


async def test_full_clinical_flow_and_tenant_isolation(monkeypatch):
    conn = await psycopg.AsyncConnection.connect(
        os.environ["TEST_DATABASE_URL"], autocommit=True, row_factory=dict_row, prepare_threshold=None
    )

    class Pool:
        @asynccontextmanager
        async def connection(self):
            yield conn

    monkeypatch.setattr(db, "_pool", Pool())
    cfg = SimpleNamespace(
        max_upload_bytes=25 * 1024 * 1024, worker_lease_seconds=300, ai_model_version="fixture-v1"
    )
    monkeypatch.setattr(main, "settings", lambda: cfg)
    monkeypatch.setattr(worker, "settings", lambda: cfg)
    admin, tech, doctor, other, admin_session, tech_session, doctor_session, other_session = [
        uuid4() for _ in range(8)
    ]
    org, org_b = uuid4(), uuid4()
    try:
        for uid, sid in [
            (admin, admin_session),
            (tech, tech_session),
            (doctor, doctor_session),
            (other, other_session),
        ]:
            await conn.execute("insert into auth.users values(%s)", (uid,))
            await conn.execute("insert into auth.sessions values(%s,%s,null)", (sid, uid))
        for oid, owner, name in [(org, admin, "Fixture A"), (org_b, other, "Fixture B")]:
            await conn.execute(
                """insert into retina.organizations(id,name,type,address,contact_email,identifier,created_by)
                values(%s,%s,'Clinic','Synthetic','test@example.org',%s,%s)""",
                (oid, name, str(oid), owner),
            )
        for uid, oid, role in [
            (admin, org, "ORG_ADMIN"),
            (tech, org, "LAB_TECHNICIAN"),
            (doctor, org, "DOCTOR"),
            (other, org_b, "ORG_ADMIN"),
        ]:
            await conn.execute(
                """insert into retina.members(user_id,org_id,email,full_name,role)
                values(%s,%s,%s,'Synthetic user',%s)""",
                (uid, oid, f"{uid}@example.org", role),
            )
        current = [Identity(tech, tech_session, "tech@example.org")]

        async def fixture_identity():
            return current[0]

        main.app.dependency_overrides[identity] = fixture_identity
        images = {}

        async def upload(path, data, mime):
            assert path not in images
            images[path] = data

        async def download(path):
            return images[path]

        monkeypatch.setattr(main.storage, "upload", upload)
        monkeypatch.setattr(main.storage, "download", download)

        async def model(endpoint, data, mime, job):
            if endpoint == "quality":
                return json.dumps(
                    {"score": 0.95, "accepted": True, "reasons": [], "model_version": "quality-fixture"}
                ).encode()
            return json.dumps(
                {
                    "severity": "No DR",
                    "confidence": 0.8,
                    "model_version": "fixture-v1",
                    "probabilities": {
                        "No DR": 0.8,
                        "Mild NPDR": 0.1,
                        "Moderate NPDR": 0.05,
                        "Severe NPDR": 0.03,
                        "Proliferative DR": 0.02,
                    },
                }
            ).encode()

        monkeypatch.setattr(worker, "call_model", model)
        await conn.execute("set role retina_api")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            key = str(uuid4())
            payload = {"fullName": "Synthetic Patient", "age": 54, "gender": "Female", "knownDiabetic": "Yes"}
            response = await client.post("/api/v1/patients", json=payload, headers={"Idempotency-Key": key})
            assert response.status_code == 201, response.text
            pid = response.json()["data"]["id"]
            replay = await client.post("/api/v1/patients", json=payload, headers={"Idempotency-Key": key})
            assert replay.json()["data"]["id"] == pid
            conflict = await client.post(
                "/api/v1/patients", json={**payload, "age": 55}, headers={"Idempotency-Key": key}
            )
            assert conflict.status_code == 409
            image = BytesIO()
            Image.new("RGB", (300, 300), "red").save(image, format="PNG")
            original = image.getvalue()
            submitted = await client.post(
                "/api/v1/screenings/analyze",
                data={"patientId": pid, "eye": "OD"},
                files={"image": ("retina.png", original, "image/png")},
                headers={"Idempotency-Key": str(uuid4())},
            )
            assert submitted.status_code == 202, submitted.text
            sid = submitted.json()["screeningId"]
            assert list(images.values()) == [original]
            denied = await client.post(
                f"/api/v1/screenings/{sid}/reviews",
                json={"decision": "VERIFIED", "finalAssessment": "Unauthorized"},
                headers={"Idempotency-Key": str(uuid4())},
            )
            assert denied.status_code == 403
            current[0] = Identity(other, other_session, "other@example.org")
            assert (await client.get(f"/api/v1/screenings/{sid}/image")).status_code == 404
            assert (await client.get("/api/v1/patients")).json()["data"] == []
            await conn.execute("reset role")
            await conn.execute("set role retina_worker")
            job = await worker.claim()
            assert job
            await worker.process(job)
            await conn.execute("reset role")
            await conn.execute("set role retina_api")
            current[0] = Identity(doctor, doctor_session, "doctor@example.org")
            detail = (await client.get(f"/api/v1/screenings/{sid}")).json()
            assert detail["screening"]["status"] == "SENT_TO_DOCTOR"
            assert detail["screening"]["assigned_doctor_id"] == str(doctor)
            assert detail["ai"]["severity"] == "No DR"
            assert detail["review"] is None
            assert (await client.post(f"/api/v1/screenings/{sid}/start-review")).status_code == 200
            verified = await client.post(
                f"/api/v1/screenings/{sid}/reviews",
                json={
                    "decision": "VERIFIED",
                    "finalAssessment": "Fixture doctor assessment",
                    "comments": "Synthetic test only",
                },
                headers={"Idempotency-Key": str(uuid4())},
            )
            assert verified.status_code == 200, verified.text
            detail = (await client.get(f"/api/v1/screenings/{sid}")).json()
            assert detail["ai"]["severity"] == "No DR"
            assert detail["review"]["final_assessment"] == "Fixture doctor assessment"
            assert (await client.post(f"/api/v1/screenings/{sid}/complete")).status_code == 200
            assert (await client.get(f"/api/v1/screenings/{sid}")).json()["screening"][
                "status"
            ] == "COMPLETED"
            assert (await client.get(f"/api/v1/screenings/{sid}/image")).content == original
            assert (await client.post(f"/api/v1/screenings/{sid}/start-review")).status_code == 409
            # Additional-analysis route and technician notification preserve the old report.
            current[0] = Identity(tech, tech_session, "tech@example.org")
            submission = await client.post(
                "/api/v1/screenings/analyze",
                data={"patientId": pid, "eye": "OS"},
                files={"image": ("retina.png", original, "image/png")},
                headers={"Idempotency-Key": str(uuid4())},
            )
            sid2 = submission.json()["screeningId"]
            await conn.execute("reset role")
            await conn.execute("set role retina_worker")
            await worker.process(await worker.claim())
            await conn.execute("reset role")
            await conn.execute("set role retina_api")
            current[0] = Identity(doctor, doctor_session, "doctor@example.org")
            await client.post(f"/api/v1/screenings/{sid2}/start-review")
            needs = await client.post(
                f"/api/v1/screenings/{sid2}/reviews",
                json={
                    "decision": "ADDITIONAL_ANALYSIS_REQUIRED",
                    "reason": "ADDITIONAL_IMAGE",
                    "comments": "Repeat acquisition",
                },
                headers={"Idempotency-Key": str(uuid4())},
            )
            assert needs.status_code == 200, needs.text
            current[0] = Identity(tech, tech_session, "tech@example.org")
            assert len((await client.get("/api/v1/notifications")).json()["data"]) >= 1
            repeat = await client.post(
                "/api/v1/screenings/analyze",
                data={"patientId": pid, "eye": "OS", "parentScreeningId": sid2},
                files={"image": ("retake.png", original, "image/png")},
                headers={"Idempotency-Key": str(uuid4())},
            )
            assert repeat.status_code == 202, repeat.text
            assert len(images) == 3
            assert (await client.get(f"/api/v1/screenings/{sid2}")).json()["review"][
                "comments"
            ] == "Repeat acquisition"
            # Revoke an active technician and prove the same valid identity loses access immediately.
            current[0] = Identity(admin, admin_session, "admin@example.org")
            revoked = await client.patch(
                f"/api/v1/users/{tech}", json={"active": False, "role": "LAB_TECHNICIAN", "available": True}
            )
            assert revoked.status_code == 200, revoked.text
            current[0] = Identity(tech, tech_session, "tech@example.org")
            assert (await client.get("/api/v1/patients")).status_code == 403
    finally:
        main.app.dependency_overrides.clear()
        await conn.close()
