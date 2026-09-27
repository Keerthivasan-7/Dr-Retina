# Implementation Plan

## Delivered foundation

- Canonical constants, ICDR/FIQA label contracts, and an explicit source-role policy.
- Data manifest writer, harmonization, patient-level internal DR split, and locked
  external DR split validation.
- Compact ResNet-50/EfficientNet-B0 baseline, FIQA baseline, shared training engine,
  class weighting, AMP, QWK/F1/recall reporting, and external DR evaluation.
- Preprocessing parity for raw external DR images and FIQA evaluation at its native
  input resolution.
- Reproducibility metadata (configuration and split hashes, environment, Git revision)
  saved beside model checkpoints.
- Automated unit-test coverage for the data contracts and preprocessing primitives.

## P0 exit criteria

1. Acquire and verify all required sources; `data/manifest.csv` must contain real image
   counts and fingerprints.
2. Generate the DR splits with no use of `--allow-missing-external`.
3. Generate EyeQ train/validation and locked DRIMDB CSVs.
4. Train FIQA and DR baselines; preserve `best.pt`, `history.json`, and
   `run_metadata.json` for each run.
5. Produce a locked DRIMDB FIQA report and an external DR evaluation report containing
   internal validation, IDRiD, and Messidor-2, before and after the FIQA gate.
6. Run the MATLAB feasibility spike against an actual processed fundus image.

P0 is not complete merely because an internal accuracy target is met. A P0 result is
reportable only when every external result and associated provenance artifact exists.

## P1 — domain generalization

Implement FundusAug-style camera, illumination, crop, blur, and compression variations
behind a configuration switch. Compare one controlled baseline against one augmented run;
select using the internal validation rule established before viewing locked-test results,
then run one external evaluation.

## P2 — clinical prediction quality

Add ordinal/CORAL loss, calibration, and lesion segmentation only after P1. Define each
metric, threshold, and ablation in configuration before training. Keep 5-class QWK,
within-one-grade accuracy, and referable-DR sensitivity/specificity as distinct outcomes.

## P3 — explanations

Implement Grad-CAM++ strictly as “model attention (coarse)” and implement lesion overlays
only from the validated segmentation branch. Test that generated artifacts include this
language and never claim lesion detection from attention alone.

## P4 — MATLAB and Simulink

Re-train the selected compact model natively in MATLAB where feasible, reproduce the
preprocessing/data contract, and construct the Simulink screening-resource workflow.
Document any unavoidable Python/MATLAB discrepancy and verify it on a fixed fixture set.

## P5 — serving and safety

Build the FastAPI service only after a selected checkpoint is frozen. It must expose
quality disposition, grade probabilities, calibrated confidence, model version, and
explicit referral/reject handling. It is a decision-support prototype, not a diagnostic
device; add authentication, audit logging, privacy review, and clinical validation before
any deployment beyond demonstration.
