# Dr.Retina — SIH26038

Explainable AI for diabetic-retinopathy (DR) screening in rural India, built for
Smart India Hackathon 2026, Problem Statement 26038 (MathWorks).

Fundus photo → **quality gate → calibrated ICDR 0–4 grading → per-lesion
segmentation → Grad-CAM++ explanation → doctor triage queue → longitudinal
patient record.** Not a single prototype — the same four trained models run
natively across three separate, independently verified surfaces.

## What's actually built

**1. Web platform** — `website/` (Next.js 16, FastAPI, PostgreSQL via Supabase
with row-level tenant isolation). Three role-based portals: Organization
Admin, Doctor, Lab Technician. Self-registration only ever creates a new
organization's admin; Doctor/Lab Technician accounts are invite-only, enforced
in both application code and a database RLS policy. Verified end-to-end:
real signup and org creation, a real screening submitted through the upload
form, picked up by the background worker, graded, and reviewed/verified by a
doctor account — all against a live database with audit-logged actions.

**2. Mobile app** — `mobile/` (Flutter). Runs the same four ONNX models
**fully offline, on-device**, via `flutter_onnxruntime`. Camera capture screen
with an alignment guide for clip-on fundus-camera attachments, plus a gallery
upload path. Verified end-to-end on an Android emulator: ~7–11 s per
screening, results matching the Python/MATLAB reference to within rounding.

**3. MATLAB desktop app** — `matlab/DrRetinaScreeningApp.m` (App Designer).
Imports the identical ONNX exports natively via `importNetworkFromONNX` — no
retraining, no format drift from the other two surfaces. Runs the full
FIQA → grade → lesion-overlay report locally.

All three surfaces consume the same exported models in `reports/onnx/`
(produced by `src/serve/export_onnx.py`), so a result on one surface is
reproducible on the others.

## The AI pipeline

- **Image-quality gate (FIQA)**: EfficientNet-B0, 3-class (Good / Usable /
  Reject). A rejected image never reaches the classifier.
- **DR grading**: ResNet-50, 5-class ICDR severity, temperature-calibrated.
  Validation ECE reduced **0.142 → 0.025** (83%); external calibration also
  checked on IDRiD (0.356→0.105) and Messidor-2 (0.245→0.042).
- **Lesion segmentation** — two complementary models:
  - Optic disc: IDRiD-only U-Net, **Dice 0.842**.
  - Microaneurysms / haemorrhages / hard exudates / soft exudates: merged
    IDRiD+DDR+e-ophtha (~1,300 images), pretrained ResNet-34 encoder + Focal
    Tversky Loss. Dice: HE 0.254, EX 0.305, SE 0.244, **MA 0.029**. MA is an
    honest proof-of-concept (literature best on much larger data is ~0.56) —
    flagged as low-confidence in every app surface, never presented as a
    finished detector. See `docs/SIH_SUBMISSION_PLAN.md` item 3 for the full
    story of getting MA off zero.
- **Explainability**: real Grad-CAM++ attention heatmaps combined with the
  per-lesion overlay in one clinical report — not a mockup.

**Datasets**: internal train/val — EyePACS, APTOS2019, DDR. Locked external
test sets, never trained or tuned on — IDRiD, Messidor-2. Lesion-segmentation
merge — IDRiD + DDR + e-ophtha. FIQA training — EyeQ + DRIMDB. Full
provenance in `data/manifest.csv` and `docs/DATASETS.md`.

## Repo layout

```
src/
  data/       download.py, harmonize.py, make_splits.py, make_fiqa_splits.py, dataset.py
  models/     fiqa.py, dr_backbone.py, lesion_unet.py
  train/      engine.py, train_fiqa.py, train_baseline.py, train_lesion_segmentation*.py
  eval/       metrics.py, external_eval.py, fiqa_external_eval.py, tune_referable_threshold.py
  explain/    gradcam.py, report.py — combined FIQA + grade + Grad-CAM++ + lesion report
  serve/      export_onnx.py, ai_service.py — FastAPI adapter serving the trained models
matlab/       App Designer clinical demo, native ONNX import, SimEvents capacity model
mobile/       Flutter app — fully offline, on-device inference
website/      Next.js + FastAPI web platform (3 role-based portals), see website/README.md
data/         raw/ (gitignored downloads), processed/, splits/ — see data/manifest.csv
reports/      eval reports, onnx/ exports, checkpoints/ (gitignored — see below)
docs/         DATASETS.md, IMPLEMENTATION_PLAN.md, PROBLEM_STATEMENT.md, SIH_SUBMISSION_PLAN.md
notebooks/    exploratory only — nothing here is a dependency of src/
_archive/     pre-plan project state (QuickQual FIQA prototype, prior dataset downloads)
```

Model checkpoints and ONNX exports (`*.pt`, `*.onnx`) are gitignored — they're
regenerable via the training/export scripts below and would otherwise bloat
the repo. `data/raw/`, `datasets/`, and `kaggle.json` are gitignored too; see
`data/manifest.csv` for dataset provenance and `docs/DATASETS.md` for how to
re-acquire them.

## Running it

### Python pipeline (training/eval)

PyTorch has no CUDA wheels for Python 3.14 yet (only up to cp313), so this
project uses a Python 3.12 venv, not the system Python.

```bash
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -c "import torch; print(torch.cuda.is_available())"   # must print True
```

```bash
python -m src.data.download --all
python -m src.data.harmonize
python -m src.data.make_splits              # external sets required + leakage-checked
python -m src.train.train_fiqa --config configs/fiqa_efficientnet_b0.yaml
python -m src.train.train_baseline --config configs/baseline_resnet50.yaml
python -m src.train.train_lesion_segmentation_v2 --config configs/lesion_segmentation_v2.yaml
python -m src.serve.export_onnx \
    --dr-checkpoint reports/checkpoints/p0_baseline_resnet50/best.pt \
    --fiqa-checkpoint reports/checkpoints/p0_fiqa_effnet_b0/best.pt \
    --lesion-checkpoint reports/checkpoints/p2_lesion_segmentation/best.pt \
    --lesion-v2-checkpoint reports/checkpoints/p2d_lesion_segmentation_v2/best.pt
    # writes reports/onnx/*.onnx
```

### AI adapter service (used by the web platform)

```bash
AI_SERVICE_KEY=<key> AI_MODEL_VERSION=<version> \
  uvicorn src.serve.ai_service:app --host 0.0.0.0 --port 8100
```

### Web platform

See `website/Dr.Retina---AI-based-healthcare-webapp-main/README.md`,
`AUTH_SETUP.md`, and `AI_INTEGRATION.md` for the full Next.js + FastAPI +
Supabase setup (auth, database, and wiring to the AI service above).

### Mobile app

```bash
cd mobile
flutter pub get
flutter run
```

Copy `reports/onnx/*.onnx` and `reports/checkpoints/p0_baseline_resnet50/calibration.json`
into `mobile/assets/` before building — see `mobile/pubspec.yaml`.

### MATLAB demo

Requires Deep Learning Toolbox + the ONNX Model Format converter add-on,
Image Processing Toolbox, Simulink, and SimEvents (for the capacity model
only). Run `matlab/DrRetinaScreeningApp` for the screening UI, or
`matlab/feasibility_spike.m` for the standalone pipeline/tooling check.

## Ground rules (do not violate)

1. **IDRiD and Messidor-2 are locked external test sets.** Never train or tune
   on them. `src/data/make_splits.py` hard-fails if any external-test filename
   leaks into train/val.
2. Internal (same-dataset) accuracy/QWK is not a success metric on its own.
   Every phase's acceptance gate is measured externally — see
   `src/eval/external_eval.py`.
3. Compact CNN (ResNet-50 / EfficientNet-B0) over transformer/foundation
   models for the production model.
4. Grad-CAM is labeled "model attention (coarse)" in any UI/report — never
   "detected lesion location." The lesion-segmentation head is the real,
   defensible per-lesion evidence.
5. Lesion segmentation confidence is reported honestly, per class — see
   "The AI pipeline" above. Never round a weak result up to sound finished.

Dataset governance: [docs/DATASETS.md](docs/DATASETS.md). Delivery plan and
full build history: [docs/SIH_SUBMISSION_PLAN.md](docs/SIH_SUBMISSION_PLAN.md).
