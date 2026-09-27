"""Fit temperature scaling on internal val, report ECE before/after on val
and (informationally, not re-fit) on the locked external sets.

Run: python -m src.eval.calibrate_model --checkpoint reports/checkpoints/p0_baseline_resnet50/best.pt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common import DATA_SPLITS  # noqa: E402
from src.data.dataset import ImageLabelDataset  # noqa: E402
from src.data.preprocess import circular_crop_and_resize  # noqa: E402
from src.eval.calibration import expected_calibration_error, fit_temperature  # noqa: E402
from src.models.dr_backbone import build_dr_model  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402


@torch.no_grad()
def collect_logits(model, csv_path, image_size, device, preprocess=None, batch_size=16, num_workers=0):
    ds = ImageLabelDataset(str(csv_path), image_size=image_size, preprocess=preprocess)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    all_logits, all_labels = [], []
    model.eval()
    for images, labels in loader:
        logits = model(images.to(device))
        all_logits.append(logits.cpu())
        all_labels.append(labels)
    return torch.cat(all_logits), torch.cat(all_labels)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    cfg = ckpt["config"]
    model = build_dr_model(backbone=cfg["model"]["backbone"], num_classes=cfg["model"]["num_classes"],
                            pretrained=False).to(device)
    model.load_state_dict(ckpt["model_state"])
    image_size = cfg["data"]["image_size"]

    print("collecting internal val logits...")
    val_logits, val_labels = collect_logits(model, DATA_SPLITS / "val.csv", image_size, device)

    ece_before = expected_calibration_error(torch.softmax(val_logits, dim=1), val_labels)
    temperature = fit_temperature(val_logits, val_labels)
    ece_after = expected_calibration_error(torch.softmax(val_logits / temperature, dim=1), val_labels)
    print(f"internal val ECE: before={ece_before:.4f} after={ece_after:.4f} (temperature={temperature:.4f})")

    results = {"temperature": temperature, "val_ece_before": ece_before, "val_ece_after": ece_after,
               "external": {}}
    for name, csv_path in (("idrid", DATA_SPLITS / "external_test_idrid.csv"),
                            ("messidor2", DATA_SPLITS / "external_test_messidor2.csv")):
        if not csv_path.exists():
            continue
        print(f"collecting {name} logits...")
        logits, labels = collect_logits(model, csv_path, image_size, device, preprocess=circular_crop_and_resize)
        ece_b = expected_calibration_error(torch.softmax(logits, dim=1), labels)
        ece_a = expected_calibration_error(torch.softmax(logits / temperature, dim=1), labels)
        print(f"  {name} ECE: before={ece_b:.4f} after={ece_a:.4f} (using val-fitted temperature, not re-fit)")
        results["external"][name] = {"ece_before": ece_b, "ece_after": ece_a}

    out_path = Path(args.checkpoint).parent / "calibration.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
