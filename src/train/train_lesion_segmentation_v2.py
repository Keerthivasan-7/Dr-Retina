"""P2.2d — lesion segmentation v2: pretrained-encoder U-Net + Focal Tversky
Loss, MA/HE/EX/SE only (Optic Disc dropped — see LESION_ONLY_CHANNELS's
docstring in src/data/segmentation_dataset.py for why).

Built after two earlier attempts (docs/SIH_SUBMISSION_PLAN.md item 3) left
Microaneurysms at 0.0 dice:
  1. IDRiD-only (54 images), whole-image 512x512: BCE+Dice loss, compact
     from-scratch U-Net. MA never learned — plausible data-scarcity ceiling.
  2. IDRiD+DDR merged (811 images), still whole-image: MA still 0.0 despite
     15x more data — proved data volume alone doesn't fix it. Diagnosis: MA
     lesions are 2-5px at native resolution and vanish under the ~3-8x
     downsample to 512x512, before the model ever sees them.
  3. +e-ophtha (1274 images total), native-resolution lesion-centered
     patches: MA STILL 0.0, but this run is confounded — Optic Disc (a
     large structure needing whole-image context patches don't reliably
     provide) went unstable under patch training and dominated the
     mean-dice early-stopping metric, triggering premature stopping (13
     epochs) before the patch approach could really be evaluated for MA.

This version fixes all three remaining suspects at once, each backed by
published practice for this exact problem (microaneurysm/small-lesion
segmentation under extreme class imbalance):
  - Drop OD entirely (already solved separately) so nothing can destabilize
    the small-lesion training or its early-stopping metric.
  - Focal Tversky Loss (Abraham & Khan 2018) instead of BCE+Dice: tunable
    alpha/beta asymmetrically penalize false negatives more than false
    positives (recall matters more than precision when the lesion is 0.1% of
    pixels), plus a focal term (gamma) that up-weights hard/rare examples.
  - ImageNet-pretrained ResNet-34 encoder (via segmentation_models_pytorch)
    instead of a from-scratch compact U-Net — transfer learning for the
    subtle low-contrast texture discrimination MA needs, standard in the
    published microaneurysm-segmentation literature.

Run: python -m src.train.train_lesion_segmentation_v2 --config configs/lesion_segmentation_v2.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import yaml
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.data.segmentation_dataset import (  # noqa: E402
    LESION_ONLY_CHANNELS, PatchLesionSegmentationDataset, build_ddr_index, build_e_ophtha_index,
    build_eval_transform, build_index, build_patch_transform,
)
from src.eval.metrics import dice_coefficient  # noqa: E402
from src.models.lesion_unet import build_pretrained_lesion_model  # noqa: E402
from src.reproducibility import run_metadata, seed_everything  # noqa: E402

NUM_CHANNELS = len(LESION_ONLY_CHANNELS)  # 4: MA, HE, EX, SE


def focal_tversky_loss(logits: torch.Tensor, targets: torch.Tensor, valid: torch.Tensor,
                        alpha: float = 0.3, beta: float = 0.7, gamma: float = 0.75,
                        eps: float = 1e-6) -> torch.Tensor:
    """Per-channel Focal Tversky Loss (Abraham & Khan, 2018), valid-masked
    the same way as bce_dice_loss in train_lesion_segmentation.py. beta > alpha
    weights false negatives more heavily than false positives — recall
    matters more than precision for a lesion that's a tiny fraction of
    pixels, where under-predicting is the failure mode we're actually
    fighting (as opposed to over-predicting, which plain BCE with a high
    pos_weight already risks). gamma > 1 focuses training on
    hard/low-Tversky channels instead of ones already doing fine."""
    probs = torch.sigmoid(logits)
    valid_expanded = valid.unsqueeze(-1).unsqueeze(-1)  # [B,C,1,1]
    probs_v = probs * valid_expanded
    targets_v = targets * valid_expanded
    dims = (0, 2, 3)
    tp = (probs_v * targets_v).sum(dim=dims)
    fp = (probs_v * (1 - targets_v)).sum(dim=dims)
    fn = ((1 - probs_v) * targets_v).sum(dim=dims)
    tversky = (tp + eps) / (tp + alpha * fp + beta * fn + eps)
    return (1.0 - tversky).clamp(min=eps).pow(gamma).mean()


def train_one_epoch(model, loader, optimizer, device, scaler, alpha, beta, gamma) -> float:
    model.train()
    total_loss = 0.0
    for images, masks, valid, _ids in tqdm(loader, desc="train", leave=False):
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)
        valid = valid.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda" if device.type == "cuda" else "cpu", enabled=scaler is not None):
            logits = model(images)
            loss = focal_tversky_loss(logits, masks, valid, alpha, beta, gamma)
        if scaler is not None:
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            optimizer.step()
        total_loss += loss.item() * images.size(0)
    return total_loss / len(loader.dataset)


@torch.no_grad()
def evaluate(model, loader, device, alpha, beta, gamma) -> dict:
    """loader yields IDRiD's full 5-channel (MA,HE,EX,SE,OD) val masks —
    only the first 4 (== LESION_ONLY_CHANNELS, same order) are used here."""
    model.eval()
    total_loss = 0.0
    per_channel_dice = {c: [] for c in LESION_ONLY_CHANNELS}
    all_valid = torch.ones(loader.batch_size, NUM_CHANNELS, device=device)
    for images, masks_full, _ids in tqdm(loader, desc="val", leave=False):
        images = images.to(device, non_blocking=True)
        masks = masks_full[:, :NUM_CHANNELS].to(device, non_blocking=True)
        logits = model(images)
        valid = all_valid[:images.size(0)]
        loss = focal_tversky_loss(logits, masks, valid, alpha, beta, gamma)
        total_loss += loss.item() * images.size(0)
        preds = (torch.sigmoid(logits) > 0.5).cpu().numpy()
        masks_np = masks.cpu().numpy()
        for i, code in enumerate(LESION_ONLY_CHANNELS):
            for b in range(preds.shape[0]):
                per_channel_dice[code].append(dice_coefficient(preds[b, i], masks_np[b, i]))
    mean_dice = {c: float(np.mean(v)) for c, v in per_channel_dice.items()}
    return {"loss": total_loss / len(loader.dataset), "dice": mean_dice}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    cfg = yaml.safe_load(open(args.config))
    seed_everything(cfg["seed"])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}")
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True

    image_size = cfg["data"]["image_size"]
    patch_size = cfg["data"]["patch_size"]
    root = cfg["data"]["idrid_segmentation_root"]
    ddr_root = cfg["data"].get("ddr_lesion_segmentation_root")
    e_ophtha_root = cfg["data"].get("e_ophtha_root")

    train_rows = build_index(Path(root), "a. Training Set")
    idrid_train_count = len(train_rows)
    ddr_rows = build_ddr_index(Path(ddr_root)) if ddr_root else []
    e_ophtha_rows = build_e_ophtha_index(Path(e_ophtha_root)) if e_ophtha_root else []
    train_rows = train_rows + ddr_rows + e_ophtha_rows

    train_ds = PatchLesionSegmentationDataset(
        train_rows, patch_size, build_patch_transform(LESION_ONLY_CHANNELS), channels=LESION_ONLY_CHANNELS,
    )
    # Reuse IDRiDSegmentationDataset's underlying eval transform/loader shape
    # (5-channel) — evaluate() slices to the first 4 channels.
    from src.data.segmentation_dataset import IDRiDSegmentationDataset
    val_ds = IDRiDSegmentationDataset(root, "b. Testing Set", image_size, build_eval_transform(image_size))

    print(f"train images: {len(train_ds)} (IDRiD: {idrid_train_count}, DDR bonus: {len(ddr_rows)}, "
          f"e-ophtha bonus: {len(e_ophtha_rows)}), val (IDRiD's own test split) images: {len(val_ds)}")
    print(f"channels: {LESION_ONLY_CHANNELS} (Optic Disc dropped — see module docstring)")

    num_workers = cfg["train"]["num_workers"]
    loader_kwargs = {"num_workers": num_workers, "pin_memory": True}
    if num_workers > 0:
        loader_kwargs["persistent_workers"] = True
    train_loader = DataLoader(train_ds, batch_size=cfg["train"]["batch_size"], shuffle=True, drop_last=False,
                               **loader_kwargs)
    val_loader = DataLoader(val_ds, batch_size=cfg["train"]["batch_size"], shuffle=False, **loader_kwargs)

    model = build_pretrained_lesion_model(
        num_classes=NUM_CHANNELS, encoder_name=cfg["model"].get("encoder_name", "resnet34"),
    ).to(device)
    if device.type == "cuda":
        model = model.to(memory_format=torch.channels_last)

    optimizer = AdamW(model.parameters(), lr=cfg["train"]["lr"], weight_decay=cfg["train"]["weight_decay"])
    scheduler = CosineAnnealingLR(optimizer, T_max=cfg["train"]["epochs"])
    scaler = torch.amp.GradScaler("cuda") if (cfg["train"]["amp"] and device.type == "cuda") else None

    tversky_alpha = cfg["train"].get("tversky_alpha", 0.3)
    tversky_beta = cfg["train"].get("tversky_beta", 0.7)
    tversky_gamma = cfg["train"].get("tversky_gamma", 0.75)
    print(f"Focal Tversky Loss: alpha={tversky_alpha} beta={tversky_beta} gamma={tversky_gamma}")

    checkpoint_dir = Path(cfg["train"]["checkpoint_dir"])
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    metadata = run_metadata(args.config, [])
    (checkpoint_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    best_mean_dice = -1.0
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
        best_mean_dice = resume_ckpt["best_mean_dice"]
        start_epoch = resume_ckpt["epoch"] + 1
        print(f"resumed from {last_ckpt_path}: completed epoch {resume_ckpt['epoch']}, "
              f"best mean dice so far={best_mean_dice:.4f}, restarting at epoch {start_epoch}")

    early_stop_patience = cfg["train"].get("early_stop_patience")
    epochs_since_improvement = 0

    history = []
    for epoch in range(start_epoch, cfg["train"]["epochs"] + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer, device, scaler,
                                      tversky_alpha, tversky_beta, tversky_gamma)
        val_result = evaluate(model, val_loader, device, tversky_alpha, tversky_beta, tversky_gamma)
        scheduler.step()

        mean_dice = float(np.mean(list(val_result["dice"].values())))
        print(f"epoch {epoch}/{cfg['train']['epochs']}  train_loss={train_loss:.4f}  val_loss={val_result['loss']:.4f}  "
              f"mean_dice={mean_dice:.4f}  per_class_dice={ {k: round(v, 3) for k, v in val_result['dice'].items()} }")
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_result["loss"],
                         "mean_dice": mean_dice, "per_class_dice": val_result["dice"]})

        is_best = mean_dice > best_mean_dice
        if is_best:
            best_mean_dice = mean_dice
            epochs_since_improvement = 0
        else:
            epochs_since_improvement += 1

        torch.save(
            {"model_state": model.state_dict(), "optimizer_state": optimizer.state_dict(),
             "scheduler_state": scheduler.state_dict(),
             "scaler_state": scaler.state_dict() if scaler is not None else None,
             "epoch": epoch, "best_mean_dice": best_mean_dice, "config": cfg, "metadata": metadata},
            last_ckpt_path,
        )
        if is_best:
            torch.save({"model_state": model.state_dict(), "epoch": epoch, "mean_dice": mean_dice, "config": cfg,
                        "metadata": metadata},
                       checkpoint_dir / "best.pt")
            print(f"  -> new best mean dice={mean_dice:.4f}, checkpoint saved")

        if early_stop_patience and epochs_since_improvement >= early_stop_patience:
            print(f"  -> no improvement for {epochs_since_improvement} epochs (patience={early_stop_patience}), "
                  f"stopping early at epoch {epoch}")
            break

    with open(checkpoint_dir / "history.json", "w") as f:
        json.dump(history, f, indent=2)
    print(f"\ndone. best mean dice={best_mean_dice:.4f} "
          f"(proof-of-concept scale: {len(train_ds)} training images — not a validated clinical result). "
          f"best.pt reflects the best-epoch checkpoint, not necessarily the last one. "
          f"Optic Disc is NOT in this model — use the original IDRiD-only checkpoint for OD.")


if __name__ == "__main__":
    main()
