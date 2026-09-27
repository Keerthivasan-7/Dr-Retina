"""P0.3 — locked splits.

Builds train.csv/val.csv (patient-level stratified split over the combined
EyePACS+APTOS+DDR pool) and external_test_idrid.csv / external_test_messidor2.csv
from the untouched external folders. Hard-fails if any external-test filename
leaks into train/val — IDRiD and Messidor-2 are locked test sets from day one
(P0 ground rule #1).

Run: python -m src.data.make_splits
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common import (  # noqa: E402
    DATA_PROCESSED,
    DATA_SPLITS,
    EXTERNAL_TEST_SOURCES,
    ICDR_CLASSES,
    INTERNAL_TRAIN_SOURCES,
    RANDOM_SEED,
    source_root,
)

VAL_FRACTION = 0.15


def load_harmonized() -> pd.DataFrame:
    path = DATA_PROCESSED / "harmonized_labels.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run `python -m src.data.harmonize` first")
    return pd.read_csv(path)


def patient_level_split(df: pd.DataFrame, val_fraction: float, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split at the patient level so both eyes of one EyePACS patient never
    straddle train/val. Stratifies on each patient's most severe grade."""
    patient_label = df.groupby("patient_id")["label"].max().reset_index()
    train_patients, val_patients = train_test_split(
        patient_label,
        test_size=val_fraction,
        stratify=patient_label["label"],
        random_state=seed,
    )
    train_df = df[df["patient_id"].isin(train_patients["patient_id"])]
    val_df = df[df["patient_id"].isin(val_patients["patient_id"])]
    return train_df, val_df


def _find_grading_csv(root: Path) -> Path | None:
    candidates = list(root.glob("**/*Disease*Grading*.csv")) + list(root.glob("**/*grad*.csv")) + list(
        root.glob("**/*.csv")
    )
    return candidates[0] if candidates else None


def load_idrid_external() -> pd.DataFrame:
    src = source_root("idrid")
    # The official IDRiD release splits the Disease Grading task into separate
    # Training/Testing label CSVs (413 + 103 = 516 images). IDRiD is used here
    # purely as a locked external test set, not trained with its own train/test
    # split, so both CSVs must be combined rather than picking just one.
    label_csvs = sorted(src.glob("**/*Disease*Grading*.csv"))
    if not label_csvs:
        raise FileNotFoundError(f"IDRiD grading CSV(s) not found under {src}")
    frames = []
    for label_csv in label_csvs:
        # The Training and Testing grading CSVs both number images from
        # IDRiD_001 onward in *separate* folders — they are different physical
        # images that happen to share an id string. Resolve each CSV strictly
        # against its own Training/Testing Set image folder (also avoids
        # colliding with same-named files in IDRiD's Segmentation/Localization
        # tasks), then tag the id with its split to keep it unique below.
        is_train = "training" in label_csv.stem.lower()
        set_glob = "*Training Set" if is_train else "*Testing Set"
        image_root = next(src.glob(f"**/B. Disease Grading/1. Original Images/{set_glob}"), None)
        if image_root is None:
            raise FileNotFoundError(f"IDRiD Disease Grading images not found for {label_csv.name}")
        frame = pd.read_csv(label_csv)
        # IDRiD's official grading CSV columns: "Image name", "Retinopathy grade", "Risk of macular edema"
        cols = {c.lower().strip(): c for c in frame.columns}
        image_col = cols.get("image name", frame.columns[0])
        label_col = cols.get("retinopathy grade", frame.columns[1])
        frame = frame.rename(columns={image_col: "image_id", label_col: "label"})[["image_id", "label"]]
        frame["image_id"] = frame["image_id"].astype(str).str.strip()
        frame["processed_path"] = frame["image_id"].apply(lambda i: str(p) if (p := _find_any(image_root, i)) else None)
        frame["image_id"] = ("idrid_train_" if is_train else "idrid_test_") + frame["image_id"]
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    df["source"] = "idrid"
    return df[["image_id", "processed_path", "label", "source"]].dropna(subset=["processed_path"])


def load_messidor2_external() -> pd.DataFrame:
    src = source_root("messidor2")
    label_csv = _find_grading_csv(src)
    if label_csv is None:
        raise FileNotFoundError(f"Messidor-2 grading CSV not found under {src}")
    df = pd.read_csv(label_csv)
    cols = {c.lower().strip(): c for c in df.columns}
    image_col = cols.get("image", df.columns[0])
    # Prefer an explicit DR grade/diagnosis column. The old broad
    # "grade" or "adjudicated" substring match picked "adjudicated_dme" (the
    # binary macular-edema flag, not the 0-4 retinopathy grade) on mirrors
    # like mariaherrerot/messidor2preprocess, silently collapsing the label
    # space to two classes.
    label_col = next(
        (cols[c] for c in cols if "diagnosis" in c or ("grad" in c and "dme" not in c and "edema" not in c)),
        df.columns[1],
    )
    df = df.rename(columns={image_col: "image_id", label_col: "label"})
    df["image_id"] = df["image_id"].astype(str).str.strip()
    df["source"] = "messidor2"
    df["processed_path"] = df["image_id"].apply(lambda i: str(p) if (p := _find_any(src, i)) else None)
    return df[["image_id", "processed_path", "label", "source"]].dropna(subset=["processed_path"])


def _find_any(root: Path, stem: str) -> Path | None:
    stem = Path(stem).stem
    for ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
        matches = list(root.glob(f"**/{stem}{ext}"))
        if matches:
            return matches[0]
    return None


def assert_no_leakage(train_val_ids: set[str], external_dfs: dict[str, pd.DataFrame]) -> None:
    for name, ext_df in external_dfs.items():
        overlap = set(ext_df["image_id"]) & train_val_ids
        if overlap:
            raise AssertionError(
                f"LEAKAGE: {len(overlap)} filenames in external_test_{name}.csv also appear in "
                f"train/val: {sorted(overlap)[:10]}..."
            )
    print("Leakage check passed: no external-test filenames appear in train/val.")


def validate_internal_pool(df: pd.DataFrame) -> None:
    unexpected = set(df["source"].unique()) - set(INTERNAL_TRAIN_SOURCES)
    if unexpected:
        raise ValueError(f"internal pool contains a locked or unknown source: {sorted(unexpected)}")
    if not df["label"].isin(range(len(ICDR_CLASSES))).all():
        raise ValueError("internal pool has labels outside the ICDR 0–4 scale")


def validate_external_set(name: str, df: pd.DataFrame) -> None:
    """Reject incomplete or ambiguously labelled locked-test CSVs before writing splits."""
    if df.empty:
        raise ValueError(f"external test set {name} has no resolved images")
    labels = pd.to_numeric(df["label"], errors="coerce")
    if labels.isna().any() or not labels.isin(range(len(ICDR_CLASSES))).all():
        raise ValueError(f"external test set {name} has labels outside the ICDR 0–4 scale")
    if df["image_id"].duplicated().any():
        raise ValueError(f"external test set {name} contains duplicate image IDs")
    missing = [path for path in df["processed_path"] if not Path(path).is_file()]
    if missing:
        raise FileNotFoundError(f"external test set {name} has {len(missing)} unreadable image paths")
    df["label"] = labels.astype(int)


def print_class_distribution(name: str, df: pd.DataFrame) -> None:
    print(f"\n{name} (n={len(df)}):")
    print(df["label"].value_counts(normalize=False).sort_index().to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-missing-external",
        action="store_true",
        help="debug-only: write internal splits when a locked external test set is unavailable",
    )
    args = parser.parse_args()

    df = load_harmonized()
    validate_internal_pool(df)
    train_df, val_df = patient_level_split(df, VAL_FRACTION, RANDOM_SEED)

    external = {}
    for name, loader in (("idrid", load_idrid_external), ("messidor2", load_messidor2_external)):
        try:
            ext_df = loader()
        except FileNotFoundError as e:
            if not args.allow_missing_external:
                raise FileNotFoundError(
                    f"locked external test set {name} is required. Acquire it or use "
                    f"--allow-missing-external only for local pipeline debugging. Original error: {e}"
                ) from e
            print(f"\nWARNING: debug-only run skipped external_test_{name}.csv — {e}")
            continue
        validate_external_set(name, ext_df)
        print_class_distribution(f"external_test_{name}", ext_df)
        external[name] = ext_df

    train_val_ids = set(train_df["image_id"]) | set(val_df["image_id"])
    missing_sources = set(EXTERNAL_TEST_SOURCES) - set(external)
    if missing_sources and not args.allow_missing_external:
        raise AssertionError(f"required locked external sets missing: {sorted(missing_sources)}")
    if external:
        assert_no_leakage(train_val_ids, external)

    # Do not leave a partial split set behind when an input validation fails.
    DATA_SPLITS.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(DATA_SPLITS / "train.csv", index=False)
    val_df.to_csv(DATA_SPLITS / "val.csv", index=False)
    for name, ext_df in external.items():
        ext_df.to_csv(DATA_SPLITS / f"external_test_{name}.csv", index=False)
    print_class_distribution("train", train_df)
    print_class_distribution("val", val_df)


if __name__ == "__main__":
    main()
