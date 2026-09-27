"""AI service adapter for the Dr.Retina web app (website/Dr.Retina---AI-based-
healthcare-webapp-main). Implements the two-endpoint contract documented in
that repo's AI_INTEGRATION.md — POST /quality and POST /predict — on top of
the same models, preprocessing, and Grad-CAM++ code already used by
src/explain/report.py, MATLAB, and the Flutter mobile app.

This is a standalone service the web backend's worker calls over HTTP with a
bearer token; it is not part of the web backend itself and does not touch its
database. Models are loaded once at startup, not per-request.

Run:
  uvicorn src.serve.ai_service:app --host 0.0.0.0 --port 8100

Then point the web backend's backend/.env at it:
  AI_SERVICE_URL=http://localhost:8100
  AI_SERVICE_KEY=<same value as AI_SERVICE_KEY below>
  AI_MODEL_VERSION=dr-retina-2026.09-p0-p2d
"""
from __future__ import annotations

import base64
import hmac
import logging
import os
import sys
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import torch
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common import ICDR_CLASSES, REPORTS_DIR  # noqa: E402
from src.data.dataset import IMAGENET_MEAN, IMAGENET_STD  # noqa: E402
from src.data.preprocess import circular_crop_and_resize  # noqa: E402
from src.data.segmentation_dataset import LESION_CHANNELS, LESION_NAMES, LESION_ONLY_CHANNELS  # noqa: E402
from src.explain.gradcam import ATTENTION_LABEL, compute_gradcam_overlay  # noqa: E402
from src.models.dr_backbone import build_dr_model  # noqa: E402
from src.models.fiqa import build_fiqa_model  # noqa: E402
from src.models.lesion_unet import build_lesion_model, build_pretrained_lesion_model  # noqa: E402

logger = logging.getLogger("retina.ai_service")

# --- Contract constants (must match backend/app/pipeline.py exactly) -------
WEB_CLASSES = ("No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR")
# ICDR_CLASSES (src/common.py) -> the web app's contract class names, same order.
ICDR_TO_WEB = dict(zip(ICDR_CLASSES, WEB_CLASSES))
FIQA_LABELS = ("Good", "Usable", "Reject")

MODEL_VERSION = os.environ.get("AI_MODEL_VERSION", "dr-retina-2026.09-p0-p2d")
SERVICE_KEY = os.environ.get("AI_SERVICE_KEY", "")

CHECKPOINTS_DIR = REPORTS_DIR / "checkpoints"
DR_CHECKPOINT = CHECKPOINTS_DIR / "p0_baseline_resnet50" / "best.pt"
FIQA_CHECKPOINT = CHECKPOINTS_DIR / "p0_fiqa_effnet_b0" / "best.pt"
LESION_CHECKPOINT = CHECKPOINTS_DIR / "p2_lesion_segmentation" / "best.pt"
LESION_V2_CHECKPOINT = CHECKPOINTS_DIR / "p2d_lesion_segmentation_v2" / "best.pt"
CALIBRATION_PATH = CHECKPOINTS_DIR / "p0_baseline_resnet50" / "calibration.json"

LESION_COLORS = {"MA": (255, 0, 0), "HE": (255, 128, 0), "EX": (255, 255, 0), "SE": (0, 255, 255), "OD": (0, 255, 0)}

bearer = HTTPBearer(auto_error=False)
models: dict = {}


def _to_model_input(image_rgb: np.ndarray, image_size: int) -> torch.Tensor:
    resized = cv2.resize(image_rgb, (image_size, image_size), interpolation=cv2.INTER_AREA)
    norm = (resized.astype(np.float32) / 255.0 - np.array(IMAGENET_MEAN)) / np.array(IMAGENET_STD)
    return torch.from_numpy(norm.transpose(2, 0, 1)).float().unsqueeze(0)


def _load_models() -> None:
    import json

    if not SERVICE_KEY:
        logger.warning("AI_SERVICE_KEY is not set — every request will be rejected with 401.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    models["device"] = device

    fiqa_ckpt = torch.load(FIQA_CHECKPOINT, map_location=device, weights_only=False)
    fiqa_model = build_fiqa_model(pretrained=False).to(device)
    fiqa_model.load_state_dict(fiqa_ckpt["model_state"])
    fiqa_model.eval()
    models["fiqa"] = {"model": fiqa_model, "image_size": fiqa_ckpt["config"]["data"]["image_size"]}

    dr_ckpt = torch.load(DR_CHECKPOINT, map_location=device, weights_only=False)
    dr_model = build_dr_model(backbone=dr_ckpt["config"]["model"]["backbone"],
                               num_classes=dr_ckpt["config"]["model"]["num_classes"], pretrained=False).to(device)
    dr_model.load_state_dict(dr_ckpt["model_state"])
    dr_model.eval()
    models["dr"] = {"model": dr_model, "image_size": dr_ckpt["config"]["data"]["image_size"],
                     "backbone": dr_ckpt["config"]["model"]["backbone"]}

    temperature = 1.0
    if CALIBRATION_PATH.exists():
        temperature = float(json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))["temperature"])
    models["temperature"] = temperature

    lesion_ckpt = torch.load(LESION_CHECKPOINT, map_location=device, weights_only=False)
    lesion_model = build_lesion_model(num_classes=len(LESION_CHANNELS),
                                       base_channels=lesion_ckpt["config"]["model"]["base_channels"]).to(device)
    lesion_model.load_state_dict(lesion_ckpt["model_state"])
    lesion_model.eval()
    models["lesion"] = lesion_model

    v2_ckpt = torch.load(LESION_V2_CHECKPOINT, map_location=device, weights_only=False)
    v2_model = build_pretrained_lesion_model(
        num_classes=len(LESION_ONLY_CHANNELS),
        encoder_name=v2_ckpt["config"]["model"].get("encoder_name", "resnet34"),
    ).to(device)
    v2_model.load_state_dict(v2_ckpt["model_state"])
    v2_model.eval()
    models["lesion_v2"] = v2_model

    logger.info("AI service models loaded on %s (calibration temperature=%.3f)", device, temperature)


async def lifespan(_app: FastAPI):
    _load_models()
    yield
    models.clear()


app = FastAPI(title="Dr.Retina AI service", lifespan=lifespan)


def _authorize(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
               idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> None:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Authentication required")
    if not SERVICE_KEY or not hmac.compare_digest(credentials.credentials, SERVICE_KEY):
        raise HTTPException(401, "Invalid credentials")
    if not idempotency_key:
        raise HTTPException(400, "Idempotency-Key header is required")


def _decode_image(data: bytes) -> np.ndarray:
    array = np.frombuffer(data, dtype=np.uint8)
    bgr = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if bgr is None:
        raise HTTPException(422, "Could not decode image")
    return bgr


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


@app.post("/quality", response_model=QualityOutput)
def quality(image: UploadFile = File(...), model_version: str = Form(...),
            _auth: None = Depends(_authorize)) -> QualityOutput:
    del model_version  # informational only; this service always reports its own MODEL_VERSION
    raw_bgr = _decode_image(image.file.read())
    processed_bgr = circular_crop_and_resize(raw_bgr, 512)
    processed_rgb = cv2.cvtColor(processed_bgr, cv2.COLOR_BGR2RGB)

    fiqa = models["fiqa"]
    device = models["device"]
    x = _to_model_input(processed_rgb, fiqa["image_size"]).to(device)
    with torch.no_grad():
        probs = torch.softmax(fiqa["model"](x), dim=1)[0].cpu().numpy()
    label = FIQA_LABELS[int(probs.argmax())]
    accepted = label != "Reject"
    score = float(1.0 - probs[FIQA_LABELS.index("Reject")])
    reasons = [] if accepted else [f"Image quality gate rejected this capture "
                                    f"({probs[FIQA_LABELS.index('Reject')] * 100:.1f}% confidence) — recapture required."]
    return QualityOutput(score=round(score, 4), accepted=accepted, reasons=reasons, model_version=MODEL_VERSION)


@app.post("/predict", response_model=PredictionOutput)
def predict(image: UploadFile = File(...), model_version: str = Form(...),
            _auth: None = Depends(_authorize)) -> PredictionOutput:
    del model_version
    raw_bgr = _decode_image(image.file.read())
    processed_bgr = circular_crop_and_resize(raw_bgr, 512)
    processed_rgb = cv2.cvtColor(processed_bgr, cv2.COLOR_BGR2RGB)
    device = models["device"]

    # DR grade, temperature-calibrated
    dr = models["dr"]
    dr_input = _to_model_input(processed_rgb, dr["image_size"]).to(device)
    with torch.no_grad():
        logits = dr["model"](dr_input)
        calibrated_probs = torch.softmax(logits / models["temperature"], dim=1)[0].cpu().numpy()
    grade_idx = int(calibrated_probs.argmax())
    severity = ICDR_TO_WEB[ICDR_CLASSES[grade_idx]]
    confidence = float(calibrated_probs[grade_idx])
    probabilities = {ICDR_TO_WEB[name]: float(p) for name, p in zip(ICDR_CLASSES, calibrated_probs)}
    total = sum(probabilities.values())
    probabilities = {k: v / total for k, v in probabilities.items()}  # keep the sum-to-1 contract exact
    confidence = probabilities[severity]

    # Grad-CAM++ attention, real (not fabricated) — same code path as src/explain/report.py
    overlay_rgb = compute_gradcam_overlay(dr["model"], dr["backbone"], dr_input, processed_rgb, grade_idx, device)
    ok, png_bytes = cv2.imencode(".png", cv2.cvtColor(overlay_rgb, cv2.COLOR_RGB2BGR))
    explainability_png_base64 = base64.b64encode(png_bytes.tobytes()).decode("ascii") if ok else None
    explainability_method = "Grad-CAM++" if explainability_png_base64 else None

    # Lesion evidence: OD from the IDRiD-only model, MA/HE/EX/SE from v2 — see
    # src/explain/report.py for why these are two separate models.
    lesion_masks: dict[str, np.ndarray] = {}
    lesion_input = _to_model_input(processed_rgb, 512).to(device)
    with torch.no_grad():
        od_logits = models["lesion"](lesion_input)
        od_masks = (torch.sigmoid(od_logits) > 0.5)[0].cpu().numpy()
    lesion_masks["OD"] = od_masks[LESION_CHANNELS.index("OD")]
    with torch.no_grad():
        v2_logits = models["lesion_v2"](lesion_input)
        v2_masks = (torch.sigmoid(v2_logits) > 0.5)[0].cpu().numpy()
    for i, code in enumerate(LESION_ONLY_CHANNELS):
        lesion_masks[code] = v2_masks[i]

    findings = []
    for code in LESION_CHANNELS:
        mask = lesion_masks.get(code)
        if mask is not None and mask.any():
            coverage_pct = float(mask.mean() * 100)
            findings.append(f"{LESION_NAMES[code]}: {coverage_pct:.2f}% of image area")
    if severity != "No DR":
        findings.append(f"{ATTENTION_LABEL} See the attached Grad-CAM++ overlay.")

    return PredictionOutput(
        severity=severity, confidence=round(confidence, 4), probabilities=probabilities,
        model_version=MODEL_VERSION, findings=findings[:100],
        explainability_method=explainability_method, explainability_png_base64=explainability_png_base64,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "device": str(models.get("device")), "model_version": MODEL_VERSION}
