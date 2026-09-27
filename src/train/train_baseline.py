"""P0.5 — DR grading baseline: plain softmax ResNet-50/EfficientNet-B0,
class-weighted cross-entropy, no ordinal loss (that's P2).

Run: python -m src.train.train_baseline --config configs/baseline_resnet50.yaml
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
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common import NUM_ICDR_CLASSES, PROJECT_ROOT  # noqa: E402
from src.data.augmentations import build_fundus_aug_transform  # noqa: E402
from src.data.dataset import ImageLabelDataset  # noqa: E402
from src.eval.metrics import confusion, macro_f1, per_class_recall, quadratic_weighted_kappa  # noqa: E402
from src.models.dr_backbone import build_dr_model  # noqa: E402
from src.reproducibility import run_metadata, seed_everything  # noqa: E402
from src.train.engine import class_weights_inverse_frequency, evaluate, train_one_epoch  # noqa: E402


def build_scheduler(optimizer, cfg: dict):
    epochs = cfg["train"]["epochs"]
    warmup = cfg["train"].get("warmup_epochs", 0)
    if warmup <= 0:
        return CosineAnnealingLR(optimizer, T_max=epochs)
    warmup_sched = LinearLR(optimizer, start_factor=0.1, total_iters=warmup)
    cosine_sched = CosineAnnealingLR(optimizer, T_max=epochs - warmup)
    return SequentialLR(optimizer, schedulers=[warmup_sched, cosine_sched], milestones=[warmup])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--resume", action="store_true",
                         help="resume from <checkpoint_dir>/last.pt (model+optimizer+scheduler+scaler state)")
    args = parser.parse_args()

    cfg = yaml.safe_load(open(args.config))
    seed_everything(cfg["seed"])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}")
    if device.type == "cuda":
        # Inputs are a fixed 512x512 every step (no augmentation in this
        # config), so cuDNN can safely autotune the fastest conv algorithms
        # for that exact shape instead of using its generic default.
        torch.backends.cudnn.benchmark = True

    image_size = cfg["data"]["image_size"]
    image_root = cfg["data"].get("image_root")
    # P1: FundusAug-style augmentation applies to the training split only —
    # val must stay untransformed so it's directly comparable to the P0
    # controlled-baseline run (docs/IMPLEMENTATION_PLAN.md's P1 selection rule).
    train_transform = build_fundus_aug_transform(image_size) if cfg["data"].get("augment") else None
    train_ds = ImageLabelDataset(
        cfg["data"]["train_csv"], image_size=image_size, image_root=image_root, transform=train_transform
    )
    val_ds = ImageLabelDataset(cfg["data"]["val_csv"], image_size=image_size, image_root=image_root)

    num_workers = cfg["train"]["num_workers"]
    loader_kwargs = {"num_workers": num_workers, "pin_memory": True}
    if num_workers > 0:
        # Keep worker processes alive across epochs (avoids re-spawn cost)
        # and let them stay a few batches ahead of the GPU.
        loader_kwargs["persistent_workers"] = True
        loader_kwargs["prefetch_factor"] = 4
    train_loader = DataLoader(
        train_ds, batch_size=cfg["train"]["batch_size"], shuffle=True, drop_last=True, **loader_kwargs
    )
    val_loader = DataLoader(
        val_ds, batch_size=cfg["train"]["batch_size"], shuffle=False, **loader_kwargs
    )

    model = build_dr_model(
        backbone=cfg["model"]["backbone"],
        num_classes=cfg["model"]["num_classes"],
        pretrained=cfg["model"]["pretrained"],
        dropout=cfg["model"].get("dropout", 0.3),
    ).to(device)
    if device.type == "cuda":
        # channels_last pairs well with AMP on Ampere/Ada tensor cores
        # (this GPU's RTX 4050) — same math, faster conv layout.
        model = model.to(memory_format=torch.channels_last)

    class_weights = class_weights_inverse_frequency(train_ds.df["label"].values, NUM_ICDR_CLASSES, device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    optimizer = AdamW(model.parameters(), lr=cfg["train"]["lr"], weight_decay=cfg["train"]["weight_decay"])
    scheduler = build_scheduler(optimizer, cfg)
    scaler = torch.amp.GradScaler("cuda") if (cfg["train"]["amp"] and device.type == "cuda") else None

    checkpoint_dir = PROJECT_ROOT / cfg["train"]["checkpoint_dir"]
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    metadata = run_metadata(args.config, [cfg["data"]["train_csv"], cfg["data"]["val_csv"]])
    (checkpoint_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    best_qwk = -1.0
    epochs_since_improvement = 0
    patience = cfg["train"].get("early_stop_patience", 8)
    history = []
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
        best_qwk = resume_ckpt["best_qwk"]
        epochs_since_improvement = resume_ckpt["epochs_since_improvement"]
        history = resume_ckpt["history"]
        start_epoch = resume_ckpt["epoch"] + 1
        print(f"resumed from {last_ckpt_path}: completed epoch {resume_ckpt['epoch']}, "
              f"best val QWK so far={best_qwk:.4f}, restarting at epoch {start_epoch}")
        if start_epoch > cfg["train"]["epochs"]:
            print("nothing to do: checkpoint's epoch already meets/exceeds cfg epochs")
            return

    for epoch in range(start_epoch, cfg["train"]["epochs"] + 1):
        train_loss = train_one_epoch(
            model, train_loader, optimizer, criterion, device, scaler, cfg["train"].get("grad_clip_norm")
        )
        val_result = evaluate(model, val_loader, criterion, device)
        scheduler.step()

        # float(): cohen_kappa_score/f1_score return numpy scalars, which
        # newer torch (2.6+, weights_only=True default) can't unpickle from a
        # checkpoint without an explicit allowlist — keep plain Python types
        # in anything that gets torch.save'd.
        qwk = float(quadratic_weighted_kappa(val_result["y_true"], val_result["y_pred"]))
        f1 = float(macro_f1(val_result["y_true"], val_result["y_pred"]))
        recall = per_class_recall(val_result["y_true"], val_result["y_pred"], NUM_ICDR_CLASSES)
        cm = confusion(val_result["y_true"], val_result["y_pred"], NUM_ICDR_CLASSES)

        print(f"\nepoch {epoch}/{cfg['train']['epochs']}  train_loss={train_loss:.4f}  val_loss={val_result['loss']:.4f}")
        print(f"  val QWK={qwk:.4f}  macro-F1={f1:.4f}  per-class recall={np.round(recall, 3).tolist()}")
        print(f"  confusion matrix:\n{cm}")

        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_result["loss"], "val_qwk": qwk, "val_macro_f1": f1})

        is_best = qwk > best_qwk
        if is_best:
            best_qwk = qwk
            epochs_since_improvement = 0
        else:
            epochs_since_improvement += 1

        # Full resumable state, overwritten every epoch regardless of whether
        # it was the best one — this is what --resume reads, separate from
        # best.pt (kept model-only/lean since external_eval.py etc. load it).
        # Note: DataLoader shuffle RNG state isn't snapshotted, so a resumed
        # run won't see the exact same batch order a single uninterrupted
        # run would have — a normal, accepted limitation of epoch-level resume.
        torch.save(
            {"model_state": model.state_dict(), "optimizer_state": optimizer.state_dict(),
             "scheduler_state": scheduler.state_dict(),
             "scaler_state": scaler.state_dict() if scaler is not None else None,
             "epoch": epoch, "best_qwk": best_qwk, "epochs_since_improvement": epochs_since_improvement,
             "history": history, "config": cfg, "metadata": metadata},
            last_ckpt_path,
        )

        if is_best:
            torch.save(
                {"model_state": model.state_dict(), "epoch": epoch, "val_qwk": qwk, "config": cfg,
                 "metadata": metadata},
                checkpoint_dir / "best.pt",
            )
            print(f"  -> new best val QWK={qwk:.4f}, checkpoint saved")
        elif epochs_since_improvement >= patience:
            print(f"early stopping: no val QWK improvement for {patience} epochs")
            break

    with open(checkpoint_dir / "history.json", "w") as f:
        json.dump(history, f, indent=2)

    print(f"\ndone. best val QWK={best_qwk:.4f}. Acceptance gate (P0.5) is >= 0.85 on internal val.")
    if best_qwk < 0.85:
        print("GATE NOT MET: fix data/label issues before touching architecture (this is a data-quality gate).")


if __name__ == "__main__":
    main()
