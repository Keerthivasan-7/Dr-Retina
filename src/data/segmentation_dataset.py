"""IDRiD lesion segmentation dataset — pairs each fundus image with its
per-lesion-type binary masks (Microaneurysms, Haemorrhages, Hard Exudates,
Soft Exudates, Optic Disc).

A lesion type with no mask file for a given image means "none present" (the
standard interpretation for IDRiD's segmentation task, not "unannotated") —
that channel is left all-zero.
"""
from __future__ import annotations

import os
from pathlib import Path

# See src/data/augmentations.py for why this must precede the albumentations
# import — a network version-check that costs 2s-40s per (re-)import,
# multiplied by every DataLoader worker spawn.
os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")

import albumentations as A  # noqa: E402
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from albumentations.pytorch import ToTensorV2  # noqa: E402
from torch.utils.data import Dataset  # noqa: E402

from src.data.dataset import IMAGENET_MEAN, IMAGENET_STD

LESION_CHANNELS = ("MA", "HE", "EX", "SE", "OD")
# Excludes Optic Disc — for the lesion-only patch-trained model (see
# train_lesion_segmentation_v2.py). OD is a large structure needing
# whole-image context that most lesion-centered patches don't provide, so
# training it jointly with tiny lesions destabilized both (see
# docs/SIH_SUBMISSION_PLAN.md item 3's patch-training note); OD stays on the
# original IDRiD-only whole-image model instead, which already gets it right.
LESION_ONLY_CHANNELS = ("MA", "HE", "EX", "SE")
LESION_NAMES = {
    "MA": "Microaneurysms", "HE": "Haemorrhages", "EX": "Hard Exudates",
    "SE": "Soft Exudates", "OD": "Optic Disc",
}
_FOLDER_NAMES = {
    "MA": "1. Microaneurysms", "HE": "2. Haemorrhages", "EX": "3. Hard Exudates",
    "SE": "4. Soft Exudates", "OD": "5. Optic Disc",
}


def build_index(idrid_segmentation_root: Path, split: str) -> list[dict]:
    """split: 'a. Training Set' or 'b. Testing Set'. IDRiD annotates all 5
    channels per image, so a missing mask file genuinely means "not
    present" — every row is marked fully `valid`."""
    root = Path(idrid_segmentation_root)
    image_dir = root / "1. Original Images" / split
    gt_dir = root / "2. All Segmentation Groundtruths" / split
    rows = []
    for image_path in sorted(image_dir.glob("IDRiD_*.jpg")):
        stem = image_path.stem  # e.g. "IDRiD_01"
        masks = {}
        for code, folder in _FOLDER_NAMES.items():
            mask_path = gt_dir / folder / f"{stem}_{code}.tif"
            if mask_path.is_file():
                masks[code] = mask_path
        rows.append({"image_id": stem, "image_path": image_path, "masks": masks,
                     "valid": set(LESION_CHANNELS)})
    return rows


# DDR's lesion_segmentation split (train/valid/test folders, ~757 images total)
# annotates MA/HE/EX/SE but not Optic Disc — used here purely as bonus
# *training* data on top of IDRiD to relieve the data-scarcity ceiling that
# left Microaneurysms at 0.0 dice with IDRiD's 54 images alone. Never used
# for validation: IDRiD's own official Testing Set remains the sole metric
# so results stay comparable across runs. `valid` excludes "OD" for every
# DDR row — see bce_dice_loss's valid-masking for why that matters (a
# missing-OD-annotation is "unknown", not "absent", and must not be punished
# as a false negative).
DDR_LESION_CHANNELS = ("MA", "HE", "EX", "SE")
_DDR_SPLITS = (("train", "label"), ("valid", "segmentation label"), ("test", "label"))


def build_ddr_index(ddr_lesion_segmentation_root: Path) -> list[dict]:
    root = Path(ddr_lesion_segmentation_root)
    rows = []
    for split, label_dirname in _DDR_SPLITS:
        image_dir = root / split / "image"
        label_dir = root / split / label_dirname
        if not image_dir.is_dir():
            continue
        for image_path in sorted(image_dir.glob("*.jpg")):
            stem = image_path.stem
            masks = {}
            for code in DDR_LESION_CHANNELS:
                mask_path = label_dir / code / f"{stem}.tif"
                if mask_path.is_file():
                    masks[code] = mask_path
            rows.append({"image_id": f"ddr_{split}_{stem}", "image_path": image_path, "masks": masks,
                         "valid": set(DDR_LESION_CHANNELS)})
    return rows


# e-ophtha (e_ophtha_MA + e_ophtha_EX): two separately-collected single-
# lesion datasets (149 MA-annotated + 234 MA-healthy; 47 EX-annotated), each
# only ever annotated for its own lesion type — an "MA" image was never
# checked for EX and vice versa. So unlike DDR (which annotates 4 channels
# per image, just not OD), each e-ophtha row is valid for exactly ONE
# channel. "healthy" folders are genuine negatives (screened and confirmed
# lesion-free for that specific type), not "unknown" — they get an all-zero
# mask with that channel marked valid, same as an annotated-but-empty mask
# would.
def _index_e_ophtha_subset(subset_root: Path, lesion_code: str, positive_dirname: str) -> list[dict]:
    rows = []
    positive_dir = subset_root / positive_dirname
    annotation_dir = subset_root / f"Annotation_{lesion_code}"
    healthy_dir = subset_root / "healthy"

    # dedupe: Windows filesystems are case-insensitive, so globbing both
    # "*.jpg" and "*.JPG" would double-count every file there.
    def _list_images(d: Path) -> list[Path]:
        return sorted({p.resolve() for p in list(d.glob("*.jpg")) + list(d.glob("*.JPG"))})

    if positive_dir.is_dir():
        for patient_dir in sorted(positive_dir.iterdir()):
            if not patient_dir.is_dir():
                continue
            ann_patient_dir = annotation_dir / patient_dir.name
            for image_path in _list_images(patient_dir):
                # EX masks are suffixed "<stem>_EX.png"; MA masks share the exact stem.
                candidates = [ann_patient_dir / f"{image_path.stem}_{lesion_code}.png",
                              ann_patient_dir / f"{image_path.stem}.png"]
                mask_path = next((c for c in candidates if c.is_file()), None)
                masks = {lesion_code: mask_path} if mask_path is not None else {}
                rows.append({"image_id": f"eophtha_{lesion_code}_{patient_dir.name}_{image_path.stem}",
                             "image_path": image_path, "masks": masks, "valid": {lesion_code}})

    if healthy_dir.is_dir():
        for patient_dir in sorted(healthy_dir.iterdir()):
            if not patient_dir.is_dir():
                continue
            for image_path in _list_images(patient_dir):
                rows.append({"image_id": f"eophtha_{lesion_code}_healthy_{patient_dir.name}_{image_path.stem}",
                             "image_path": image_path, "masks": {}, "valid": {lesion_code}})
    return rows


def build_e_ophtha_index(e_ophtha_root: Path) -> list[dict]:
    root = Path(e_ophtha_root)
    rows = []
    ma_root = root / "e_ophtha_MA" / "e_optha_MA"
    if ma_root.is_dir():
        rows += _index_e_ophtha_subset(ma_root, "MA", "MA")
    ex_root = root / "e_ophtha_EX" / "e_optha_EX"
    if ex_root.is_dir():
        rows += _index_e_ophtha_subset(ex_root, "EX", "EX")
    return rows


def compute_pos_weights_from_rows(rows: list[dict], cap: float = 50.0) -> torch.Tensor:
    """Per-channel BCE pos_weight = background_px / lesion_px, capped (an
    uncapped ratio like Microaneurysms' ~935 would blow up gradients on any
    single false negative). Rows lacking annotation for a channel (e.g. DDR's
    rows for "OD") are skipped entirely for that channel's count, rather than
    counted as all-background — that would bias the weight toward under-
    estimating true prevalence."""
    positive = {c: 0 for c in LESION_CHANNELS}
    total = {c: 0 for c in LESION_CHANNELS}
    for row in rows:
        image = cv2.imread(str(row["image_path"]))
        h, w = image.shape[:2]
        for code in LESION_CHANNELS:
            if code not in row["valid"]:
                continue
            mask_path = row["masks"].get(code)
            total[code] += h * w
            if mask_path is not None:
                m = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)
                if m.ndim == 3:
                    m = m[..., 0]
                positive[code] += int((m > 0).sum())
    weights = []
    for code in LESION_CHANNELS:
        pos = max(positive[code], 1)
        neg = total[code] - positive[code]
        weights.append(min(neg / pos, cap))
    return torch.tensor(weights, dtype=torch.float32)


def compute_pos_weights(idrid_segmentation_root: Path, split: str, cap: float = 50.0) -> torch.Tensor:
    """IDRiD-only convenience wrapper, kept for backward compatibility."""
    rows = build_index(Path(idrid_segmentation_root), split)
    return compute_pos_weights_from_rows(rows, cap)


def apply_clahe_rgb(image: np.ndarray, clip_limit: float = 2.5, tile_grid_size: tuple[int, int] = (8, 8)) -> np.ndarray:
    """Contrast-limited adaptive histogram equalization on the L channel of
    LAB space — standard fundus-image enhancement (boosts local contrast for
    small, low-contrast lesions like microaneurysms and haemorrhages against
    the retinal background) without distorting hue like per-channel-RGB CLAHE
    would. Also directly serves PS 26038 item 1's "illumination normalization"
    requirement, not just a segmentation-training trick."""
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l_enhanced = clahe.apply(l_channel)
    enhanced = cv2.merge((l_enhanced, a_channel, b_channel))
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)


def build_train_transform(image_size: int) -> A.Compose:
    """Heavier augmentation than the DR-grading FundusAug pipeline — with
    only 54 training images, augmentation is carrying much more weight here.
    additional_targets registers each lesion channel as its own mask so
    albumentations applies the identical geometric transform to all of them
    in sync with the image."""
    return A.Compose(
        [
            A.RandomResizedCrop(size=(image_size, image_size), scale=(0.7, 1.0), ratio=(0.9, 1.1), p=1.0),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.Affine(rotate=(-20, 20), p=0.5),
            A.HueSaturationValue(hue_shift_limit=10, sat_shift_limit=20, val_shift_limit=10, p=0.5),
            A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
            A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ToTensorV2(),
        ],
        additional_targets={f"mask_{c}": "mask" for c in LESION_CHANNELS},
    )


def build_eval_transform(image_size: int) -> A.Compose:
    return A.Compose(
        [
            A.Resize(image_size, image_size),
            A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ToTensorV2(),
        ],
        additional_targets={f"mask_{c}": "mask" for c in LESION_CHANNELS},
    )


def build_patch_transform(channels: tuple[str, ...] = LESION_CHANNELS) -> A.Compose:
    """For patches already cropped to the target size at native resolution
    (see PatchLesionSegmentationDataset) — no further resize/crop, just
    augmentation. Lighter geometric augmentation than build_train_transform:
    a lesion-centered patch is already a "hard" (informative) sample, and
    aggressive scale/rotation risks cropping tiny MA lesions out of frame
    entirely after the fact."""
    return A.Compose(
        [
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.Affine(rotate=(-15, 15), p=0.3, border_mode=cv2.BORDER_REFLECT101),
            A.HueSaturationValue(hue_shift_limit=10, sat_shift_limit=20, val_shift_limit=10, p=0.5),
            A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
            A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ToTensorV2(),
        ],
        additional_targets={f"mask_{c}": "mask" for c in channels},
    )


class IDRiDSegmentationDataset(Dataset):
    def __init__(self, idrid_segmentation_root: str, split: str, image_size: int, transform: A.Compose):
        self.rows = build_index(Path(idrid_segmentation_root), split)
        if not self.rows:
            raise FileNotFoundError(f"no IDRiD segmentation images found under {idrid_segmentation_root}/{split}")
        self.image_size = image_size
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int):
        row = self.rows[idx]
        image = apply_clahe_rgb(cv2.cvtColor(cv2.imread(str(row["image_path"])), cv2.COLOR_BGR2RGB))
        h, w = image.shape[:2]

        mask_kwargs = {}
        for code in LESION_CHANNELS:
            mask_path = row["masks"].get(code)
            if mask_path is not None:
                m = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)
                if m.ndim == 3:
                    m = m[..., 0]
                mask = (m > 0).astype(np.float32)
            else:
                mask = np.zeros((h, w), dtype=np.float32)
            mask_kwargs[f"mask_{code}"] = mask

        transformed = self.transform(image=image, **mask_kwargs)
        image_t = transformed["image"]
        mask_t = torch.stack([transformed[f"mask_{c}"] for c in LESION_CHANNELS], dim=0).float()
        return image_t, mask_t, row["image_id"]


class MergedLesionSegmentationDataset(Dataset):
    """Training-only dataset combining rows from multiple sources (IDRiD +
    DDR) that may not all annotate every channel. Returns a per-sample
    `valid` vector alongside the mask so the loss can skip channels a given
    source doesn't annotate (see bce_dice_loss's valid-masking in
    train_lesion_segmentation.py) instead of training against a fabricated
    "definitely absent" label. Never use this for validation — IDRiD's own
    Testing Set (via IDRiDSegmentationDataset) stays the single comparable
    metric across runs."""

    def __init__(self, rows: list[dict], image_size: int, transform: A.Compose):
        self.rows = rows
        self.image_size = image_size
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int):
        row = self.rows[idx]
        image = apply_clahe_rgb(cv2.cvtColor(cv2.imread(str(row["image_path"])), cv2.COLOR_BGR2RGB))
        h, w = image.shape[:2]

        mask_kwargs = {}
        for code in LESION_CHANNELS:
            mask_path = row["masks"].get(code)
            if mask_path is not None:
                m = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)
                if m.ndim == 3:
                    m = m[..., 0]
                mask = (m > 0).astype(np.float32)
            else:
                mask = np.zeros((h, w), dtype=np.float32)
            mask_kwargs[f"mask_{code}"] = mask

        transformed = self.transform(image=image, **mask_kwargs)
        image_t = transformed["image"]
        mask_t = torch.stack([transformed[f"mask_{c}"] for c in LESION_CHANNELS], dim=0).float()
        valid_t = torch.tensor([1.0 if c in row["valid"] else 0.0 for c in LESION_CHANNELS], dtype=torch.float32)
        return image_t, mask_t, valid_t, row["image_id"]


# Priority order for choosing which lesion to center a patch on, when a row
# has more than one present: rarest/smallest first. This is specifically
# what whole-image 512x512 training can't do — Microaneurysms are 2-5px at
# native resolution and vanish under a ~3-8x downsample to 512, so no volume
# of whole-image data can teach the model to see them. Cropping a
# patch_size-sized window at *native* resolution, centered on an actual MA
# pixel, keeps that lesion at its real size in the training signal.
_PATCH_CENTER_PRIORITY = ("MA", "HE", "SE", "EX", "OD")


class PatchLesionSegmentationDataset(Dataset):
    """Training-only dataset that crops fixed-size patches from images at
    their NATIVE resolution (no whole-image downsample first), oversampling
    patches centered on lesion pixels — see module note above. Falls back to
    a random crop location when a row has no annotated positive pixels
    (DDR/e-ophtha "healthy" rows, or plain random negatives for background
    diversity) or on the (1 - pos_sample_prob) draw.

    Never use for validation — same reasoning as MergedLesionSegmentationDataset."""

    def __init__(self, rows: list[dict], patch_size: int, transform: A.Compose, pos_sample_prob: float = 0.8,
                 channels: tuple[str, ...] = LESION_CHANNELS):
        self.rows = rows
        self.patch_size = patch_size
        self.transform = transform
        self.pos_sample_prob = pos_sample_prob
        self.channels = channels

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int):
        row = self.rows[idx]
        image = apply_clahe_rgb(cv2.cvtColor(cv2.imread(str(row["image_path"])), cv2.COLOR_BGR2RGB))
        h, w = image.shape[:2]

        masks = {}
        for code in self.channels:
            mask_path = row["masks"].get(code)
            if mask_path is not None:
                m = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)
                if m.ndim == 3:
                    m = m[..., 0]
                masks[code] = (m > 0).astype(np.uint8)
            else:
                masks[code] = np.zeros((h, w), dtype=np.uint8)

        ps = self.patch_size
        # Upscale (rare: only smaller-than-patch source images) so a full
        # patch is always extractable.
        if h < ps or w < ps:
            scale = ps / min(h, w)
            new_w, new_h = int(np.ceil(w * scale)), int(np.ceil(h * scale))
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            for code in self.channels:
                masks[code] = cv2.resize(masks[code], (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            h, w = new_h, new_w

        center = None
        if np.random.random() < self.pos_sample_prob:
            for code in _PATCH_CENTER_PRIORITY:
                if code not in self.channels or code not in row["valid"]:
                    continue
                ys, xs = np.nonzero(masks[code])
                if len(ys) > 0:
                    i = np.random.randint(len(ys))
                    center = (int(ys[i]), int(xs[i]))
                    break

        if center is None:
            cy = np.random.randint(0, h) if h > 0 else 0
            cx = np.random.randint(0, w) if w > 0 else 0
            center = (cy, cx)

        half = ps // 2
        y0 = int(np.clip(center[0] - half, 0, max(h - ps, 0)))
        x0 = int(np.clip(center[1] - half, 0, max(w - ps, 0)))
        y1, x1 = y0 + ps, x0 + ps

        image_patch = image[y0:y1, x0:x1]
        mask_kwargs = {f"mask_{code}": masks[code][y0:y1, x0:x1].astype(np.float32) for code in self.channels}

        transformed = self.transform(image=image_patch, **mask_kwargs)
        image_t = transformed["image"]
        mask_t = torch.stack([transformed[f"mask_{c}"] for c in self.channels], dim=0).float()
        valid_t = torch.tensor([1.0 if c in row["valid"] else 0.0 for c in self.channels], dtype=torch.float32)
        return image_t, mask_t, valid_t, row["image_id"]
