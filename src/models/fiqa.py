"""P0.4 — FIQA baseline: cheap EfficientNet-B0 3-class quality gate."""
from __future__ import annotations

import timm
import torch.nn as nn

from src.common import FIQA_CLASSES


def build_fiqa_model(pretrained: bool = True) -> nn.Module:
    return timm.create_model(
        "efficientnet_b0",
        pretrained=pretrained,
        num_classes=len(FIQA_CLASSES),
    )
