"""Probe the largest training batch size that fits in GPU memory for a given
config, then rewrite that config's batch_size in place.

Built for maximizing T4 (16GB) utilization on a second/parallel Colab
account running P1 (docs/SIH_SUBMISSION_PLAN.md item 1) — the checked-in
p1_augmented_colab.yaml used batch_size=16, chosen conservatively without a
memory probe; this finds how much headroom the T4 actually has and uses it,
which shortens wall-clock per epoch without changing what the model learns.

Builds the exact same model / optimizer / AMP / channels_last setup as
train_baseline.py, runs one real forward+backward+optimizer.step() at each
candidate batch size (doubling until OOM, then binary-searching the gap),
and applies a safety margin so the picked size survives the *validation*
batch too (val uses the same batch_size, no gradients, so it never needs
more memory than a train step — no separate check needed) and normal
memory fragmentation across a long run.

Run: python -m src.train.find_max_batch_size --config configs/p1_augmented_colab_t4max.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
import torch.nn as nn
import yaml
from torch.optim import AdamW

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common import NUM_ICDR_CLASSES  # noqa: E402
from src.models.dr_backbone import build_dr_model  # noqa: E402

SAFETY_MARGIN = 0.85  # keep batch size at 85% of the largest size that fit, for fragmentation/other processes


def try_batch_size(cfg: dict, batch_size: int, device: torch.device) -> bool:
    """Returns True if one train step at this batch size completes without OOM."""
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)
    try:
        model = build_dr_model(
            backbone=cfg["model"]["backbone"],
            num_classes=cfg["model"]["num_classes"],
            pretrained=False,  # skip downloading pretrained weights just to probe memory
            dropout=cfg["model"].get("dropout", 0.3),
        ).to(device)
        model = model.to(memory_format=torch.channels_last)
        optimizer = AdamW(model.parameters(), lr=cfg["train"]["lr"], weight_decay=cfg["train"]["weight_decay"])
        scaler = torch.amp.GradScaler("cuda")
        criterion = nn.CrossEntropyLoss()

        image_size = cfg["data"]["image_size"]
        dummy_images = torch.randn(batch_size, 3, image_size, image_size, device=device).to(
            memory_format=torch.channels_last
        )
        dummy_labels = torch.randint(0, NUM_ICDR_CLASSES, (batch_size,), device=device)

        optimizer.zero_grad(set_to_none=True)
        with torch.autocast("cuda", dtype=torch.float16):
            logits = model(dummy_images)
            loss = criterion(logits, dummy_labels)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        torch.cuda.synchronize()

        peak_gb = torch.cuda.max_memory_allocated(device) / (1024**3)
        print(f"  batch_size={batch_size}: OK (peak {peak_gb:.2f} GB)")
        del model, optimizer, dummy_images, dummy_labels, logits, loss
        torch.cuda.empty_cache()
        return True
    except torch.cuda.OutOfMemoryError:
        print(f"  batch_size={batch_size}: OOM")
        torch.cuda.empty_cache()
        return False


def find_max_batch_size(cfg: dict, device: torch.device, start: int = 8, max_cap: int = 256) -> int:
    print("probing max batch size (doubling until OOM)...")
    last_ok = None
    size = start
    while size <= max_cap:
        if try_batch_size(cfg, size, device):
            last_ok = size
            size *= 2
        else:
            break
    if last_ok is None:
        raise RuntimeError(f"even batch_size={start} OOM'd — reduce image_size or start smaller")

    if size > max_cap:
        return last_ok

    print(f"binary-searching between {last_ok} (OK) and {size} (OOM)...")
    lo, hi = last_ok, size
    while hi - lo > 2:
        mid = (lo + hi) // 2
        mid -= mid % 2  # keep it even, plays nicer with some cuDNN kernels
        if mid <= lo:
            break
        if try_batch_size(cfg, mid, device):
            lo = mid
        else:
            hi = mid
    return lo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--start", type=int, default=8)
    parser.add_argument("--max-cap", type=int, default=256)
    parser.add_argument("--dry-run", action="store_true", help="probe only, don't rewrite the config file")
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("no CUDA GPU visible — nothing to probe")

    device = torch.device("cuda")
    torch.backends.cudnn.benchmark = True
    print(f"GPU: {torch.cuda.get_device_name(device)}")
    total_gb = torch.cuda.get_device_properties(device).total_memory / (1024**3)
    print(f"total VRAM: {total_gb:.1f} GB\n")

    cfg = yaml.safe_load(open(args.config))
    max_ok = find_max_batch_size(cfg, device, start=args.start, max_cap=args.max_cap)
    chosen = max(args.start, int(max_ok * SAFETY_MARGIN))
    chosen -= chosen % 2
    print(f"\nlargest batch size that fit: {max_ok}")
    print(f"chosen batch size ({int(SAFETY_MARGIN * 100)}% safety margin): {chosen}")

    if args.dry_run:
        print("(--dry-run: not writing config)")
        return

    cfg["train"]["batch_size"] = chosen
    with open(args.config, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    print(f"wrote batch_size={chosen} to {args.config}")


if __name__ == "__main__":
    main()
