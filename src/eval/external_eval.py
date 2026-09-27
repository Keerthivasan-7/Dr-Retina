"""P0.6 — external validation harness. Build this before any further modeling.

Loads a DR-grading checkpoint, runs it on the internal val split plus both
locked external test sets (IDRiD, Messidor-2), and writes a report stating
the internal-vs-external gap explicitly. Metrics are reported both before and
after the FIQA quality gate (if a FIQA checkpoint is supplied) so the gate
can't hide difficult external cases.

This is the file that makes "internal QWK 0.87, external QWK 0.61" an honest,
reproducible number instead of a claim. No numeric threshold on this script
itself — P0.6's gate is just that this report exists and is complete.

Run:
  python -m src.eval.external_eval --checkpoint reports/checkpoints/p0_baseline_resnet50/best.pt \
      --run-id p0_baseline
  # optionally add: --fiqa-checkpoint reports/checkpoints/p0_fiqa_effnet_b0/best.pt
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common import DATA_SPLITS, FIQA_CLASSES, ICDR_CLASSES, NUM_ICDR_CLASSES, REPORTS_DIR  # noqa: E402
from src.data.dataset import ImageLabelDataset  # noqa: E402
from src.data.preprocess import circular_crop_and_resize  # noqa: E402
from src.eval.metrics import confusion, quadratic_weighted_kappa, referable_dr_metrics  # noqa: E402
from src.models.dr_backbone import build_dr_model  # noqa: E402
from src.models.fiqa import build_fiqa_model  # noqa: E402


@torch.no_grad()
def run_inference(model, loader: DataLoader, device) -> dict:
    model.eval()
    all_preds, all_labels, all_probs = [], [], []
    for images, labels in loader:
        images = images.to(device, non_blocking=True, memory_format=torch.channels_last)
        probs = torch.softmax(model(images), dim=1).cpu().numpy()
        all_probs.append(probs)
        all_preds.append(probs.argmax(axis=1))
        all_labels.append(labels.numpy())
    return {
        "y_pred": np.concatenate(all_preds),
        "y_true": np.concatenate(all_labels),
        "y_prob": np.concatenate(all_probs),
    }


@torch.no_grad()
def run_fiqa_gate(fiqa_model, loader: DataLoader, device) -> np.ndarray:
    """Returns a boolean 'accept' mask (Good or Usable) aligned with loader order."""
    fiqa_model.eval()
    reject_idx = FIQA_CLASSES.index("Reject")
    accepted = []
    for images, _ in loader:
        images = images.to(device, non_blocking=True, memory_format=torch.channels_last)
        preds = torch.softmax(fiqa_model(images), dim=1).argmax(dim=1).cpu().numpy()
        accepted.append(preds != reject_idx)
    return np.concatenate(accepted)


def format_confusion_md(cm: np.ndarray, classes: list[str]) -> str:
    header = "| true\\pred | " + " | ".join(classes) + " |"
    sep = "|" + "---|" * (len(classes) + 1)
    rows = [header, sep]
    for i, cls in enumerate(classes):
        rows.append("| " + cls + " | " + " | ".join(str(v) for v in cm[i]) + " |")
    return "\n".join(rows)


def evaluate_dataset(model, csv_path: Path, image_size: int, batch_size: int, device, num_workers: int,
                     preprocess=None) -> dict | None:
    if not csv_path.exists():
        return None
    ds = ImageLabelDataset(str(csv_path), image_size=image_size, preprocess=preprocess)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=True)
    result = run_inference(model, loader, device)
    result["loader"] = loader
    result["csv_path"] = csv_path
    return result


def build_report_section(name: str, result: dict, fiqa_model=None, fiqa_image_size: int | None = None,
                         device=None, num_workers: int = 4) -> tuple[str, float, dict]:
    y_true, y_pred = result["y_true"], result["y_pred"]
    qwk = quadratic_weighted_kappa(y_true, y_pred)
    ref = referable_dr_metrics(y_true, y_pred)
    cm = confusion(y_true, y_pred, NUM_ICDR_CLASSES)

    lines = [
        f"### {name}",
        "",
        f"- n = {len(y_true)}",
        f"- 5-class QWK: **{qwk:.4f}**",
        f"- Referable-DR (>= moderate NPDR) sensitivity: **{ref['sensitivity']:.4f}**, "
        f"specificity: {ref['specificity']:.4f}, PPV: {ref['ppv']:.4f}, NPV: {ref['npv']:.4f}",
        f"- Referable-DR confusion: TP={ref['tp']} TN={ref['tn']} FP={ref['fp']} FN={ref['fn']}",
        "",
        "Confusion matrix (5-class):",
        "",
        format_confusion_md(cm, ICDR_CLASSES),
        "",
    ]

    if fiqa_model is not None:
        # FIQA is trained at its own resolution (normally 224px); never run
        # its checkpoint through the DR model's 512px loader.
        fiqa_ds = ImageLabelDataset(str(result["csv_path"]), image_size=fiqa_image_size)
        fiqa_loader = DataLoader(fiqa_ds, batch_size=result["loader"].batch_size, shuffle=False,
                                 num_workers=num_workers, pin_memory=True)
        accept_mask = run_fiqa_gate(fiqa_model, fiqa_loader, device)
        rejection_rate = 1.0 - accept_mask.mean()
        rejected_grades = np.bincount(y_true[~accept_mask], minlength=NUM_ICDR_CLASSES)
        lines += [
            f"**After FIQA gate** (rejection rate: {rejection_rate:.2%}):",
            "",
        ]
        if accept_mask.sum() > 0:
            y_true_g, y_pred_g = y_true[accept_mask], y_pred[accept_mask]
            qwk_g = quadratic_weighted_kappa(y_true_g, y_pred_g)
            ref_g = referable_dr_metrics(y_true_g, y_pred_g)
            lines += [
                f"- n = {accept_mask.sum()} (of {len(y_true)})",
                f"- 5-class QWK (post-gate): **{qwk_g:.4f}**",
                f"- Referable-DR sensitivity (post-gate): **{ref_g['sensitivity']:.4f}**, "
                f"specificity: {ref_g['specificity']:.4f}",
            ]
        lines += [
            "- DR-grade distribution of rejected images: "
            + ", ".join(f"{cls}={c}" for cls, c in zip(ICDR_CLASSES, rejected_grades)),
            "",
        ]

    return "\n".join(lines), qwk, ref


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, help="DR grading model checkpoint (.pt)")
    parser.add_argument("--fiqa-checkpoint", default=None, help="optional FIQA checkpoint for before/after-gate reporting")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument(
        "--allow-missing-datasets", action="store_true",
        help="debug-only: produce an incomplete report when a required split CSV is absent",
    )
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True

    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    cfg = ckpt["config"]
    model = build_dr_model(
        backbone=cfg["model"]["backbone"], num_classes=cfg["model"]["num_classes"], pretrained=False,
    ).to(device)
    model.load_state_dict(ckpt["model_state"])
    if device.type == "cuda":
        model = model.to(memory_format=torch.channels_last)
    image_size = cfg["data"]["image_size"]

    fiqa_model = None
    fiqa_image_size = None
    if args.fiqa_checkpoint:
        fiqa_ckpt = torch.load(args.fiqa_checkpoint, map_location=device, weights_only=False)
        fiqa_model = build_fiqa_model(pretrained=False).to(device)
        fiqa_model.load_state_dict(fiqa_ckpt["model_state"])
        if device.type == "cuda":
            fiqa_model = fiqa_model.to(memory_format=torch.channels_last)
        fiqa_model.eval()
        fiqa_image_size = fiqa_ckpt["config"]["data"]["image_size"]

    datasets = {
        "Internal val": DATA_SPLITS / "val.csv",
        "External: IDRiD": DATA_SPLITS / "external_test_idrid.csv",
        "External: Messidor-2": DATA_SPLITS / "external_test_messidor2.csv",
    }

    sections = []
    qwk_by_name = {}
    for name, csv_path in datasets.items():
        preprocess = circular_crop_and_resize if name.startswith("External:") else None
        result = evaluate_dataset(model, csv_path, image_size, args.batch_size, device, args.num_workers, preprocess)
        if result is None:
            if not args.allow_missing_datasets:
                raise FileNotFoundError(
                    f"required evaluation split is missing: {csv_path}. "
                    "Use --allow-missing-datasets only for local plumbing checks."
                )
            sections.append(f"### {name}\n\n_SKIPPED: {csv_path} not found._\n")
            continue
        section_md, qwk, _ref = build_report_section(
            name, result, fiqa_model, fiqa_image_size, device, args.num_workers
        )
        sections.append(section_md)
        qwk_by_name[name] = qwk

    gap_lines = []
    internal_qwk = qwk_by_name.get("Internal val")
    if internal_qwk is not None:
        for ext_name in ("External: IDRiD", "External: Messidor-2"):
            if ext_name in qwk_by_name:
                gap = internal_qwk - qwk_by_name[ext_name]
                gap_lines.append(
                    f"- Internal QWK {internal_qwk:.4f} vs {ext_name} QWK {qwk_by_name[ext_name]:.4f} "
                    f"-> **gap = {gap:.4f}**"
                )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"eval_{args.run_id}.md"
    report = [
        f"# External validation report — {args.run_id}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Checkpoint: `{args.checkpoint}`",
        f"FIQA checkpoint: `{args.fiqa_checkpoint or 'none — before/after-gate metrics not computed'}`",
        "",
        "## Internal-vs-external gap",
        "",
        *(gap_lines or ["_Not enough data to compute a gap (need internal val + at least one external set)._"]),
        "",
        "## Per-dataset results",
        "",
        *sections,
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(f"\nWrote {report_path}")
    print("\n".join(gap_lines))


if __name__ == "__main__":
    main()
