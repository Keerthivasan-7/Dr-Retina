"""Referable-DR (ICDR >= 2) operating-point tuning.

PS 26038's acceptance bar is sensitivity > 0.90 AND specificity > 0.85 for
referable DR, simultaneously. The 5-class argmax decision boundary used
everywhere else in this pipeline was never chosen to optimize that specific
binary operating point — this script sweeps a threshold on
P(grade >= REFERABLE_THRESHOLD) instead of trusting argmax, picks the
threshold on INTERNAL VAL ONLY (never touches locked external sets to
choose), then reports that fixed threshold's honest performance on IDRiD and
Messidor-2. This is the cheapest lever available before considering
retraining: it costs one inference pass, not a training run.

Run:
  python -m src.eval.tune_referable_threshold --checkpoint reports/checkpoints/p0_baseline_resnet50/best.pt
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common import DATA_SPLITS, NUM_ICDR_CLASSES, REFERABLE_THRESHOLD, REPORTS_DIR  # noqa: E402
from src.data.preprocess import circular_crop_and_resize  # noqa: E402
from src.eval.external_eval import evaluate_dataset  # noqa: E402
from src.models.dr_backbone import build_dr_model  # noqa: E402

TARGET_SENS = 0.90
TARGET_SPEC = 0.85


def sens_spec_at_threshold(y_true: np.ndarray, referable_prob: np.ndarray, threshold: float) -> tuple[float, float]:
    y_true_bin = (y_true >= REFERABLE_THRESHOLD).astype(int)
    y_pred_bin = (referable_prob >= threshold).astype(int)
    tp = int(np.sum((y_true_bin == 1) & (y_pred_bin == 1)))
    tn = int(np.sum((y_true_bin == 0) & (y_pred_bin == 0)))
    fp = int(np.sum((y_true_bin == 0) & (y_pred_bin == 1)))
    fn = int(np.sum((y_true_bin == 1) & (y_pred_bin == 0)))
    sensitivity = tp / (tp + fn) if (tp + fn) else float("nan")
    specificity = tn / (tn + fp) if (tn + fp) else float("nan")
    return sensitivity, specificity


def sweep(y_true: np.ndarray, referable_prob: np.ndarray) -> list[dict]:
    rows = []
    for t in np.arange(0.02, 0.99, 0.01):
        sens, spec = sens_spec_at_threshold(y_true, referable_prob, t)
        rows.append({"threshold": round(float(t), 2), "sensitivity": sens, "specificity": spec})
    return rows


def choose_threshold(rows: list[dict]) -> tuple[dict, bool]:
    """Prefer a threshold meeting both PS targets simultaneously (maximizing
    sens+spec among those); if none exists, fall back to the Youden-optimal
    point (max sens+spec overall) and say so honestly."""
    meeting_both = [r for r in rows if r["sensitivity"] > TARGET_SENS and r["specificity"] > TARGET_SPEC]
    if meeting_both:
        best = max(meeting_both, key=lambda r: r["sensitivity"] + r["specificity"])
        return best, True
    best = max(rows, key=lambda r: r["sensitivity"] + r["specificity"])
    return best, False


def referable_prob_from_probs(y_prob: np.ndarray) -> np.ndarray:
    return y_prob[:, REFERABLE_THRESHOLD:].sum(axis=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--num-workers", type=int, default=4)
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

    print("running inference on internal val...")
    val_result = evaluate_dataset(model, DATA_SPLITS / "val.csv", image_size, args.batch_size, device, args.num_workers)
    val_referable_prob = referable_prob_from_probs(val_result["y_prob"])
    rows = sweep(val_result["y_true"], val_referable_prob)
    chosen, both_met = choose_threshold(rows)
    threshold = chosen["threshold"]
    print(f"chosen threshold (internal val only): {threshold} "
          f"(val sens={chosen['sensitivity']:.4f} spec={chosen['specificity']:.4f}, "
          f"{'meets both PS targets' if both_met else 'does NOT meet both PS targets — closest achievable point'})")

    print("evaluating that fixed threshold on locked external sets...")
    external_results = {}
    for name, csv_path in (("IDRiD", DATA_SPLITS / "external_test_idrid.csv"),
                            ("Messidor-2", DATA_SPLITS / "external_test_messidor2.csv")):
        result = evaluate_dataset(model, csv_path, image_size, args.batch_size, device, args.num_workers,
                                   preprocess=circular_crop_and_resize)
        if result is None:
            print(f"  SKIPPED {name}: {csv_path} not found")
            continue
        ref_prob = referable_prob_from_probs(result["y_prob"])
        sens, spec = sens_spec_at_threshold(result["y_true"], ref_prob, threshold)
        external_results[name] = (sens, spec, len(result["y_true"]))
        print(f"  {name}: n={len(result['y_true'])} sensitivity={sens:.4f} specificity={spec:.4f}")

    # argmax baseline for comparison, same data, same model, just the old decision rule
    argmax_sens, argmax_spec = sens_spec_at_threshold(
        val_result["y_true"], (val_result["y_pred"] >= REFERABLE_THRESHOLD).astype(float), 0.5
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "referable_threshold_tuning.md"
    lines = [
        "# Referable-DR operating-point tuning",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Checkpoint: `{args.checkpoint}`",
        "",
        "PS 26038 target: sensitivity > 0.90 AND specificity > 0.85 for referable DR "
        "(ICDR grade >= 2), simultaneously.",
        "",
        "Threshold chosen on internal val only, never on the locked external sets — this "
        "avoids turning IDRiD/Messidor-2 into a tuning signal, which would invalidate them "
        "as held-out evidence.",
        "",
        f"## Chosen threshold: P(grade>=2) >= {threshold}",
        "",
        f"- Internal val: n={len(val_result['y_true'])}, "
        f"sensitivity={chosen['sensitivity']:.4f}, specificity={chosen['specificity']:.4f}, "
        f"{'meets both PS targets' if both_met else '**does not meet both PS targets** — reported as the closest achievable point by thresholding alone'}",
        f"- Argmax baseline (old decision rule) on the same internal val: "
        f"sensitivity={argmax_sens:.4f}, specificity={argmax_spec:.4f}",
        "",
        "## Fixed threshold applied to locked external sets (honest, not re-tuned per-set)",
        "",
    ]
    for name, (sens, spec, n) in external_results.items():
        meets = sens > TARGET_SENS and spec > TARGET_SPEC
        lines.append(f"- **{name}** (n={n}): sensitivity={sens:.4f}, specificity={spec:.4f} "
                     f"{'✓ meets both PS targets' if meets else '✗ does not meet both PS targets'}")
    lines += [
        "",
        "## Full threshold sweep (internal val)",
        "",
        "| threshold | sensitivity | specificity |",
        "|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['threshold']} | {r['sensitivity']:.4f} | {r['specificity']:.4f} |")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
