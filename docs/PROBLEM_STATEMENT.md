# SIH 2026 — Problem Statement 26038

**Title:** Explainable AI for Diabetic Retinopathy Screening in Rural India
**Organization / Department:** MathWorks
**Category:** Software — MedTech / BioTech / HealthTech
**Deadline:** 2026-09-30

## Background

India has over 77 million diabetic adults — the second highest globally. Diabetic
Retinopathy (DR) affects ~18% of this population and is a leading cause of preventable
blindness. Early screening can prevent 90% of vision loss, but India has only ~1
ophthalmologist per 100,000 rural population, making mass manual screening infeasible.
Existing AI solutions function as black boxes, lack clinical validation rigor, and fail
with variable image quality from portable fundus cameras in field conditions. A robust,
explainable, and validated screening system is essential for deployment in primary
healthcare centres across rural India.

## Description

Design a **MATLAB-based** retinal image analysis pipeline for automated DR screening
addressing real-world deployment challenges:

1. **Image Quality Assessment and Enhancement.** Automatically evaluate fundus images
   for adequacy (focus, illumination, field of view). Apply adaptive enhancement (CLAHE,
   illumination normalization, denoising) for borderline images; reject ungradeable ones
   with recapture feedback.

2. **Retinal Structure Segmentation.** Extract clinically relevant structures — optic
   disc/fovea localization, vessel segmentation, microaneurysm detection, exudate
   segmentation, hemorrhage classification, and neovascularization detection.

3. **DR Severity Grading.** Classify using the International Clinical DR severity scale
   (Levels 0–4, no DR to proliferative DR) with clinically acceptable **sensitivity
   >90% and specificity >85% for referable DR (Level 2+)**.

4. **Explainability Module.** Implement Grad-CAM attention maps, **lesion-level evidence
   correlated with clinical criteria**, calibrated confidence scores, and automated
   annotated reports — enabling ophthalmologist validation in under 30 seconds for a
   human-in-the-loop workflow.

5. **Simulink Workflow Simulation.** Model the telemedicine screening pipeline in
   Simulink — image acquisition rates, bandwidth constraints, processing throughput, and
   review capacity — to optimize resource allocation for district-level programs serving
   100,000+ patients annually.

> This problem demands clinical validation rigor, sub-pixel microaneurysm detection, and
> clinically meaningful explainability.

**Required tools:** Image Processing Toolbox, Computer Vision Toolbox, Deep Learning
Toolbox, Medical Imaging Toolbox, Simulink, Statistics and Machine Learning Toolbox.

## Expected solution

A working prototype demonstrating:
- DR classification with **>90% sensitivity and >85% specificity for referable DR**
- **Explainable Grad-CAM outputs rated as clinically useful**
- A **Simulink model optimizing screening resource allocation**
- Validation against published benchmarks showing the integrated pipeline outperforms
  any single-technique approach

## Datasets named in the PS

- APTOS 2019 Blindness Detection — https://www.kaggle.com/c/aptos2019-blindness-detection
- IDRiD — https://ieee-dataport.org/open-access/indian-diabetic-retinopathy-image-dataset-idrid
- DRIVE (vessel extraction) — https://drive.grand-challenge.org/
- Messidor-2 — https://www.adcis.net/en/third-party/messidor2/

## What this means for this project's plan (read alongside docs/IMPLEMENTATION_PLAN.md)

- **Lesion-level evidence is a hard requirement (item 4), not optional.** A coarse
  Grad-CAM heatmap alone does not satisfy this PS — IDRiD's segmentation labels
  (Microaneurysms, Haemorrhages, Hard Exudates, Soft Exudates, Optic Disc; already in
  `data/raw/idrid/A. Segmentation/`) must drive real lesion-level reasoning, even if
  only proof-of-concept scale given 81 labeled images.
- **"MATLAB-based pipeline" is explicit and the org is MathWorks.** Full native
  retraining in the time available is high-risk (see P0.7 spike experience); ONNX
  export of the trained PyTorch model into MATLAB (Deep Learning Toolbox) for the
  serving/inference pipeline is the pragmatic way to satisfy this honestly.
- **The >90% sensitivity / >85% specificity bar is numeric and simultaneous.** Current
  P0 external results do not clear both at once on either locked set (IDRiD: sens 0.960
  / spec 0.643; Messidor-2: sens 0.878 / spec 0.870). Referable-DR operating-point
  (threshold) tuning on internal val is the fastest lever here, before considering
  retraining.
- **Simulink needs a real capacity/resource-allocation model**, not a proof-it-runs
  diagram — acquisition rate, bandwidth, throughput, review capacity, sized for
  100,000+ patients/year.
