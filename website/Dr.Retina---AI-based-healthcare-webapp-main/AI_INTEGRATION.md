# AI service contract

No trained weights or model endpoint were provided. The worker integrates with a separately deployed,
authenticated service; it does not simulate classifications.

## Reference implementation

`src/serve/ai_service.py` in the parent Dr.Retina repo implements this exact contract — `/quality` (the
FIQA gate) and `/predict` (calibrated DR grading + lesion segmentation findings + a real Grad-CAM++
overlay), on top of the same trained checkpoints and preprocessing used by `src/explain/report.py`,
the MATLAB demo, and the Flutter mobile app. Run it from the Dr.Retina repo root:

```
AI_SERVICE_KEY=<matches backend/.env's AI_SERVICE_KEY> \
AI_MODEL_VERSION=<matches backend/.env's AI_MODEL_VERSION> \
uvicorn src.serve.ai_service:app --host 0.0.0.0 --port 8100
```

It loads all four checkpoints once at startup (`GET /health` reports readiness and device), and returns
findings/severity/lesion coverage consistent with the mobile app's on-device results for the same image.

Set AI_SERVICE_URL, AI_SERVICE_KEY and the approved AI_MODEL_VERSION.
The service receives an Authorization Bearer header and an Idempotency-Key header (job UUID).
Both requests are multipart: `image` contains original JPEG/PNG bytes and `model_version` is the expected version.
Do not forward patient names, phone numbers, organization credentials or clinical notes to the model.

## POST /quality

Return HTTP 200 and:

```json
{
  "score": 0.95,
  "accepted": true,
  "reasons": [],
  "model_version": "approved-quality-version"
}
```

The score must be finite and between 0 and 1. The validated quality service determines acceptance.
Rejected images become QUALITY_REJECTED; the classifier is never called.
These example numbers describe the wire format only, not measured performance.

## POST /predict

Called only after accepted image quality:

```json
{
  "severity": "No DR",
  "confidence": 0.80,
  "probabilities": {
    "No DR": 0.80,
    "Mild NPDR": 0.10,
    "Moderate NPDR": 0.05,
    "Severe NPDR": 0.03,
    "Proliferative DR": 0.02
  },
  "model_version": "the-configured-AI_MODEL_VERSION",
  "findings": [],
  "explainability_method": null,
  "explainability_png_base64": null
}
```

Exactly these five classes are required. Probabilities must be finite, in [0,1], and sum to 1 within 0.001.
The selected class must have maximal probability; confidence must equal its probability.
The returned classifier version must exactly match the configured version.
Unknown result fields are rejected so contract changes are deliberate.

When supported, send `explainability_method: "Grad-CAM++"` and the base64-encoded PNG together.
The worker validates and stores the overlay separately from the original. No heatmap is fabricated.
Current overlay validation expects a valid PNG at least 256 × 256 pixels, with the same decompression safety limit as uploads.
The response has a bounded size; the base64 field is limited to 8 million characters.

A quality model, classifier and clinically validated Grad-CAM++ generation must exist in the external service.
Lesion descriptions appear only when the model actually returns them.
The worker's HTTP timeout is 120 seconds per model call. Expensive deployments must stay within that contract or introduce a separately reviewed asynchronous adapter.

## Failures

Missing model configuration gives the job AI_NOT_CONFIGURED.
Invalid JSON, invalid probabilities/version, unavailable storage or service errors give ANALYSIS_UNAVAILABLE.
The original image remains preserved. A technician can retry a failed job without re-uploading;
a QUALITY_REJECTED image requires a new capture linked to the rejected screening.
Quality and AI results, timestamps and model versions are append-only.
Doctor assessments cannot change any original AI prediction.

The test classifier used by tests/test_integration.py is a synthetic fixture, never reachable by the production application.

