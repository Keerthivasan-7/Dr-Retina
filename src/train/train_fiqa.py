"""P0.4 — FIQA baseline training: EfficientNet-B0 3-class quality gate on EyeQ.

Cheap/fast by design — don't over-invest here. Acceptance gate is AUROC >= 0.90
for Good-vs-Reject on an EyeQ held-out split (see src/eval/external_eval.py for
the separate, non-tuned DRIMDB external report).

Run: python -m src.train.train_fiqa --config configs/fiqa_efficientnet_b0.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import yaml
from sklearn.metrics import roc_auc_score
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common import FIQA_CLASSES, PROJECT_ROOT  # noqa: E402
from src.data.dataset import ImageLabelDataset  # noqa: E402
from src.models.fiqa import build_fiqa_model  # noqa: E402
from src.reproducibility import run_metadata, seed_everything  # noqa: E402
from src.train.engine import evaluate, train_one_epoch  # noqa: E402


def good_vs_reject_auroc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Binarizes Good(0) vs Reject(2), dropping Usable(1) rows — matches the
    plan's P0.4 acceptance-gate metric definition exactly."""
    good_idx = FIQA_CLASSES.index("Good")
    reject_idx = FIQA_CLASSES.index("Reject")
    mask = np.isin(y_true, [good_idx, reject_idx])
    y_bin = (y_true[mask] == reject_idx).astype(int)
    score = y_prob[mask][:, reject_idx]
    return roc_auc_score(y_bin, score)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--resume", action="store_true",
                         help="resume from <checkpoint_dir>/last.pt (model+optimizer+scheduler+scaler state)")
    args = parser.parse_args()

    cfg = yaml.safe_load(open(args.config))
    seed_everything(cfg["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True

    image_size = cfg["data"]["image_size"]
    image_root = cfg["data"].get("image_root")
    train_ds = ImageLabelDataset(cfg["data"]["train_csv"], image_size=image_size, image_root=image_root)
    val_ds = ImageLabelDataset(cfg["data"]["val_csv"], image_size=image_size, image_root=image_root)

    num_workers = cfg["train"]["num_workers"]
    loader_kwargs = {"num_workers": num_workers, "pin_memory": True}
    if num_workers > 0:
        loader_kwargs["persistent_workers"] = True
        loader_kwargs["prefetch_factor"] = 4
    train_loader = DataLoader(train_ds, batch_size=cfg["train"]["batch_size"], shuffle=True,
                               drop_last=True, **loader_kwargs)
    val_loader = DataLoader(val_ds, batch_size=cfg["train"]["batch_size"], shuffle=False, **loader_kwargs)

    model = build_fiqa_model(pretrained=cfg["model"]["pretrained"]).to(device)
    if device.type == "cuda":
        model = model.to(memory_format=torch.channels_last)
    criterion = nn.CrossEntropyLoss()
    optimizer = AdamW(model.parameters(), lr=cfg["train"]["lr"], weight_decay=cfg["train"]["weight_decay"])
    scheduler = CosineAnnealingLR(optimizer, T_max=cfg["train"]["epochs"])
    scaler = torch.amp.GradScaler("cuda") if (cfg["train"]["amp"] and device.type == "cuda") else None

    checkpoint_dir = PROJECT_ROOT / cfg["train"]["checkpoint_dir"]
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    metadata = run_metadata(args.config, [cfg["data"]["train_csv"], cfg["data"]["val_csv"]])
    (checkpoint_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    best_auroc = -1.0
    start_epoch = 1

    last_ckpt_path = checkpoint_dir / "last.pt"
    if args.resume:
        if not last_ckpt_path.exists():
            raise FileNotFoundError(f"--resume given but no checkpoint at {last_ckpt_path}")
        resume_ckpt = torch.load(last_ckpt_path, map_location=device, weights_only=False)
        model.load_state_dict(resume_ckpt["model_state"])
        optimizer.load_state_dict(resume_ckpt["optimizer_state"])
        scheduler.load_state_dict(resume_ckpt["scheduler_state"])
        if scaler is not None and resume_ckpt.get("scaler_state") is not None:
            scaler.load_state_dict(resume_ckpt["scaler_state"])
        best_auroc = resume_ckpt["best_auroc"]
        start_epoch = resume_ckpt["epoch"] + 1
        print(f"resumed from {last_ckpt_path}: completed epoch {resume_ckpt['epoch']}, "
              f"best AUROC so far={best_auroc:.4f}, restarting at epoch {start_epoch}")
        if start_epoch > cfg["train"]["epochs"]:
            print("nothing to do: checkpoint's epoch already meets/exceeds cfg epochs")
            return

    for epoch in range(start_epoch, cfg["train"]["epochs"] + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer, criterion, device, scaler, None)
        val_result = evaluate(model, val_loader, criterion, device)
        scheduler.step()

        auroc = float(good_vs_reject_auroc(val_result["y_true"], val_result["y_prob"]))
        print(f"epoch {epoch}/{cfg['train']['epochs']}  train_loss={train_loss:.4f}  "
              f"val_loss={val_result['loss']:.4f}  Good-vs-Reject AUROC={auroc:.4f}")

        is_best = auroc > best_auroc
        if is_best:
            best_auroc = auroc

        torch.save(
            {"model_state": model.state_dict(), "optimizer_state": optimizer.state_dict(),
             "scheduler_state": scheduler.state_dict(),
             "scaler_state": scaler.state_dict() if scaler is not None else None,
             "epoch": epoch, "best_auroc": best_auroc, "config": cfg, "metadata": metadata},
            last_ckpt_path,
        )

        if is_best:
            torch.save({"model_state": model.state_dict(), "epoch": epoch, "auroc": auroc, "config": cfg,
                        "metadata": metadata},
                       checkpoint_dir / "best.pt")

    print(f"\ndone. best Good-vs-Reject AUROC={best_auroc:.4f}. Acceptance gate (P0.4) is >= 0.90.")
    if best_auroc < 0.90:
        print("GATE NOT MET.")


if __name__ == "__main__":
    main()
