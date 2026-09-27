"""P1 — FundusAug-style domain-generalization augmentation.

Implements the five variation categories docs/IMPLEMENTATION_PLAN.md's P1 section
names explicitly — camera, illumination, crop, blur, compression — as one
albumentations pipeline, gated behind config (`data.augment: true`; see
configs/p1_augmented*.yaml). Only ever applied to the training split: val and
external stay untransformed so the controlled-baseline-vs-augmented comparison
the plan calls for is measuring the augmentation, not a moved goalpost.

Ranges are deliberately mild-to-moderate, not paper-exact FundusAug parameters:
aggressive enough to expose the model to real capture variation, conservative
enough that a human grader would still assign the same ICDR label to the
augmented image (heavy augmentation on a medical image risks silently making
the label wrong, not just harder).
"""
from __future__ import annotations

import os

# Must be set before `import albumentations`: it does a network version-check
# on import (PyPI), which silently costs 2s-40s per call on flaky/firewalled
# connections — and DataLoader workers re-import this module on every spawn,
# so with num_workers>0 this was costing minutes per epoch. Set unconditionally
# here so it's not dependent on the calling shell's environment.
os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")

import albumentations as A  # noqa: E402
from albumentations.pytorch import ToTensorV2  # noqa: E402

from src.data.dataset import IMAGENET_MEAN, IMAGENET_STD


def build_fundus_aug_transform(image_size: int) -> A.Compose:
    return A.Compose([
        # Crop: mild re-framing/zoom (camera positioning differences), stays
        # within the circular fundus disc rather than cutting into it.
        A.RandomResizedCrop(size=(image_size, image_size), scale=(0.85, 1.0), ratio=(0.95, 1.05), p=0.5),
        # Unconditional: RandomResizedCrop above is probabilistic (p=0.5), so
        # without this, a skipped crop leaves the image at its native size —
        # harmless when that happens to already equal image_size, but wrong
        # in general and exactly what breaks batch collation otherwise.
        A.Resize(image_size, image_size),
        # Camera: color/white-balance response differences across fundus camera hardware.
        A.HueSaturationValue(hue_shift_limit=10, sat_shift_limit=20, val_shift_limit=10, p=0.5),
        # Illumination: exposure/lighting variation during capture.
        A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
        A.RandomGamma(gamma_limit=(80, 120), p=0.3),
        # Blur: focus/motion quality variation.
        A.OneOf([
            A.Defocus(radius=(1, 4), alias_blur=(0.1, 0.4), p=1.0),
            A.MotionBlur(blur_limit=(3, 5), p=1.0),
        ], p=0.3),
        # Compression: export/storage artifact variation.
        A.ImageCompression(quality_range=(60, 100), p=0.3),
        A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ToTensorV2(),
    ])
