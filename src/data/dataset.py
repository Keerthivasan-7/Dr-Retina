"""Shared torch Dataset for CSV-driven image/label pairs.

Used by both P0.4 (FIQA) and P0.5+ (DR grading) training/eval scripts so the
image-loading path is identical everywhere.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


class ImageLabelDataset(Dataset):
    """Reads a CSV with at least `processed_path` (or `src_path`) and `label`
    columns. `transform` is an albumentations Compose applied to the RGB
    numpy image; if None, a plain resize+normalize+to-tensor is used.

    `image_root`, if given, is joined onto each row's path. This is a no-op
    when a row's path is already absolute *for the current OS* (pathlib's
    `/` operator returns the right-hand side unchanged in that case), which
    is what makes the same CSV portable: a relative path (e.g. from a CSV
    built on a different machine/OS, such as a Colab checkout) gets resolved
    against image_root, while an existing absolute path is left alone.
    """

    def __init__(self, csv_path: str, image_size: int = 512, transform=None, path_col: str | None = None,
                 preprocess=None, image_root: str | None = None):
        self.df = pd.read_csv(csv_path)
        self.path_col = path_col or ("processed_path" if "processed_path" in self.df.columns else "src_path")
        self.image_size = image_size
        self.transform = transform
        self.preprocess = preprocess
        self.image_root = Path(image_root) if image_root else None

    def __len__(self) -> int:
        return len(self.df)

    def _load_image(self, path: str) -> np.ndarray:
        resolved = str(self.image_root / path) if self.image_root is not None else path
        image = cv2.imread(resolved)
        if image is None:
            raise FileNotFoundError(f"could not read image: {resolved}")
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        image = self._load_image(row[self.path_col])
        if self.preprocess is not None:
            image = self.preprocess(image, self.image_size)

        if self.transform is not None:
            image = self.transform(image=image)["image"]
        else:
            if image.shape[0] != self.image_size or image.shape[1] != self.image_size:
                image = cv2.resize(image, (self.image_size, self.image_size), interpolation=cv2.INTER_AREA)
            image = image.astype(np.float32) / 255.0
            image = (image - np.array(IMAGENET_MEAN, dtype=np.float32)) / np.array(IMAGENET_STD, dtype=np.float32)
            image = torch.from_numpy(image.transpose(2, 0, 1)).float()

        label = int(row["label"])
        return image, label
