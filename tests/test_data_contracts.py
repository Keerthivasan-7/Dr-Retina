from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.make_fiqa_splits import make_fiqa_splits
from src.data.make_splits import patient_level_split, validate_external_set, validate_internal_pool
from src.data.preprocess import circular_crop_and_resize


def test_patient_split_keeps_patient_eyes_together():
    frame = pd.DataFrame({
        "patient_id": ["a", "a", "b", "c", "d", "e", "f", "g", "h", "i"],
        "label": [0, 0, 0, 0, 1, 1, 1, 1, 0, 1],
        "source": ["eyepacs"] * 10,
    })
    train, val = patient_level_split(frame, 0.2, 42)
    assert set(train.patient_id).isdisjoint(set(val.patient_id))


def test_external_set_rejects_invalid_label(tmp_path: Path):
    image = tmp_path / "image.png"
    image.write_bytes(b"fixture")
    frame = pd.DataFrame({"image_id": ["x"], "processed_path": [str(image)], "label": [5]})
    with pytest.raises(ValueError, match="ICDR"):
        validate_external_set("idrid", frame)


def test_internal_pool_rejects_locked_source():
    frame = pd.DataFrame({"source": ["idrid"], "label": [0]})
    with pytest.raises(ValueError, match="locked"):
        validate_internal_pool(frame)


def test_fiqa_split_requires_all_classes():
    frame = pd.DataFrame({"label": [0, 0, 1, 1]})
    with pytest.raises(ValueError, match="Good, Usable, and Reject"):
        make_fiqa_splits(frame)


def test_fundus_preprocess_returns_square_image():
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    image[4:28, 8:40] = 180
    result = circular_crop_and_resize(image, 64)
    assert result.shape == (64, 64, 3)
