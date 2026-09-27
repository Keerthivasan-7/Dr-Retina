"""Evaluate a FIQA checkpoint on the locked DRIMDB split without tuning on it."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import torch
from sklearn.metrics import classification_report
from torch.utils.data import DataLoader

from src.common import DATA_SPLITS, FIQA_CLASSES, REPORTS_DIR
from src.data.dataset import ImageLabelDataset
from src.eval.external_eval import run_inference
from src.models.fiqa import build_fiqa_model
from src.train.train_fiqa import good_vs_reject_auroc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--csv", default=str(DATA_SPLITS / "fiqa_external_drimdb.csv"))
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=4)
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"locked DRIMDB split is required: {csv_path}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    image_size = checkpoint["config"]["data"]["image_size"]
    model = build_fiqa_model(pretrained=False).to(device)
    model.load_state_dict(checkpoint["model_state"])
    dataset = ImageLabelDataset(str(csv_path), image_size=image_size)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers, pin_memory=True)
    result = run_inference(model, loader, device)
    auroc = good_vs_reject_auroc(result["y_true"], result["y_prob"])
    report = classification_report(
        result["y_true"], result["y_pred"], labels=list(range(len(FIQA_CLASSES))),
        target_names=FIQA_CLASSES, digits=4, zero_division=0,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output = REPORTS_DIR / f"fiqa_external_eval_{args.run_id}.md"
    output.write_text(
        "\n".join([
            f"# Locked external FIQA evaluation — {args.run_id}", "",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Checkpoint: `{args.checkpoint}`", f"Split: `{csv_path}`", "",
            f"- n = {len(dataset)}", f"- Good-vs-Reject AUROC: **{auroc:.4f}**", "",
            "## Per-class classification report", "", "```", report, "```", "",
            "DRIMDB was used only for this final external evaluation; no checkpoint, threshold, or "
            "configuration decision may be based on this report.",
        ]), encoding="utf-8"
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
