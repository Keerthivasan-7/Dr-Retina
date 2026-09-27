# SIH submission plan — 7 days to 2026-09-30

Read alongside `docs/PROBLEM_STATEMENT.md` (the actual rubric) and
`docs/IMPLEMENTATION_PLAN.md` (the original phased research plan — this doc is the
deadline-scoped reprioritization of it).

Status legend: [ ] not started, [~] in progress, [x] done, [-] explicitly cut for time
(state why so it's a decision, not a gap that slipped).

## Cut for time (decided 2026-09-23)

- [-] Full clinical validation (P5) — not achievable in code on any timeline; call out
  as future work in the report, not attempted.
- [-] Full DRIVE vessel segmentation as its own validated component — DR grading and
  explainability don't strictly need it; skip unless time remains after everything else.
- [-] Full native MATLAB retraining matching the Python model's performance (P4 as
  originally scoped) — today's spike alone (an *untrained* single step) cost ~4h fighting
  R2026a environment friction. Use ONNX-into-MATLAB for the serving pipeline instead;
  keep the already-passing feasibility spike as the "native toolchain verified" proof.

## Priority order

1. [x] **P1 finish** — Colab augmented run completed (30-epoch budget, early-stopped at
   epoch 21, best epoch 13). **Result: P1 does not beat P0.** P1 best internal val
   QWK = 0.8106 vs P0's 0.8158 — applying the pre-registered internal-QWK-only
   selection rule (no peeking at external results), **P0 remains the production
   checkpoint**. Diagnosis: P1's train_loss kept falling smoothly to 0.16 by epoch 21
   while val_loss exploded 0.88→2.86 over the same span — clear overfitting that set in
   fast; augmentation slowed it but didn't prevent it or improve on P0's peak.
   Everything downstream (calibration, ONNX export, MATLAB inference, threshold tuning)
   was already built on P0, so nothing needs to be redone. A second Colab account is
   still running the same recipe at a T4-maximized batch size
   (`configs/p1_augmented_colab_t4max.yaml`) purely for faster wall-clock — same data/
   architecture, so not expected to change this conclusion; not blocking further work.
2. [x] **Referable-DR operating-point tuning** — done (`src/eval/tune_referable_threshold.py`).
   Finding: no threshold clears both PS targets simultaneously on the P0 baseline —
   sensitivity caps ~87% internally; externally, sensitivity clears 90% but specificity
   collapses (IDRiD 0.575, Messidor-2 0.751) — a domain-shift signature P1 should help.
   Re-run against P1's checkpoint once selected.
3. [x] **Lesion segmentation** — now TWO complementary checkpoints, used together:
   - **Optic Disc**: `reports/checkpoints/p2_lesion_segmentation/best.pt` (IDRiD-only,
     whole-image, compact from-scratch U-Net, 80 epochs). OD dice **0.842**. Kept
     as-is — nothing downstream needed this to change.
   - **MA/HE/EX/SE**: `reports/checkpoints/p2d_lesion_segmentation_v2/best.pt`
     (`src/train/train_lesion_segmentation_v2.py`), reached after two earlier merged-data
     attempts (`p2b`, `p2c`) both left MA at exactly 0.0 despite adding DDR (+757) and
     e-ophtha (+463) bonus training images and, in `p2c`, native-resolution
     lesion-centered patches — proving data volume and even patch-based resolution
     weren't themselves sufficient. Root-caused to two further factors, both fixed in v2:
     (a) Optic Disc — a large structure needing whole-image context — was still jointly
     trained alongside the tiny lesions in `p2c`, went unstable under patch training
     (swung 0.57→0→0.49 epoch to epoch), and dominated the mean-dice early-stopping
     metric, cutting training short before the patch approach could be fairly judged;
     (b) BCE+Dice loss and a from-scratch compact U-Net aren't what the published
     microaneurysm-segmentation literature actually uses. **v2 fixes both**: drops OD
     entirely (already solved above), switches to Focal Tversky Loss (Abraham & Khan
     2018 — asymmetric false-negative weighting + focal term, purpose-built for exactly
     this small-ROI/extreme-imbalance problem), and swaps the from-scratch U-Net for an
     ImageNet-pretrained ResNet-34 encoder (`segmentation_models_pytorch`), all standard
     practice per the microaneurysm-segmentation literature. Result (epoch 8/20, early
     stopped): **MA 0.029** (first non-zero result all project), HE 0.254, EX 0.305,
     SE 0.244 — all four stable across epochs, no v1-style instability. For scale: FGADR's
     Dense U-Net (1,842 clean expert images) gets MA=0.559 — 0.029 is a genuine
     proof-of-concept result on ~1,300 merged images, not a finished detector. Report this
     scale caveat wherever these masks are used downstream. A classical morphological
     top-hat MA detector (MATLAB Image Processing Toolbox) remains available as a
     training-data-free complementary signal if time allows. **Wired into the
     explainability report** (`src/explain/report.py` now takes both `--lesion-checkpoint`
     for OD and `--lesion-v2-checkpoint` for MA/HE/EX/SE, combining both models' outputs
     into one overlay) — verified end-to-end on a real image, both checkpoints loading and
     contributing correctly to the same report.
4. [x] **Grad-CAM++ wiring** — done (`src/explain/gradcam.py`), tested end-to-end on a real
   val image; heatmap correctly avoided the optic disc and focused on plausible lesion
   regions. Also wired into a combined explainability report generator
   (`src/explain/report.py`), tested end-to-end: FIQA gate → calibrated DR grade →
   Grad-CAM++ overlay → per-lesion evidence overlay → JSON + PNG report.
5. [x] **ONNX export + MATLAB import** — all three models exported and verified
   (`src/serve/export_onnx.py`, all <5e-6 diff vs PyTorch): DR grading, FIQA gate, lesion
   segmentation. **Calibration** done (`src/eval/calibrate_model.py`): temperature=5.38,
   val ECE 0.142→0.025, external ECE improved similarly (IDRiD 0.356→0.105, Messidor-2
   0.245→0.042). **MATLAB-side native inference pipeline done**
   (`matlab/import_onnx_pipeline.m`): imports all three ONNX models via
   `importNetworkFromONNX` (Deep Learning Toolbox Converter for ONNX Model Format — not
   installed by default, user installed via Add-On Explorer), runs FIQA gate → calibrated
   DR grading → lesion segmentation natively in MATLAB on a real fundus image, applying the
   same fitted temperature (5.3817) as the Python pipeline. Verified against
   `src/explain/report.py`'s output on the same image: FIQA=Usable, DR grade=Moderate
   (referable), calibrated confidence 0.725 in MATLAB vs 0.720 in Python (near-exact match,
   small residual difference from `imresize` vs PIL/cv2 interpolation), lesion pattern
   identical (MA absent; HE/EX/SE/OD present). This is what makes inference genuinely
   MATLAB-based per the PS, not just Python with exported weights.
6. [x] **Simulink capacity model** — done (`matlab/screening_capacity_model.m`), two
   SimEvents stages (capture+AI grading; ophthalmologist review) built and saved as real
   `.slx` models, parameterized from this project's own measurements (referable rate
   27.4% from `data/splits/val.csv`, transmission time from mean processed-image size,
   review time from the PS's own 30s target). **Environment limitation, documented in the
   script**: this trial-license R2026a install only has one C/C++ compiler (Visual Studio
   18 / "2026"), which Simulink Coder's toolchain registry doesn't yet recognize, so
   SimEvents' discrete-event engine silently schedules zero entities (confirmed via
   isolated single-block tests — no alternate compiler available, license expires in 2
   days, not worth further environment surgery). The script falls back to analytical
   queueing results from the identical parameters: capture ~0.18% utilization, AI grading
   ~0.14% utilization, ophthalmologist ~11.4% utilization (0.91h of work in an 8h day) —
   **verdict: 1 ophthalmologist comfortably sustains 100,000 patients/year** at this
   referable rate, with large slack even under real-world arrival burstiness.
7. [~] **Demo pipeline** — MATLAB App Designer edition done
   (`matlab/DrRetinaScreeningApp.m`, plus reusable `matlab/runScreeningPipeline.m` and
   `matlab/loadScreeningNetworks.m`): upload image → FIQA gate → calibrated grade →
   lesion evidence overlay (OD from the IDRiD-only model, MA/HE/EX/SE from v2) → caveats,
   entirely native MATLAB inference via `importNetworkFromONNX` on all 4 exported models
   (added `reports/onnx/lesion_segmentation_v2.onnx`, verified <3e-5 diff vs PyTorch).
   Written as plain classdef code (same uifigure/uigridlayout components App Designer's
   canvas generates — opens and edits visually in App Designer too), not built via the
   interactive designer. **Verified**: app constructs cleanly, loads all 4 networks, builds
   every UI component with no errors; the underlying pipeline function independently
   verified against the Python report (identical FIQA/grade/confidence/coverage numbers).
   **Not verified**: actual button-click interaction (upload/run) — no tool available to
   drive a MATLAB GUI, so this needs a manual click-through (`app = DrRetinaScreeningApp`)
   before it's demo-ready. FastAPI wrapper around `src/explain/report.py` remains a
   possible second, optional demo if time allows after the report.
8. [ ] **Report / slides / demo video** — do not let this get squeezed to the last hour;
   the PS is judged on presentation too. State cut items and dataset-scale caveats
   honestly rather than overclaiming.

## Infra note (2026-09-23, cost real time — don't reintroduce)

Two environment issues ate a large chunk of today, both now fixed:
- `torch.load` on PyTorch 2.6+ defaults `weights_only=True` and rejects numpy scalars in
  our checkpoints — fixed by passing `weights_only=False` everywhere (checkpoints are
  self-generated and trusted) and by casting metrics to plain `float()` before saving.
- albumentations does a PyPI version-check on import that was timing out on this
  network (2-40s+ per attempt), and DataLoader workers re-import it on every spawn —
  looked exactly like GPU contention/deadlocks (which is what it was misdiagnosed as for
  a while) but was actually this. Fixed via `NO_ALBUMENTATIONS_UPDATE=1`, set in code so
  it doesn't depend on the shell environment.
- SimEvents (`sldelib`) blocks silently schedule zero entities in this R2026a trial
  install — no error, just empty stats/NaN throughput — because Simulink Coder's
  toolchain registry doesn't recognize the only installed compiler ("Unable to determine
  the default toolchain" warning, non-fatal, easy to miss). Not fixable without installing
  an older/alternate compiler; `matlab/screening_capacity_model.m` now detects this (empty
  stat logs) and falls back to analytical queueing results from the same parameters. Two
  other real SimEvents gotchas found along the way, worth knowing before touching these
  blocks again: (1) `get_param(block, 'Utilization'/'AverageWait'/'NumberEntitiesArrived')`
  only ever returns the checkbox state `'on'`/`'off'`, never the computed number — the
  value is emitted as a new signal output port that must be wired to a logger (e.g. "To
  Workspace") and read back after `sim()`; (2) enabling such a stat inserts the new signal
  port *before* the block's existing entity/message port, pushing it to the last port
  index, so entity-chain wiring must be redone with the shifted index if stats are enabled
  after the chain was drawn (safer to always enable stats first).

## Numeric targets to track against (from the PS, not the original plan's 0.85 QWK gate)

- Referable DR (grade >= 2): sensitivity > 0.90 **and** specificity > 0.85, simultaneously,
  on both locked external sets (IDRiD, Messidor-2).
- Explainability: Grad-CAM output + lesion-level evidence, both present, both correctly
  labeled per README ground rule #5.
- Simulink: an actual optimization/capacity result, not just "the diagram runs."
