"""P3 — Grad-CAM++ attention maps.

Strictly "model attention (coarse)" per README ground rule #5 — this shows
which regions most influenced the predicted class, not detected lesions.
Real lesion-level evidence comes from src/models/lesion_unet.py's
segmentation output (src/explain/report.py combines both).
"""
from __future__ import annotations

import cv2
import numpy as np
import torch
import torch.nn as nn
from pytorch_grad_cam import GradCAMPlusPlus
from pytorch_grad_cam.utils.image import show_cam_on_image

ATTENTION_LABEL = "Model attention (coarse) — not a detected lesion location."


def resolve_target_layer(model: nn.Module, backbone: str) -> nn.Module:
    if backbone == "resnet50":
        return model.layer4[-1]
    if backbone == "efficientnet_b0":
        return model.conv_head
    raise ValueError(f"no known Grad-CAM target layer for backbone {backbone!r}")


def compute_gradcam_overlay(
    model: nn.Module, backbone: str, image_tensor: torch.Tensor, image_rgb_uint8: np.ndarray,
    target_class: int, device: torch.device,
) -> np.ndarray:
    """image_tensor: normalized [1,3,H,W] model input. image_rgb_uint8: the
    same image as displayable RGB uint8 (any size — resized to match here).
    Returns an RGB uint8 array with the heatmap overlaid."""
    target_layer = resolve_target_layer(model, backbone)
    was_training = model.training
    model.eval()
    cam = GradCAMPlusPlus(model=model, target_layers=[target_layer])
    from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
    grayscale_cam = cam(input_tensor=image_tensor.to(device), targets=[ClassifierOutputTarget(target_class)])
    grayscale_cam = grayscale_cam[0]  # [H, W] in the model's input resolution
    if was_training:
        model.train()

    h, w = image_rgb_uint8.shape[:2]
    cam_resized = cv2.resize(grayscale_cam, (w, h))
    rgb_float = image_rgb_uint8.astype(np.float32) / 255.0
    overlay = show_cam_on_image(rgb_float, cam_resized, use_rgb=True)
    return overlay
