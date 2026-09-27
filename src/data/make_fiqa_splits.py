"""Build explicit FIQA train/validation and locked DRIMDB external CSVs.

The source label files are required inputs because EyeQ and DRIMDB are
distributed with different folder layouts.  Each CSV must contain an image ID
or path column and a quality label.  Accepted label aliases are documented in
docs/DATASETS.md.

Run:
  python -m src.data.make_fiqa_splits --eyeq-labels <labels.csv> --eyeq-root <images> \
      --drimdb-labels <labels.csv> --drimdb-root <images>
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from src.common import DATA_SPLITS, FIQA_CLASSES, RANDOM_SEED

LABEL_ALIASES = {
    "good": "Good", "0": "Good", "usable": "Usable", "1": "Usable",
    "reject": "Reject", "unusable": "Reject", "bad": "Reject", "2": "Reject",
}
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


def _column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    normalised = {column.lower().strip(): column for column in frame.columns}
    for candidate in candidates:
        if candidate in normalised:
            return normalised[candidate]
    raise ValueError(f"expected one of {candidates}; found {list(frame.columns)}")


_image_index_cache: dict[Path, dict[str, str]] = {}


def _image_index(root: Path) -> dict[str, str]:
    """Stem -> path over every image file under root, built once per root.

    A per-row `root.glob(f"**/{stem}{ext}")` rescans the whole tree on every
    call, which is O(n^2) and unusable once root has tens of thousands of
    files (e.g. EyeQ's ~29k labels resolved against EyePACS's ~89k images).
    """
    if root not in _image_index_cache:
        index: dict[str, str] = {}
        for path in root.rglob("*"):
            if path.suffix.lower() in IMAGE_EXTENSIONS and path.is_file():
                index.setdefault(path.stem, str(path.resolve()))
        _image_index_cache[root] = index
    return _image_index_cache[root]


def _resolve_path(root: Path, value: str) -> str | None:
    candidate = Path(value)
    if candidate.is_file():
        return str(candidate.resolve())
    direct = root / candidate
    if direct.is_file():
        return str(direct.resolve())
    return _image_index(root).get(candidate.stem)


def load_quality_labels(labels_path: str | Path, image_root: str | Path, source: str) -> pd.DataFrame:
    """Normalise a source label CSV to the pipeline's Good/Usable/Reject IDs."""
    frame = pd.read_csv(labels_path)
    image_col = _column(frame, ("image_id", "image", "id", "filename", "path", "image_path"))
    label_col = _column(frame, ("label", "quality", "quality_label", "grade"))
    quality_names = frame[label_col].astype(str).str.strip().str.lower().map(LABEL_ALIASES)
    if quality_names.isna().any():
        unknown = sorted(frame.loc[quality_names.isna(), label_col].astype(str).unique())[:10]
        raise ValueError(f"{source} has unknown quality labels: {unknown}")
    paths = frame[image_col].astype(str).map(lambda value: _resolve_path(Path(image_root), value))
    if paths.isna().any():
        raise FileNotFoundError(f"{source} has {int(paths.isna().sum())} images that cannot be resolved")
    output = pd.DataFrame({
        "image_id": frame[image_col].astype(str),
        "processed_path": paths,
        "label": quality_names.map({name: index for index, name in enumerate(FIQA_CLASSES)}).astype(int),
        "source": source,
    })
    if output["image_id"].duplicated().any():
        raise ValueError(f"{source} label CSV has duplicate image IDs")
    return output


def make_fiqa_splits(eyeq: pd.DataFrame, val_fraction: float = 0.15, seed: int = RANDOM_SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    if set(eyeq["label"].unique()) != set(range(len(FIQA_CLASSES))):
        raise ValueError("EyeQ training data must contain Good, Usable, and Reject examples")
    train, val = train_test_split(eyeq, test_size=val_fraction, stratify=eyeq["label"], random_state=seed)
    return train.reset_index(drop=True), val.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eyeq-labels", required=True)
    parser.add_argument("--eyeq-root", required=True)
    parser.add_argument("--drimdb-labels", required=True)
    parser.add_argument("--drimdb-root", required=True)
    args = parser.parse_args()

    eyeq = load_quality_labels(args.eyeq_labels, args.eyeq_root, "eyeq")
    drimdb = load_quality_labels(args.drimdb_labels, args.drimdb_root, "drimdb")
    train, val = make_fiqa_splits(eyeq)
    DATA_SPLITS.mkdir(parents=True, exist_ok=True)
    train.to_csv(DATA_SPLITS / "fiqa_train.csv", index=False)
    val.to_csv(DATA_SPLITS / "fiqa_val.csv", index=False)
    drimdb.to_csv(DATA_SPLITS / "fiqa_external_drimdb.csv", index=False)
    for name, frame in (("fiqa_train", train), ("fiqa_val", val), ("fiqa_external_drimdb", drimdb)):
        print(f"{name} n={len(frame)} labels={frame['label'].value_counts().sort_index().to_dict()}")


if __name__ == "__main__":
    main()
