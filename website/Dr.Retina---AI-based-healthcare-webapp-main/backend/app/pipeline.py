import base64
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import settings
from .images import validate_image

CLASSES = ("No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR")


class QualityOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    accepted: bool
    reasons: list[str] = Field(max_length=20)
    model_version: str = Field(min_length=1, max_length=120)


class PredictionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    severity: Literal["No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR"]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    probabilities: dict[str, float]
    model_version: str = Field(min_length=1, max_length=120)
    findings: list[str] = Field(default_factory=list, max_length=100)
    explainability_method: Literal["Grad-CAM++"] | None = None
    explainability_png_base64: str | None = Field(default=None, max_length=8_000_000)

    @model_validator(mode="after")
    def calibrated_contract(self):
        if set(self.probabilities) != set(CLASSES):
            raise ValueError("Five ICDR class probabilities are required")
        if any(not 0 <= p <= 1 for p in self.probabilities.values()):
            raise ValueError("Invalid class probability")
        if abs(sum(self.probabilities.values()) - 1) > 0.001:
            raise ValueError("Probabilities must sum to one")
        if abs(self.confidence - self.probabilities[self.severity]) > 0.001:
            raise ValueError("Confidence must match predicted class probability")
        if self.probabilities[self.severity] < max(self.probabilities.values()):
            raise ValueError("Predicted class must have maximal probability")
        if bool(self.explainability_method) != bool(self.explainability_png_base64):
            raise ValueError("Explainability method and image must be supplied together")
        return self


async def call_model(endpoint, image, mime, job_id):
    cfg = settings()
    if not cfg.ai_service_url or not cfg.ai_model_version:
        raise RuntimeError("AI_NOT_CONFIGURED")
    if cfg.environment == "production" and not cfg.ai_service_url.startswith("https://"):
        raise RuntimeError("AI_TLS_REQUIRED")
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{cfg.ai_service_url.rstrip('/')}/{endpoint}",
            headers={
                "Authorization": f"Bearer {cfg.ai_service_key.get_secret_value()}",
                "Idempotency-Key": str(job_id),
            },
            files={"image": ("fundus", image, mime)},
            data={"model_version": cfg.ai_model_version},
        ) as response:
            response.raise_for_status()
            parts = bytearray()
            async for chunk in response.aiter_bytes():
                parts.extend(chunk)
                if len(parts) > 9_000_000:
                    raise ValueError("AI response exceeds limit")
    return bytes(parts)


def explainability_bytes(output):
    if not output.explainability_png_base64:
        return None
    data = base64.b64decode(output.explainability_png_base64, validate=True)
    mime, _, _ = validate_image(data)
    if mime != "image/png":
        raise ValueError("Explainability must be PNG")
    return data
