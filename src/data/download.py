"""P0.2 — data acquisition.

One function per source dataset, plus a manifest writer that records source,
license, and checksum for every downloaded/verified dataset. Datasets behind
manual registration (IDRiD via IEEE DataPort, Messidor-2 via ADCIS) are not
scriptable end-to-end: their functions verify an already-downloaded archive
and log it, printing instructions if the archive is missing.

Run: python -m src.data.download --all
     python -m src.data.download --dataset eyepacs
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common import DATA_RAW, source_root  # noqa: E402

MANIFEST_PATH = DATA_RAW.parent.parent / "data" / "manifest.csv"

# Known totals from the plan's acceptance gate (P0.2), used to sanity-check
# what actually landed on disk.
EXPECTED_IMAGE_COUNTS = {
    "eyepacs": 88702,
    # The Kaggle bundle contains 3,662 labelled training and 1,928 unlabelled
    # test images; the manifest deliberately counts the whole acquired bundle.
    "aptos2019": 5590,
    "ddr": 13673,
    "idrid": 516,
    "messidor2": 1748,
    "drive": 40,
    "drimdb": 216,
}


@dataclass
class DatasetSpec:
    name: str
    license: str
    dest: Path
    manual_url: str
    manual_instructions: str
    kaggle_slug: str | None = None
    extensions: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".tif", ".tiff")


SPECS: dict[str, DatasetSpec] = {
    "eyepacs": DatasetSpec(
        name="eyepacs",
        license="Kaggle competition rules — diabetic-retinopathy-detection (EyePACS)",
        dest=DATA_RAW / "eyepacs",
        manual_url="https://www.kaggle.com/competitions/diabetic-retinopathy-detection",
        manual_instructions="kaggle competitions download -c diabetic-retinopathy-detection",
        kaggle_slug="competitions/diabetic-retinopathy-detection",
    ),
    "aptos2019": DatasetSpec(
        name="aptos2019",
        license="Kaggle competition rules — aptos2019-blindness-detection (APTOS/ARIA)",
        dest=DATA_RAW / "aptos2019",
        manual_url="https://www.kaggle.com/competitions/aptos2019-blindness-detection",
        manual_instructions="kaggle competitions download -c aptos2019-blindness-detection",
        kaggle_slug="competitions/aptos2019-blindness-detection",
    ),
    "ddr": DatasetSpec(
        name="ddr",
        license="DDR dataset license (see GitHub release — non-commercial research use)",
        dest=DATA_RAW / "ddr",
        manual_url="https://github.com/nkicsl/DDR-dataset",
        manual_instructions=(
            "Download release archives from https://github.com/nkicsl/DDR-dataset/releases "
            f"and extract into {DATA_RAW / 'ddr'}"
        ),
    ),
    "idrid": DatasetSpec(
        name="idrid",
        license="CC BY 4.0 (IEEE DataPort)",
        dest=DATA_RAW / "idrid",
        manual_url="https://ieee-dataport.org/open-access/indian-diabetic-retinopathy-image-dataset-idrid",
        manual_instructions=(
            "Register + download from IEEE DataPort, then extract "
            "'A. Segmentation', 'B. Disease Grading', 'C. Localization' into "
            f"{DATA_RAW / 'idrid'}. LOCKED EXTERNAL TEST SET — never use for "
            "training/tuning outside src/eval."
        ),
    ),
    "messidor2": DatasetSpec(
        name="messidor2",
        license="Messidor-2 license (ADCIS — research use, request-based access)",
        dest=DATA_RAW / "messidor2",
        manual_url="https://www.adcis.net/en/third-party/messidor2/",
        manual_instructions=(
            f"Request access via ADCIS, then extract into {DATA_RAW / 'messidor2'}. "
            "LOCKED EXTERNAL TEST SET — never use for training/tuning outside src/eval."
        ),
    ),
    "drive": DatasetSpec(
        name="drive",
        license="DRIVE dataset license (research use)",
        dest=DATA_RAW / "drive",
        manual_url="https://drive.grand-challenge.org/",
        manual_instructions=f"Download from the DRIVE challenge site and extract into {DATA_RAW / 'drive'}",
    ),
    "eyeq": DatasetSpec(
        name="eyeq",
        license="EyeQ dataset license (research use, derived from EyePACS)",
        dest=DATA_RAW / "eyeq",
        manual_url="https://github.com/HzFu/EyeQ",
        manual_instructions=f"Follow the EyeQ GitHub release links and extract into {DATA_RAW / 'eyeq'}",
    ),
    "drimdb": DatasetSpec(
        name="drimdb",
        license="DRIMDB dataset license (research use)",
        dest=DATA_RAW / "drimdb",
        manual_url="https://academictorrents.com/browse.php?search=DRIMDB",
        manual_instructions=f"Download DRIMDB and extract into {DATA_RAW / 'drimdb'}. External FIQA eval only.",
    ),
}


def _sha256_of_dir(path: Path, limit_files: int = 200) -> str:
    """Cheap directory fingerprint: hash of sorted (relpath, size) tuples for
    up to `limit_files` files. Not a full-content hash — that would be too
    slow for an 88k-image dataset — but stable enough to catch swapped/partial
    downloads between runs."""
    h = hashlib.sha256()
    if not path.exists():
        return ""
    files = sorted(p for p in path.rglob("*") if p.is_file())[:limit_files]
    for f in files:
        h.update(str(f.relative_to(path)).encode())
        h.update(str(f.stat().st_size).encode())
    return h.hexdigest()


def _count_images(path: Path, extensions: tuple[str, ...]) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.rglob("*") if p.suffix.lower() in extensions)


def _kaggle_download(slug: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["kaggle"] + slug.split("/", 1)[0:1] + ["download", "-p", str(dest)]
    # slug is "competitions/<name>" or "datasets/<owner/name>"
    kind, ref = slug.split("/", 1)
    cmd = ["kaggle", kind, "download", "-c" if kind == "competitions" else "-d", ref, "-p", str(dest)]
    print(f"[eyepacs/aptos] running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    for zpath in dest.glob("*.zip"):
        print(f"  extracting {zpath.name}")
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(dest)


def download_eyepacs(spec: DatasetSpec) -> None:
    try:
        _kaggle_download(spec.kaggle_slug, spec.dest)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[eyepacs] automatic download failed ({e}). Manual fallback:\n  {spec.manual_instructions}")


def download_aptos2019(spec: DatasetSpec) -> None:
    try:
        _kaggle_download(spec.kaggle_slug, spec.dest)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[aptos2019] automatic download failed ({e}). Manual fallback:\n  {spec.manual_instructions}")


def _manual_only(spec: DatasetSpec) -> None:
    if spec.dest.exists() and any(spec.dest.iterdir()):
        print(f"[{spec.name}] found existing data at {spec.dest}")
    else:
        print(f"[{spec.name}] not found. This dataset requires manual acquisition:")
        print(f"  source: {spec.manual_url}")
        print(f"  {spec.manual_instructions}")


def download_ddr(spec: DatasetSpec) -> None:
    _manual_only(spec)


def download_idrid(spec: DatasetSpec) -> None:
    _manual_only(spec)


def download_messidor2(spec: DatasetSpec) -> None:
    _manual_only(spec)


def download_drive(spec: DatasetSpec) -> None:
    _manual_only(spec)


def download_eyeq(spec: DatasetSpec) -> None:
    _manual_only(spec)


def download_drimdb(spec: DatasetSpec) -> None:
    _manual_only(spec)


DOWNLOAD_FNS = {
    "eyepacs": download_eyepacs,
    "aptos2019": download_aptos2019,
    "ddr": download_ddr,
    "idrid": download_idrid,
    "messidor2": download_messidor2,
    "drive": download_drive,
    "eyeq": download_eyeq,
    "drimdb": download_drimdb,
}


def write_manifest(names: list[str]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in names:
        spec = SPECS[name]
        discovered_path = source_root(name)
        count = _count_images(discovered_path, spec.extensions)
        rows.append(
            {
                "dataset": name,
                "license": spec.license,
                "source_url": spec.manual_url,
                "dest_path": str(discovered_path),
                "image_count": count,
                "expected_count": EXPECTED_IMAGE_COUNTS.get(name, ""),
                "count_matches_expected": count == EXPECTED_IMAGE_COUNTS.get(name, -1),
                "dir_fingerprint_sha256": _sha256_of_dir(discovered_path),
            }
        )
    with open(MANIFEST_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote manifest: {MANIFEST_PATH}")
    for r in rows:
        flag = "OK" if r["count_matches_expected"] else "MISMATCH/MISSING"
        print(f"  [{flag:17s}] {r['dataset']:12s} count={r['image_count']:<7} expected={r['expected_count']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="download/verify all 8 sources")
    parser.add_argument("--dataset", choices=list(SPECS.keys()), help="download/verify a single source")
    args = parser.parse_args()

    if not args.all and not args.dataset:
        parser.error("pass --all or --dataset <name>")

    names = list(SPECS.keys()) if args.all else [args.dataset]
    for name in names:
        print(f"\n=== {name} ===")
        DOWNLOAD_FNS[name](SPECS[name])

    write_manifest(names if args.all else list(SPECS.keys()))


if __name__ == "__main__":
    main()
