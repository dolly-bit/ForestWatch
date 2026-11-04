"""Paint the labels onto the EXACT prediction grid (needs rasterio) and verify the grids match.
  python scripts/rasterize_reference_labels.py --split validation --baseline-run-id <id from build_sampling_frame.py>
Writes data/reference/masks/<split>_label_mask.tif (0 no_loss, 1 loss, 255 excluded), _valid_mask.tif (1 = evaluate),
_unit_index.tif (chip number) and _metadata.json. Test masks need --final-evaluation."""
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.audit import sha256_file
from forestwatch.pipeline import load_window
from forestwatch.reference.context import load_context
from forestwatch.reference.schema import read_rows, SPLITS, MASK_ENCODING, guard_test_labels
from forestwatch.reference.rasterize import rasterize_chip_labels, write_geotiff, read_grid_meta, check_same_grid

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--split", required=True, choices=SPLITS)
ap.add_argument("--baseline-run-id", required=True)
ap.add_argument("--final-evaluation", action="store_true")
ap.add_argument("--force", action="store_true")
args = ap.parse_args()
guard_test_labels([args.split], args.final_evaluation)
cfg, ref, meta, shape = load_context(ROOT)
labels_path = ROOT / "data" / "reference" / f"labels_{args.split}.csv"
rows = read_rows(labels_path)
mc = cfg["cloud_mask"]["min_valid_observations"]
before, after = load_window(ROOT, "before", mc), load_window(ROOT, "after", mc)
imagery_valid = before["valid"] & after["valid"]
label, valid, index = rasterize_chip_labels(rows, shape, ref["chip_px"], imagery_valid)
out = ROOT / "data" / "reference" / "masks"
out.mkdir(parents=True, exist_ok=True)
names = {"label_mask": (label, "uint8"), "valid_mask": (valid, "uint8"), "unit_index": (index, "int32")}
paths = {k: out / f"{args.split}_{k}.tif" for k in names}
if any(p.exists() for p in paths.values()) and not args.force:
    sys.exit("Masks already exist for this split; use --force to replace them.")
for k, (arr, dt) in names.items():
    write_geotiff(paths[k], arr, meta, dt)
    check_same_grid(meta, read_grid_meta(paths[k]), "prediction grid", str(paths[k].name))     # read back and compare
info = {"split": args.split, "baseline_run_id": args.baseline_run_id, "dataset_version": ref["dataset_version"],
        "protocol_version": ref["protocol_version"], "created_utc": datetime.now(timezone.utc).isoformat(),
        "labels_file": str(labels_path.relative_to(ROOT)), "labels_sha256": sha256_file(labels_path),
        "crs": meta["crs"], "transform": meta["transform"], "width": meta["width"], "height": meta["height"],
        "resolution_m": cfg["region"]["resolution_m"], "chip_px": ref["chip_px"],
        "truth_resolution": "chip (unit-level): every pixel of a chip carries its chip's class. Evaluate per chip, not per pixel.",
        "mask_encoding": MASK_ENCODING, "valid_mask": "1 = chip labelled loss/no_loss AND imagery clear on both dates",
        "unit_index": "(chip_row0 // chip_px) * (width // chip_px) + (chip_col0 // chip_px) + 1; 0 = no chip",
        "counts": {"loss_px": int(((label == 1) & (valid == 1)).sum()), "no_loss_px": int(((label == 0) & (valid == 1)).sum()),
                   "excluded_px_inside_labelled_chips": int(((index > 0) & (valid == 0)).sum())}}
(out / f"{args.split}_mask_metadata.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
print("Wrote masks for", args.split, info["counts"], "- grids verified identical to the prediction grid.")
