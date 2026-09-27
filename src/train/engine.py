"""Shared train/eval loop used by both train_fiqa.py and train_baseline.py.

Keeping one engine means AMP handling, class weighting, and checkpointing
behave identically for the FIQA gate and the DR grading model.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader
from tqdm import tqdm


def class_weights_inverse_frequency(labels: np.ndarray, num_classes: int, device) -> torch.Tensor:
    weights = compute_class_weight(
        class_weight="balanced",
        classes=np.arange(num_classes),
        y=labels,
    )
    return torch.tensor(weights, dtype=torch.float32, device=device)


def train_one_epoch(model, loader: DataLoader, optimizer, criterion, device, scaler, grad_clip_norm: float | None):
    model.train()
    total_loss = 0.0
    for images, labels in tqdm(loader, desc="train", leave=False):
        images = images.to(device, non_blocking=True, memory_format=torch.channels_last)
        labels = labels.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)

        with torch.autocast(device_type="cuda" if device.type == "cuda" else "cpu", enabled=scaler is not None):
            logits = model(images)
            loss = criterion(logits, labels)

        if scaler is not None:
            scaler.scale(loss).backward()
            if grad_clip_norm:
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(model.parameters(), grad_clip_norm)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            if grad_clip_norm:
                nn.utils.clip_grad_norm_(model.parameters(), grad_clip_norm)
            optimizer.step()

        total_loss += loss.item() * images.size(0)
    return total_loss / len(loader.dataset)


@torch.no_grad()
def evaluate(model, loader: DataLoader, criterion, device):
    model.eval()
    total_loss = 0.0
    all_preds, all_labels, all_probs = [], [], []
    for images, labels in tqdm(loader, desc="val", leave=False):
        images = images.to(device, non_blocking=True, memory_format=torch.channels_last)
        labels = labels.to(device, non_blocking=True)
        logits = model(images)
        loss = criterion(logits, labels)
        total_loss += loss.item() * images.size(0)

        probs = torch.softmax(logits, dim=1)
        preds = probs.argmax(dim=1)
        all_preds.append(preds.cpu().numpy())
        all_labels.append(labels.cpu().numpy())
        all_probs.append(probs.cpu().numpy())

    return {
        "loss": total_loss / len(loader.dataset),
        "y_pred": np.concatenate(all_preds),
        "y_true": np.concatenate(all_labels),
        "y_prob": np.concatenate(all_probs),
    }
