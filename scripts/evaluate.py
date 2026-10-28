"""Score baseline (with/without seasonal filter) and U-Net on the frozen TEST blocks."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.config import load_config
from forestwatch.pipeline import run_pipeline, split_maps
from forestwatch.preprocess.splits import TEST
from forestwatch.eval.grids import check_same_shape
from forestwatch.eval.metrics import pixel_metrics, polygon_metrics, block_bootstrap_f1

ROOT = Path(__file__).resolve().parents[1]
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
label_path = ROOT / "data" / "labels" / "change.npy"
if not label_path.exists():
    raise SystemExit("Missing data/labels/change.npy. Run scripts/make_labels.py first.")
labels = np.load(label_path).astype(bool)

runs = [("baseline, no seasonal filter", "baseline", False),
        ("baseline + seasonal filter", "baseline", True)]
if (ROOT / cfg["model"]["checkpoint"]).exists():
    runs += [("U-Net, no seasonal filter", "unet", False), ("U-Net + seasonal filter", "unet", True)]
else:
    print("(No trained model found: U-Net rows skipped.)")

results = {}
for name, method, seas in runs:
    res = run_pipeline(cfg, ROOT, method, seasonal=seas)
    check_same_shape("label raster", labels, "prediction", res["mask"])
    truth = labels & res["valid"]
    split, blocks = split_maps(cfg, truth.shape)
    region = split == TEST
    pm, gm = pixel_metrics(res["mask"], truth, region), polygon_metrics(res["mask"], truth, region)
    lo, hi = block_bootstrap_f1(res["mask"], truth, split, blocks, TEST)
    results[name] = {"pixel": pm, "patch": gm, "f1_ci95": [lo, hi]}
    print(f"{name:32s} P={pm['precision']:.3f} R={pm['recall']:.3f} F1={pm['f1']:.3f} "
          f"CI[{lo:.3f},{hi:.3f}]  patches {gm['detected']}/{gm['true_patches']}  blobs {gm['pred_blobs']}")
out = ROOT / "outputs" / "evaluation.json"
out.parent.mkdir(exist_ok=True); out.write_text(json.dumps(results, indent=2))
print("Saved", out)
