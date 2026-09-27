# Dataset Notes and Governance

## Source roles

| Source | Role | Status required before a reported result |
| --- | --- | --- |
| EyePACS, APTOS 2019, DDR | Internal DR training/validation only | Labels mapped to ICDR 0–4; patient-level split where linkage exists |
| IDRiD, Messidor-2 | Locked external DR test sets | Present, non-empty, label-validated, never used for training or tuning |
| EyeQ | Internal FIQA training/validation only | All three classes (Good, Usable, Reject) present |
| DRIMDB | Locked external FIQA test set | Present and never used for FIQA training or threshold selection |

`data/raw/<source>` is the canonical data location. The code can discover the existing
workspace copies of APTOS and EyePACS when the canonical folder is empty, but it does
not move, duplicate, or mutate raw data. These legacy locations are compatibility-only;
record any new acquisition in `data/manifest.csv`.

### Known caveat: Messidor-2 source

Official Messidor-2 (ADCIS) requires request-based access. The acquired copy is the
Kaggle mirror `mariaherrerot/messidor2preprocess`, whose 1,744 images are 512x512
PNGs (`*_PP.png`) already cropped/resized by a third party before this pipeline's own
`circular_crop_and_resize` runs on top — unlike IDRiD, which stays raw until
harmonization/eval applies the identical preprocessing (see "DR data contract" below).
Messidor-2 external results are therefore not a clean apples-to-apples
domain-generalization test the way IDRiD is; treat IDRiD as the primary external
generalization signal and Messidor-2 as a secondary, caveated one until raw Messidor-2
images (official ADCIS access, or another untouched mirror) are acquired.

## DR data contract

Every internal split row contains `image_id`, `processed_path`, `label`, `patient_id`,
and `source`. ICDR labels are integers 0–4 in this order: No DR, Mild, Moderate,
Severe, Proliferative DR. DDR label 5 is explicitly excluded from grading and may be
used only as a separately documented FIQA-reject candidate.

Run the DR preparation sequence only after all locked external sets have been acquired:

```powershell
python -m src.data.download --all
python -m src.data.harmonize
python -m src.data.make_splits
```

`make_splits` now fails if IDRiD or Messidor-2 is absent, empty, has duplicate image
IDs, unresolved paths, or labels outside 0–4. `--allow-missing-external` exists solely
for local plumbing checks; results from such a run are not eligible for reporting.

Training images are circular-cropped and resized during harmonization. External DR
images remain raw to preserve their locked source material, then receive the identical
circular-crop-and-resize operation in evaluation. This avoids measuring a preprocessing
mismatch as a domain-generalization failure.

## FIQA data contract

FIQA labels use: `Good=0`, `Usable=1`, `Reject=2`. To keep source-layout assumptions
out of code, provide one CSV per source to the split builder. It accepts an image column
named `image_id`, `image`, `id`, `filename`, `path`, or `image_path`, plus a label column
named `label`, `quality`, `quality_label`, or `grade`. Accepted values are `Good`/`0`,
`Usable`/`1`, and `Reject`, `Unusable`, `Bad`, or `2`.

```powershell
python -m src.data.make_fiqa_splits `
  --eyeq-labels <eyeq-labels.csv> --eyeq-root <eyeq-images> `
  --drimdb-labels <drimdb-labels.csv> --drimdb-root <drimdb-images>
```

This creates `fiqa_train.csv`, `fiqa_val.csv`, and the locked
`fiqa_external_drimdb.csv`. Training refuses EyeQ input that lacks any class. DRIMDB is
not fed to the trainer; it is reserved for external FIQA reporting.

## Reporting rules

- Do not select an architecture, epoch, augmentation, FIQA threshold, or calibration
  setting by external-test performance.
- Record the manifest, split CSV hashes, configuration hash, package/runtime details,
  and Git revision beside every checkpoint.
- Report internal and external DR results together, both before and after the FIQA gate,
  including the rejection rate and the grades of rejected images.
- An FIQA checkpoint is always evaluated at its own configured resolution (224px by
  default), never through the DR model's 512px loader.
