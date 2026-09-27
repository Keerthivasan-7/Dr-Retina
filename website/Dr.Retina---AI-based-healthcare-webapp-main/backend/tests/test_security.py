from io import BytesIO
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from PIL import Image
from pydantic import ValidationError

from app.auth import identity, require
from app.images import validate_image
from app.pipeline import PredictionOutput, QualityOutput, call_model
from app.schemas import InviteIn, PatientIn, ReviewIn
from app.workflow import transition, validate_transition


@pytest.mark.parametrize(
    "role,allowed",
    [
        ("LAB_TECHNICIAN", "DOCTOR"),
        ("LAB_TECHNICIAN", "ORG_ADMIN"),
        ("DOCTOR", "ORG_ADMIN"),
        ("ORG_ADMIN", "DOCTOR"),
    ],
)
def test_roles_do_not_inherit_clinical_powers(role, allowed):
    with pytest.raises(HTTPException) as error:
        require({"role": role}, allowed)
    assert error.value.status_code == 403


@pytest.mark.parametrize(
    "old,new",
    [
        ("IMAGE_UPLOADED", "VERIFIED"),
        ("QUALITY_REJECTED", "AI_PROCESSING"),
        ("AI_PROCESSING", "COMPLETED"),
        ("VERIFIED", "AI_PROCESSING"),
        ("COMPLETED", "DOCTOR_REVIEWING"),
        ("ADDITIONAL_ANALYSIS_REQUIRED", "VERIFIED"),
    ],
)
def test_illegal_transitions_rejected(old, new):
    with pytest.raises(HTTPException) as error:
        validate_transition(old, new)
    assert error.value.status_code == 409


async def test_transition_records_actor_and_status():
    conn = AsyncMock()
    screening = {"id": uuid4(), "org_id": uuid4(), "status": "DOCTOR_REVIEWING"}
    actor = uuid4()
    await transition(conn, screening, "VERIFIED", actor)
    assert screening["status"] == "VERIFIED"
    assert conn.execute.await_count == 2
    assert actor in conn.execute.await_args.args[1]


@pytest.mark.parametrize(
    "body",
    [
        {"decision": "VERIFIED"},
        {"decision": "ADDITIONAL_ANALYSIS_REQUIRED", "reason": "IMAGE_QUALITY"},
        {"decision": "ADDITIONAL_ANALYSIS_REQUIRED", "comments": "Retake"},
        {"decision": "VERIFIED", "finalAssessment": "No DR", "aiSeverity": "No DR"},
        {"decision": "VERIFIED", "finalAssessment": "No DR", "doctor_id": str(uuid4())},
    ],
)
def test_review_requires_documentation_and_rejects_overwriting_ai(body):
    with pytest.raises(ValidationError):
        ReviewIn(**body)


def test_good_review():
    assert (
        ReviewIn(
            decision="VERIFIED", finalAssessment="No visible DR; follow local screening protocol"
        ).decision
        == "VERIFIED"
    )


def test_tenant_and_role_spoofing_rejected():
    with pytest.raises(ValidationError):
        PatientIn(fullName="Test Patient", age=50, gender="Female", organization_id=str(uuid4()))
    with pytest.raises(ValidationError):
        InviteIn(fullName="Admin", email="admin@example.org", role="ORG_ADMIN")


@pytest.mark.parametrize("data", [b"", b"not an image", b"<svg onload='alert(1)'/>", b"\x89PNG\r\n"])
def test_invalid_uploads(data):
    with pytest.raises(HTTPException):
        validate_image(data)


def test_image_signature_and_dimensions():
    stream = BytesIO()
    Image.new("RGB", (300, 300), "red").save(stream, format="PNG")
    original = stream.getvalue()
    assert validate_image(original) == ("image/png", 300, 300)
    assert stream.getvalue() == original
    tiny = BytesIO()
    Image.new("RGB", (10, 10)).save(tiny, format="JPEG")
    with pytest.raises(HTTPException):
        validate_image(tiny.getvalue())


def prediction():
    return {
        "severity": "No DR",
        "confidence": 0.8,
        "model_version": "test-v1",
        "probabilities": {
            "No DR": 0.8,
            "Mild NPDR": 0.1,
            "Moderate NPDR": 0.05,
            "Severe NPDR": 0.03,
            "Proliferative DR": 0.02,
        },
    }


def test_prediction_contract():
    assert PredictionOutput(**prediction()).severity == "No DR"
    for field, value in [
        ("confidence", 0.9),
        ("severity", "Severe NPDR"),
        ("probabilities", {"No DR": 1}),
        ("confidence", float("nan")),
        ("explainability_method", "Grad-CAM++"),
    ]:
        invalid = prediction()
        invalid[field] = value
        with pytest.raises(ValidationError):
            PredictionOutput(**invalid)


def test_quality_finite():
    with pytest.raises(ValidationError):
        QualityOutput(score=float("nan"), accepted=True, reasons=[], model_version="quality-v1")


async def test_missing_auth():
    with pytest.raises(HTTPException) as error:
        await identity(None)
    assert error.value.status_code == 401


async def test_forged_token_rejected(monkeypatch):
    from types import SimpleNamespace

    import app.auth as auth

    monkeypatch.setattr(
        auth,
        "settings",
        lambda: SimpleNamespace(supabase_url="https://example.invalid", supabase_publishable_key="public"),
    )
    client = AsyncMock()
    client.get.return_value = SimpleNamespace(status_code=401)
    manager = AsyncMock()
    manager.__aenter__.return_value = client
    monkeypatch.setattr(auth.httpx, "AsyncClient", lambda **kw: manager)
    with pytest.raises(HTTPException) as error:
        await identity(HTTPAuthorizationCredentials(scheme="Bearer", credentials="forged.admin.token"))
    assert error.value.status_code == 401


async def test_unconfigured_model_never_fabricates_prediction(monkeypatch):
    from types import SimpleNamespace

    import app.pipeline as pipeline

    monkeypatch.setattr(pipeline, "settings", lambda: SimpleNamespace(ai_service_url="", ai_model_version=""))
    with pytest.raises(RuntimeError, match="AI_NOT_CONFIGURED"):
        await call_model("predict", b"image", "image/png", uuid4())
