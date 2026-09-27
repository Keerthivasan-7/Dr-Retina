from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app.auth import context
from app.main import app


@pytest.fixture
def technician():
    conn = AsyncMock()
    member = {"org_id": uuid4(), "user_id": uuid4(), "role": "LAB_TECHNICIAN"}

    async def ctx():
        yield conn, member, None

    app.dependency_overrides[context] = ctx
    yield conn, member
    app.dependency_overrides.clear()


async def test_missing_bearer_rejected_without_database():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/patients")
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/v1/users/invite", {"email": "doctor@example.org", "fullName": "Doctor", "role": "DOCTOR"}),
        (f"/api/v1/screenings/{uuid4()}/reviews", {"decision": "VERIFIED", "finalAssessment": "No DR"}),
        (f"/api/v1/screenings/{uuid4()}/assign", {"doctorId": str(uuid4())}),
    ],
)
async def test_technician_cannot_escalate(technician, path, payload):
    conn, _ = technician
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(path, json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 403
    conn.execute.assert_not_awaited()


async def test_tenant_spoofing_is_validation_failure(technician):
    conn, _ = technician
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/patients",
            json={"fullName": "Asha Rao", "age": 50, "gender": "Female", "org_id": str(uuid4())},
            headers={"Idempotency-Key": str(uuid4())},
        )
    assert response.status_code == 422
    assert "Asha" not in response.text
    conn.execute.assert_not_awaited()


async def test_unknown_screening_not_found(technician, monkeypatch):
    import app.main as routes

    monkeypatch.setattr(routes, "one", AsyncMock(return_value=None))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/screenings/{uuid4()}/image")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "private, no-store"


def test_openapi_contract_contains_required_routes():
    paths = app.openapi()["paths"]
    for path in [
        "/api/v1/me",
        "/api/v1/organizations",
        "/api/v1/users/invite",
        "/api/v1/screenings/analyze",
        "/api/v1/screenings/{sid}/reviews",
        "/api/v1/patients/{pid}/history",
    ]:
        assert path in paths
