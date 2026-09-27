"""P2.2 — lesion segmentation (Microaneurysms, Haemorrhages, Hard Exudates,
Soft Exudates, Optic Disc) on IDRiD's segmentation split.

Explicitly proof-of-concept scale: IDRiD provides 54 training / 27 testing
images for this task — nowhere near enough for a validated clinical
segmentation model, but enough to produce real per-lesion masks that drive
genuine "found X here, therefore grade Y" explainability text (PS 26038 item
4), instead of a Grad-CAM heatmap alone. Report this scale caveat wherever
these masks are used downstream.

Run: python -m src.train.train_lesion_segmentation --config configs/lesion_segmentation.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.data.segmentation_dataset import (  # noqa: E402
    DDR_LESION_CHANNELS, LESION_CHANNELS, IDRiDSegmentationDataset, MergedLesionSegmentationDataset,
    PatchLesionSegmentationDataset, build_ddr_index, build_e_ophtha_index, build_eval_transform, build_index,
    build_patch_transform, build_train_transform, compute_pos_weights_from_rows,
)
from src.eval.metrics import dice_coefficient  # noqa: E402
from src.models.lesion_unet import build_lesion_model  # noqa: E402
from src.reproducibility import run_metadata, seed_everything  # noqa: E402


def dice_loss_per_channel(logits: torch.Tensor, targets: torch.Tensor, valid: torch.Tensor,
                           eps: float = 1e-6) -> torch.Tensor:
    # valid: [B,C], 1.0 where this sample's ground truth for that channel is
    # known, 0.0 where unannotated (e.g. DDR rows for "OD"). Zeroing both
    # probs and targets for invalid entries drops them from the ratio
    # entirely, rather than training the model toward "always absent" there.
    probs = torch.sigmoid(logits)
    valid_expanded = valid.unsqueeze(-1).unsqueeze(-1)  # [B,C,1,1]
    probs_v = probs * valid_expanded
    targets_v = targets * valid_expanded
    dims = (0, 2, 3)
    intersection = (probs_v * targets_v).sum(dim=dims)
    denom = probs_v.sum(dim=dims) + targets_v.sum(dim=dims)
    dice = (2 * intersection + eps) / (denom + eps)
    return 1.0 - dice  # [C]


def bce_dice_loss(logits: torch.Tensor, targets: torch.Tensor, valid: torch.Tensor,
                   pos_weight: torch.Tensor | None = None) -> torch.Tensor:
    # Per-channel BCE, THEN averaged across channels — not flattened into one
    # global mean. Microaneurysms are ~0.1% of pixels vs Optic Disc's ~1.8%;
    # a flat mean over all (B,C,H,W) elements lets OD/EX's sheer pixel volume
    # dominate the gradient, so the model learns "predict nothing" for MA/HE
    # is nearly loss-free (this is exactly what happened: MA/HE dice sat at
    # 0.0 for 20 straight epochs). Equal per-channel weighting fixes that.
    # pos_weight (per-channel, capped) additionally offsets the within-channel
    # foreground/background imbalance (lesion pixels are rare even within
    # their own channel).
    #
    # valid: [B,C] — DDR-sourced rows don't annotate Optic Disc, so those
    # samples must be excluded from OD's loss entirely (not treated as
    # negatives), else the model gets actively punished for correctly
    # predicting OD on hundreds of images that simply weren't checked for it.
    num_channels = logits.shape[1]
    bce_per_channel = []
    for c in range(num_channels):
        elem = F.binary_cross_entropy_with_logits(
            logits[:, c], targets[:, c],
            pos_weight=pos_weight[c] if pos_weight is not None else None,
            reduction="none",
        )  # [B,H,W]
        v = valid[:, c].view(-1, 1, 1)  # [B,1,1]
        denom = v.sum() * elem.shape[1] * elem.shape[2]
        if denom > 0:
            bce_per_channel.append((elem * v).sum() / denom)
        else:
            bce_per_channel.append(elem.sum() * 0.0)  # no valid samples this batch — zero, no grad signal
    bce_per_channel = torch.stack(bce_per_channel)
    dice_per_channel = dice_loss_per_channel(logits, targets, valid)
    return (bce_per_channel + dice_per_channel).mean()


def train_one_epoch(model, loader, optimizer, device, scaler, pos_weight) -> float:
    model.train()
    total_loss = 0.0
    for images, masks, valid, _ids in tqdm(loader, desc="train", leave=False):
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)
        valid = valid.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda" if device.type == "cuda" else "cpu", enabled=scaler is not None):
            logits = model(images)
            loss = bce_dice_loss(logits, masks, valid, pos_weight)
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
def evaluate(model, loader, device, pos_weight) -> dict:
    model.eval()
    total_loss = 0.0
    per_channel_dice = {c: [] for c in LESION_CHANNELS}
    all_valid = torch.ones(loader.batch_size, len(LESION_CHANNELS), device=device)
    for images, masks, _ids in tqdm(loader, desc="val", leave=False):
        images, masks = images.to(device, non_blocking=True), masks.to(device, non_blocking=True)
        logits = model(images)
        valid = all_valid[:images.size(0)]  # IDRiD's own Testing Set: every channel always annotated
        loss = bce_dice_loss(logits, masks, valid, pos_weight)
        total_loss += loss.item() * images.size(0)
        preds = (torch.sigmoid(logits) > 0.5).cpu().numpy()
        masks_np = masks.cpu().numpy()
        for i, code in enumerate(LESION_CHANNELS):
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
    root = cfg["data"]["idrid_segmentation_root"]
    ddr_root = cfg["data"].get("ddr_lesion_segmentation_root")
    e_ophtha_root = cfg["data"].get("e_ophtha_root")
    patch_size = cfg["data"].get("patch_size")  # if set, train on native-resolution lesion-centered patches instead

    train_rows = build_index(Path(root), "a. Training Set")
    idrid_train_count = len(train_rows)
    ddr_train_count = 0
    if ddr_root:
        ddr_rows = build_ddr_index(Path(ddr_root))
        ddr_train_count = len(ddr_rows)
        train_rows = train_rows + ddr_rows
    e_ophtha_train_count = 0
    if e_ophtha_root:
        e_ophtha_rows = build_e_ophtha_index(Path(e_ophtha_root))
        e_ophtha_train_count = len(e_ophtha_rows)
        train_rows = train_rows + e_ophtha_rows

    if patch_size:
        train_ds = PatchLesionSegmentationDataset(train_rows, patch_size, build_patch_transform())
        print(f"  patch-based training: {patch_size}x{patch_size} crops at NATIVE resolution, "
              f"lesion-centered 80% of the time (preserves microaneurysm-scale detail lost by whole-image resize)")
    else:
        train_ds = MergedLesionSegmentationDataset(train_rows, image_size, build_train_transform(image_size))
    val_ds = IDRiDSegmentationDataset(root, "b. Testing Set", image_size, build_eval_transform(image_size))
    print(f"train images: {len(train_ds)} (IDRiD: {idrid_train_count}, DDR bonus: {ddr_train_count}, "
          f"e-ophtha bonus: {e_ophtha_train_count}), val (IDRiD's own test split) images: {len(val_ds)}")
    if ddr_train_count:
        print(f"  note: DDR rows annotate {DDR_LESION_CHANNELS} only — Optic Disc loss/pos_weight "
              f"still comes from IDRiD alone (DDR rows excluded via the valid mask)")
    if e_ophtha_train_count:
        print("  note: e-ophtha rows annotate exactly one of {MA, EX} each — the other 4 channels "
              "excluded via the valid mask for those rows")

    pos_weight = compute_pos_weights_from_rows(train_rows).to(device)
    print(f"per-channel BCE pos_weight {dict(zip(LESION_CHANNELS, pos_weight.tolist()))}")

    num_workers = cfg["train"]["num_workers"]
    loader_kwargs = {"num_workers": num_workers, "pin_memory": True}
    if num_workers > 0:
        loader_kwargs["persistent_workers"] = True
    train_loader = DataLoader(train_ds, batch_size=cfg["train"]["batch_size"], shuffle=True, drop_last=False, **loader_kwargs)
    val_loader = DataLoader(val_ds, batch_size=cfg["train"]["batch_size"], shuffle=False, **loader_kwargs)

    model = build_lesion_model(num_classes=len(LESION_CHANNELS), base_channels=cfg["model"]["base_channels"]).to(device)
    if device.type == "cuda":
        model = model.to(memory_format=torch.channels_last)

    optimizer = AdamW(model.parameters(), lr=cfg["train"]["lr"], weight_decay=cfg["train"]["weight_decay"])
    scheduler = CosineAnnealingLR(optimizer, T_max=cfg["train"]["epochs"])
    scaler = torch.amp.GradScaler("cuda") if (cfg["train"]["amp"] and device.type == "cuda") else None

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
        train_loss = train_one_epoch(model, train_loader, optimizer, device, scaler, pos_weight)
        val_result = evaluate(model, val_loader, device, pos_weight)
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
          f"best.pt reflects the best-epoch checkpoint, not necessarily the last one.")


if __name__ == "__main__":
    main()
