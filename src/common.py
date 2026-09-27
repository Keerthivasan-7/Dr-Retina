"""Shared constants for the Dr.Retina pipeline.

Single source of truth for label encoding, dataset roles, and paths so
`src/data`, `src/train`, and `src/eval` never disagree with each other.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_SPLITS = PROJECT_ROOT / "data" / "splits"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOCAL_DATASETS_DIR = PROJECT_ROOT / "datasets"

# ICDR 0-4 grading scale, shared across EyePACS / APTOS / DDR.
ICDR_CLASSES = ["No_DR", "Mild", "Moderate", "Severe", "Proliferative_DR"]
NUM_ICDR_CLASSES = len(ICDR_CLASSES)

# Referable DR = moderate NPDR or worse (ICDR >= 2).
REFERABLE_THRESHOLD = 2

# Datasets that make up the internal train/val pool. Never add IDRiD or
# Messidor-2 here — see P0 ground rule #1.
INTERNAL_TRAIN_SOURCES = ["eyepacs", "aptos2019", "ddr"]

# Locked external test sets. Any script that fits/tunes on these is a bug.
EXTERNAL_TEST_SOURCES = ["idrid", "messidor2"]

FIQA_CLASSES = ["Good", "Usable", "Reject"]

IMAGE_SIZE = 512
RANDOM_SEED = 42

# A small compatibility bridge for data already placed in this workspace before
# the canonical data/raw layout was introduced.  The pipeline never moves or
# rewrites these folders; it merely reads them when the canonical source is
# absent.  New acquisitions should always use data/raw/<source>.
LEGACY_SOURCE_ROOTS = {
    "aptos2019": [LOCAL_DATASETS_DIR / "aptos2019-blindness-detection"],
    "eyepacs": [LOCAL_DATASETS_DIR / "Diabetic Retinopathy Detection" / "zip files"],
}


def source_root(source: str) -> Path:
    """Return the canonical source folder, or a documented local legacy copy."""
    canonical = DATA_RAW / source
    if canonical.exists() and any(canonical.iterdir()):
        return canonical
    for candidate in LEGACY_SOURCE_ROOTS.get(source, []):
        if candidate.exists() and any(candidate.iterdir()):
            return candidate
    return canonical
