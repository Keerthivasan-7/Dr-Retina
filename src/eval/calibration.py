"""Temperature scaling (Guo et al. 2017) — the standard, cheapest fix for
softmax overconfidence. Cross-entropy-trained networks' raw softmax outputs
are well documented to NOT be calibrated probabilities (PS 26038 explicitly
asks for "calibrated confidence scores", so raw argmax-softmax doesn't
satisfy that on its own). Fits a single scalar T on internal val logits,
never on the locked external sets.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class TemperatureScaler(nn.Module):
    def __init__(self):
        super().__init__()
        self.log_temperature = nn.Parameter(torch.zeros(1))

    @property
    def temperature(self) -> torch.Tensor:
        return self.log_temperature.exp()

    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        return logits / self.temperature


def fit_temperature(logits: torch.Tensor, labels: torch.Tensor, max_iter: int = 100) -> float:
    """logits/labels from internal val only. Returns the fitted temperature."""
    scaler = TemperatureScaler()
    optimizer = torch.optim.LBFGS(scaler.parameters(), lr=0.05, max_iter=max_iter)
    criterion = nn.CrossEntropyLoss()

    def closure():
        optimizer.zero_grad()
        loss = criterion(scaler(logits), labels)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(scaler.temperature.item())


def expected_calibration_error(probs: torch.Tensor, labels: torch.Tensor, n_bins: int = 15) -> float:
    """Standard ECE: bins predictions by confidence, compares mean confidence
    to actual accuracy per bin. Lower is better-calibrated."""
    confidences, predictions = probs.max(dim=1)
    accuracies = predictions.eq(labels)
    bin_boundaries = torch.linspace(0, 1, n_bins + 1)
    ece = torch.zeros(1)
    for lo, hi in zip(bin_boundaries[:-1], bin_boundaries[1:]):
        in_bin = (confidences > lo) & (confidences <= hi)
        prop_in_bin = in_bin.float().mean()
        if prop_in_bin.item() > 0:
            acc_in_bin = accuracies[in_bin].float().mean()
            conf_in_bin = confidences[in_bin].mean()
            ece += torch.abs(conf_in_bin - acc_in_bin) * prop_in_bin
    return float(ece.item())
