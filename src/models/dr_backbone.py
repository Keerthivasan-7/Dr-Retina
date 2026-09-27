"""P0.5 — DR grading backbone: ResNet-50 or EfficientNet-B0, plain softmax head.

Ordinal (CORAL) and multi-task lesion-fusion heads are P2 — not here.
"""
from __future__ import annotations

import timm
import torch.nn as nn

from src.common import NUM_ICDR_CLASSES

SUPPORTED_BACKBONES = ("resnet50", "efficientnet_b0")


def build_dr_model(
    backbone: str = "resnet50",
    num_classes: int = NUM_ICDR_CLASSES,
    pretrained: bool = True,
    dropout: float = 0.3,
) -> nn.Module:
    if backbone not in SUPPORTED_BACKBONES:
        raise ValueError(f"backbone must be one of {SUPPORTED_BACKBONES}, got {backbone!r}")
    return timm.create_model(
        backbone,
        pretrained=pretrained,
        num_classes=num_classes,
        drop_rate=dropout,
    )
