"""P0.3 — harmonization: common preprocessing baseline + consistent ICDR labels.

Standardizes every image to: circular fundus crop (removes black border /
letterboxing so the model can't key on it), resize to a common resolution,
and encodes labels from EyePACS/APTOS/DDR onto the same ICDR 0-4 scale.

This is preprocessing only — no augmentation (that's P1.1's job).

Run: python -m src.data.harmonize --sources eyepacs aptos2019 ddr
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common import DATA_PROCESSED, ICDR_CLASSES, IMAGE_SIZE, source_root  # noqa: E402
from src.data.preprocess import circular_crop_and_resize  # noqa: E402

# DDR's raw label space is ICDR 0-4 plus a 5th "ungradable" class. Ungradable
# images are not DR-grading training data — route them to the FIQA reject
# pool instead (see P0.4 / P1 decision-gate note on DDR ungradable examples).
DDR_UNGRADABLE_LABEL = 5


def _load_eyepacs_labels() -> pd.DataFrame:
    src = source_root("eyepacs")
    label_csv = next(src.glob("**/trainLabels.csv"), None) or next(src.glob("**/*trainLabels*.csv"), None)
    if label_csv is None:
        raise FileNotFoundError(f"EyePACS trainLabels.csv not found under {src}")
    df = pd.read_csv(label_csv)
    df = df.rename(columns={"image": "image_id", "level": "label"})
    # EyePACS image_id is "<patient>_<left|right>" — both eyes of a patient
    # must land in the same split to avoid leakage.
    df["patient_id"] = df["image_id"].str.replace(r"_(left|right)$", "", regex=True)
    df["source"] = "eyepacs"
    df["src_path"] = df["image_id"].apply(lambda i: _find_image(src, i))
    return df[["image_id", "src_path", "label", "patient_id", "source"]]


def _load_aptos2019_labels() -> pd.DataFrame:
    src = source_root("aptos2019")
    label_csv = src / "train.csv"
    if not label_csv.exists():
        raise FileNotFoundError(f"APTOS train.csv not found at {label_csv}")
    df = pd.read_csv(label_csv)
    df = df.rename(columns={"id_code": "image_id", "diagnosis": "label"})
    # APTOS publishes no patient linkage; treat each image as its own patient.
    df["patient_id"] = df["image_id"]
    df["source"] = "aptos2019"
    df["src_path"] = df["image_id"].apply(lambda i: _find_image(src, i))
    return df[["image_id", "src_path", "label", "patient_id", "source"]]


def _load_ddr_labels() -> pd.DataFrame:
    src = source_root("ddr")
    # The official DDR-dataset release splits grading labels across
    # DR_grading/{train,valid,test}.txt — none of which have "label" in the
    # filename, so they must be located by their DR_grading parent, not by name.
    label_files = sorted(src.glob("**/DR_grading/*.txt"))
    if not label_files:
        raise FileNotFoundError(f"DDR grading label files (DR_grading/*.txt) not found under {src}")
    frames = []
    for label_file in label_files:
        frame = pd.read_csv(label_file, sep=r"\s+", header=None, names=["image_id", "label"])
        # Each label file's images live directly in the like-named sibling
        # folder (DR_grading/train.txt -> DR_grading/train/<image_id>), so the
        # path is exact — no need for a (slow, ambiguous) glob over 13k files.
        split_dir = label_file.parent / label_file.stem
        frame["src_path"] = frame["image_id"].apply(lambda i, d=split_dir: str(d / i) if (d / i).is_file() else None)
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    df["patient_id"] = df["image_id"]  # DDR publishes no patient linkage
    df["source"] = "ddr"
    return df[["image_id", "src_path", "label", "patient_id", "source"]]


LOADERS = {
    "eyepacs": _load_eyepacs_labels,
    "aptos2019": _load_aptos2019_labels,
    "ddr": _load_ddr_labels,
}


_IMAGE_EXTENSIONS = (".jpeg", ".jpg", ".png", ".tif", ".tiff")
_image_index_cache: dict[Path, dict[str, str]] = {}


def _image_index(root: Path) -> dict[str, str]:
    """Stem -> path over every image file under root, built once per root.

    A per-row `root.glob(f"**/{stem}{ext}")` (the original approach) rescans
    the whole tree on every call — fine for APTOS's 5.6k files, but O(n^2)
    and effectively unusable for EyePACS's 88.7k files. Walking the tree once
    and doing dict lookups afterward is the same result, just tractable.
    """
    if root not in _image_index_cache:
        index: dict[str, str] = {}
        for path in root.rglob("*"):
            if path.suffix.lower() in _IMAGE_EXTENSIONS and path.is_file():
                index.setdefault(path.stem, str(path))
        _image_index_cache[root] = index
    return _image_index_cache[root]


def _find_image(root: Path, stem: str) -> str | None:
    return _image_index(root).get(Path(stem).stem)


def verify_label_encoding(df: pd.DataFrame) -> None:
    """Guard against an off-by-one between sources: all labels must fall in
    the shared ICDR 0-4 range once ungradable/unknown rows are dropped."""
    bad = df[~df["label"].isin(range(len(ICDR_CLASSES)))]
    if len(bad):
        raise ValueError(
            f"{len(bad)} rows have labels outside 0-{len(ICDR_CLASSES) - 1} "
            f"after ungradable filtering: {bad['source'].value_counts().to_dict()}"
        )
    for source, group in df.groupby("source"):
        dist = group["label"].value_counts(normalize=True).sort_index()
        print(f"  {source}: label distribution\n{dist.to_string()}")


def process_source(name: str, limit: int | None = None) -> pd.DataFrame:
    print(f"\n=== harmonizing {name} ===")
    df = LOADERS[name]()
    missing = df["src_path"].isna().sum()
    if missing:
        print(f"  WARNING: {missing}/{len(df)} images not found on disk, dropping")
        df = df.dropna(subset=["src_path"])

    if name == "ddr":
        n_ungradable = (df["label"] == DDR_UNGRADABLE_LABEL).sum()
        print(f"  routing {n_ungradable} DDR 'ungradable' rows to reports/ddr_ungradable.csv (FIQA use, not grading)")
        ungradable = df[df["label"] == DDR_UNGRADABLE_LABEL]
        if len(ungradable):
            out = DATA_PROCESSED.parent.parent / "reports" / "ddr_ungradable.csv"
            out.parent.mkdir(parents=True, exist_ok=True)
            ungradable.to_csv(out, index=False)
        df = df[df["label"] != DDR_UNGRADABLE_LABEL]

    if limit:
        df = df.head(limit)

    out_dir = DATA_PROCESSED / name
    out_dir.mkdir(parents=True, exist_ok=True)
    processed_rows = []
    for row in tqdm(df.itertuples(index=False), total=len(df), desc=f"processing {name}"):
        # JPEG, not PNG: source images are already JPEG-compressed, so this
        # adds no meaningful quality loss, and PNG's decode cost (~5-10x
        # slower than JPEG for photographic images) otherwise dominates
        # every training epoch's wall time far more than GPU compute does.
        out_path = out_dir / f"{row.image_id}.jpg"
        if not out_path.exists():
            image = cv2.imread(row.src_path)
            if image is None:
                continue
            processed = circular_crop_and_resize(image, IMAGE_SIZE)
            cv2.imwrite(str(out_path), processed, [cv2.IMWRITE_JPEG_QUALITY, 95])
        processed_rows.append(
            {
                "image_id": row.image_id,
                "processed_path": str(out_path),
                "label": int(row.label),
                "patient_id": row.patient_id,
                "source": row.source,
            }
        )
    return pd.DataFrame(processed_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+", default=list(LOADERS.keys()), choices=list(LOADERS.keys()))
    parser.add_argument("--limit", type=int, default=None, help="debug: cap images per source")
    args = parser.parse_args()

    frames = [process_source(name, limit=args.limit) for name in args.sources]
    combined = pd.concat(frames, ignore_index=True)

    print("\n=== verifying label encoding consistency across sources ===")
    verify_label_encoding(combined)

    out_csv = DATA_PROCESSED / "harmonized_labels.csv"
    combined.to_csv(out_csv, index=False)
    print(f"\nWrote {len(combined)} harmonized rows to {out_csv}")


if __name__ == "__main__":
    main()
