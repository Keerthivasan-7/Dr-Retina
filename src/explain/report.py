"""P3/PS-item-4 — combined explainability report: FIQA gate, calibrated DR
grade, Grad-CAM++ attention, and lesion-level evidence, in one annotated
output. This is what PS 26038 item 4 actually asks for — not any single
piece of it alone.

"Ophthalmologist validation in under 30 seconds" (the PS's own framing)
means the report has to be readable at a glance: predicted grade + confidence
first, then the two kinds of visual evidence side by side, each labeled for
what it actually is.

Run:
  python -m src.explain.report --image path/to/fundus.jpg \
      --dr-checkpoint reports/checkpoints/p0_baseline_resnet50/best.pt \
      --fiqa-checkpoint reports/checkpoints/p0_fiqa_effnet_b0/best.pt \
      --lesion-checkpoint reports/checkpoints/p2_lesion_segmentation/best.pt \
      --lesion-v2-checkpoint reports/checkpoints/p2d_lesion_segmentation_v2/best.pt

Two lesion checkpoints, combined: `--lesion-checkpoint` (IDRiD-only, whole-
image, 5-channel) is used for Optic Disc only (0.842 dice — the model that's
actually good at it); `--lesion-v2-checkpoint` (merged IDRiD+DDR+e-ophtha,
pretrained-encoder, Focal Tversky Loss, 4-channel) is used for MA/HE/EX/SE,
which is where it actually improved over the original model — see
docs/SIH_SUBMISSION_PLAN.md item 3 for why these are two separate models
rather than one. Passing only one of the two still works (that one's
channels are used, the other's are simply absent from the report).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common import ICDR_CLASSES, PROJECT_ROOT, REPORTS_DIR  # noqa: E402
from src.data.dataset import IMAGENET_MEAN, IMAGENET_STD  # noqa: E402
from src.data.preprocess import circular_crop_and_resize  # noqa: E402
from src.data.segmentation_dataset import LESION_CHANNELS, LESION_NAMES, LESION_ONLY_CHANNELS  # noqa: E402
from src.explain.gradcam import ATTENTION_LABEL, compute_gradcam_overlay  # noqa: E402
from src.models.dr_backbone import build_dr_model  # noqa: E402
from src.models.fiqa import build_fiqa_model  # noqa: E402
from src.models.lesion_unet import build_lesion_model, build_pretrained_lesion_model  # noqa: E402

FIQA_LABELS = ("Good", "Usable", "Reject")


def _to_model_input(image_rgb: np.ndarray, image_size: int) -> torch.Tensor:
    resized = cv2.resize(image_rgb, (image_size, image_size), interpolation=cv2.INTER_AREA)
    norm = (resized.astype(np.float32) / 255.0 - np.array(IMAGENET_MEAN)) / np.array(IMAGENET_STD)
    return torch.from_numpy(norm.transpose(2, 0, 1)).float().unsqueeze(0)


def generate_report(
    image_path: str, dr_checkpoint: str, fiqa_checkpoint: str | None = None,
    lesion_checkpoint: str | None = None, lesion_v2_checkpoint: str | None = None,
    temperature: float = 1.0, out_dir: str | Path | None = None,
) -> dict:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out_dir = Path(out_dir) if out_dir else REPORTS_DIR / "explainability"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(image_path).stem

    raw_bgr = cv2.imread(str(image_path))
    if raw_bgr is None:
        raise FileNotFoundError(image_path)
    processed_bgr = circular_crop_and_resize(raw_bgr, 512)
    processed_rgb = cv2.cvtColor(processed_bgr, cv2.COLOR_BGR2RGB)

    result: dict = {"image": str(image_path)}

    # 1. FIQA gate
    if fiqa_checkpoint:
        ckpt = torch.load(fiqa_checkpoint, map_location=device, weights_only=False)
        model = build_fiqa_model(pretrained=False).to(device)
        model.load_state_dict(ckpt["model_state"])
        model.eval()
        image_size = ckpt["config"]["data"]["image_size"]
        x = _to_model_input(processed_rgb, image_size).to(device)
        with torch.no_grad():
            probs = torch.softmax(model(x), dim=1)[0].cpu().numpy()
        fiqa_idx = int(probs.argmax())
        result["fiqa"] = {"label": FIQA_LABELS[fiqa_idx], "probs": dict(zip(FIQA_LABELS, probs.tolist()))}
        if FIQA_LABELS[fiqa_idx] == "Reject":
            result["warning"] = "FIQA gate rejected this image (poor quality) — grade below is unreliable."

    # 2. DR grade + calibrated confidence
    ckpt = torch.load(dr_checkpoint, map_location=device, weights_only=False)
    dr_model = build_dr_model(backbone=ckpt["config"]["model"]["backbone"],
                               num_classes=ckpt["config"]["model"]["num_classes"], pretrained=False).to(device)
    dr_model.load_state_dict(ckpt["model_state"])
    dr_model.eval()
    dr_image_size = ckpt["config"]["data"]["image_size"]
    dr_input = _to_model_input(processed_rgb, dr_image_size).to(device)
    with torch.no_grad():
        logits = dr_model(dr_input)
        calibrated_probs = torch.softmax(logits / temperature, dim=1)[0].cpu().numpy()
    pred_grade = int(calibrated_probs.argmax())
    result["dr_grade"] = {
        "grade": pred_grade, "label": ICDR_CLASSES[pred_grade],
        "confidence": float(calibrated_probs[pred_grade]), "temperature_used": temperature,
        "all_probs": dict(zip(ICDR_CLASSES, calibrated_probs.tolist())),
    }

    # 3. Grad-CAM++ — model attention, explicitly labeled as coarse, not lesion detection
    gradcam_overlay = compute_gradcam_overlay(
        dr_model, ckpt["config"]["model"]["backbone"], dr_input, processed_rgb, pred_grade, device,
    )
    gradcam_path = out_dir / f"{stem}_gradcam.png"
    cv2.imwrite(str(gradcam_path), cv2.cvtColor(gradcam_overlay, cv2.COLOR_RGB2BGR))
    result["attention_map"] = {"path": str(gradcam_path), "label": ATTENTION_LABEL}

    # 4. Lesion segmentation — the real, defensible per-lesion evidence.
    # Two models, combined: `lesion_checkpoint` (IDRiD-only, whole-image) is
    # used for Optic Disc only — it's what that model is actually good at
    # (0.842 dice). `lesion_v2_checkpoint` (merged data, pretrained encoder,
    # Focal Tversky Loss) is used for MA/HE/EX/SE — see
    # docs/SIH_SUBMISSION_PLAN.md item 3 for why these are separate models.
    lesion_masks_by_code: dict[str, np.ndarray] = {}

    if lesion_checkpoint:
        lckpt = torch.load(lesion_checkpoint, map_location=device, weights_only=False)
        lesion_model = build_lesion_model(num_classes=len(LESION_CHANNELS),
                                           base_channels=lckpt["config"]["model"]["base_channels"]).to(device)
        lesion_model.load_state_dict(lckpt["model_state"])
        lesion_model.eval()
        lesion_input = _to_model_input(processed_rgb, 512).to(device)
        with torch.no_grad():
            lesion_logits = lesion_model(lesion_input)
            lesion_masks = (torch.sigmoid(lesion_logits) > 0.5)[0].cpu().numpy()
        lesion_masks_by_code["OD"] = lesion_masks[LESION_CHANNELS.index("OD")]

    if lesion_v2_checkpoint:
        v2ckpt = torch.load(lesion_v2_checkpoint, map_location=device, weights_only=False)
        v2_model = build_pretrained_lesion_model(
            num_classes=len(LESION_ONLY_CHANNELS),
            encoder_name=v2ckpt["config"]["model"].get("encoder_name", "resnet34"),
        ).to(device)
        v2_model.load_state_dict(v2ckpt["model_state"])
        v2_model.eval()
        v2_input = _to_model_input(processed_rgb, 512).to(device)
        with torch.no_grad():
            v2_logits = v2_model(v2_input)
            v2_masks = (torch.sigmoid(v2_logits) > 0.5)[0].cpu().numpy()
        for i, code in enumerate(LESION_ONLY_CHANNELS):
            lesion_masks_by_code[code] = v2_masks[i]

    if lesion_masks_by_code:
        overlay = processed_rgb.copy()
        colors = {"MA": (255, 0, 0), "HE": (255, 128, 0), "EX": (255, 255, 0), "SE": (0, 255, 255), "OD": (0, 255, 0)}
        lesion_evidence = {}
        for code in LESION_CHANNELS:
            if code not in lesion_masks_by_code:
                continue
            mask = lesion_masks_by_code[code]
            coverage_pct = float(mask.mean() * 100)
            lesion_evidence[code] = {"name": LESION_NAMES[code], "coverage_pct": round(coverage_pct, 3),
                                      "present": bool(mask.any())}
            if mask.any():
                overlay[mask] = colors[code]
        blended = cv2.addWeighted(processed_rgb, 0.6, overlay, 0.4, 0)
        lesion_path = out_dir / f"{stem}_lesions.png"
        cv2.imwrite(str(lesion_path), cv2.cvtColor(blended, cv2.COLOR_RGB2BGR))
        result["lesion_evidence"] = {
            "path": str(lesion_path), "per_lesion": lesion_evidence,
            "caveat": "Optic Disc: IDRiD-only (54 images), 0.842 dice. MA/Haemorrhage/Hard "
                      "Exudate/Soft Exudate: merged IDRiD+DDR+e-ophtha (~1,300 images), "
                      "pretrained-encoder + Focal Tversky Loss — proof-of-concept scale, not a "
                      "validated clinical result. Microaneurysm dice is 0.029 (first non-zero "
                      "result after three earlier attempts; literature best on much larger, "
                      "cleaner data is ~0.56) — treat any MA marking as a weak, low-confidence "
                      "signal, not a definitive finding (see docs/SIH_SUBMISSION_PLAN.md item 3).",
        }

    report_path = out_dir / f"{stem}_report.json"
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--dr-checkpoint", required=True)
    parser.add_argument("--fiqa-checkpoint", default=None)
    parser.add_argument("--lesion-checkpoint", default=None)
    parser.add_argument("--lesion-v2-checkpoint", default=None)
    parser.add_argument("--temperature", type=float, default=1.0)
    args = parser.parse_args()
    result = generate_report(args.image, args.dr_checkpoint, args.fiqa_checkpoint,
                              args.lesion_checkpoint, args.lesion_v2_checkpoint, args.temperature)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
