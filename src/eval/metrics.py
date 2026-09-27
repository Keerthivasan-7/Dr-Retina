"""Shared metrics used by both training (per-epoch logging) and the external
validation harness, so a "QWK" reported during training means the same thing
as a "QWK" reported in an external eval report.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import cohen_kappa_score, confusion_matrix, f1_score, recall_score

from src.common import REFERABLE_THRESHOLD


def quadratic_weighted_kappa(y_true, y_pred) -> float:
    return cohen_kappa_score(y_true, y_pred, weights="quadratic")


def macro_f1(y_true, y_pred) -> float:
    return f1_score(y_true, y_pred, average="macro")


def per_class_recall(y_true, y_pred, num_classes: int) -> np.ndarray:
    return recall_score(y_true, y_pred, average=None, labels=list(range(num_classes)))


def confusion(y_true, y_pred, num_classes: int) -> np.ndarray:
    return confusion_matrix(y_true, y_pred, labels=list(range(num_classes)))


def within_one_grade_accuracy(y_true, y_pred) -> float:
    """Fraction of predictions within one ICDR severity grade of the true
    label. This is the metric P2.1 uses to judge CORAL's real benefit under
    domain shift — kept here so both phases share one definition."""
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    return float(np.mean(np.abs(y_true - y_pred) <= 1))


def dice_coefficient(pred_mask: np.ndarray, true_mask: np.ndarray, eps: float = 1e-6) -> float:
    """Per-image Dice for one binary lesion mask; caller averages across images/classes."""
    pred_mask = np.asarray(pred_mask).astype(bool)
    true_mask = np.asarray(true_mask).astype(bool)
    intersection = np.logical_and(pred_mask, true_mask).sum()
    denom = pred_mask.sum() + true_mask.sum()
    if denom == 0:
        return 1.0  # both empty: correct by definition, not a division-by-zero error
    return float(2.0 * intersection / (denom + eps))


def referable_dr_metrics(y_true, y_pred, threshold: int = REFERABLE_THRESHOLD) -> dict:
    """Binarizes at `threshold` (default: moderate-or-worse NPDR) and reports
    sensitivity/specificity/PPV/NPV — the clinically-relevant numbers, not
    just 5-class accuracy."""
    y_true_bin = (np.asarray(y_true) >= threshold).astype(int)
    y_pred_bin = (np.asarray(y_pred) >= threshold).astype(int)

    tp = int(np.sum((y_true_bin == 1) & (y_pred_bin == 1)))
    tn = int(np.sum((y_true_bin == 0) & (y_pred_bin == 0)))
    fp = int(np.sum((y_true_bin == 0) & (y_pred_bin == 1)))
    fn = int(np.sum((y_true_bin == 1) & (y_pred_bin == 0)))

    sensitivity = tp / (tp + fn) if (tp + fn) else float("nan")
    specificity = tn / (tn + fp) if (tn + fp) else float("nan")
    ppv = tp / (tp + fp) if (tp + fp) else float("nan")
    npv = tn / (tn + fn) if (tn + fn) else float("nan")

    return {
        "sensitivity": sensitivity,
        "specificity": specificity,
        "ppv": ppv,
        "npv": npv,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }
