"""Run-level reproducibility helpers shared by training entry points."""
from __future__ import annotations

import hashlib
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch


def seed_everything(seed: int) -> None:
    """Seed Python, NumPy, and PyTorch without claiming bitwise portability."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    # Deterministic kernels make experiment comparisons defensible.  Some
    # operations may be slower or unavailable; fail early rather than silently
    # falling back to a non-deterministic result.
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run_metadata(config_path: str | Path, data_csvs: list[str | Path]) -> dict:
    """Return inspectable provenance saved alongside every checkpoint."""
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "git_revision": _git_revision(),
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "data_csv_sha256": {str(path): sha256_file(path) for path in data_csvs},
    }
