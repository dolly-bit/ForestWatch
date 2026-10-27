"""End-to-end Phase 1 demo on SYNTHETIC data (no network, no rasterio needed).

Shows: spatial block split -> NDVI baseline -> held-out evaluation, and why
same-season comparison matters (cross-season pairs create false alarms).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from forestwatch.config import load_config
from forestwatch.synthetic import make_scene_pair
from forestwatch.change.baseline import detect_change, components_summary
from forestwatch.preprocess.splits import (assign_block_splits, pixel_split_map, block_id_map,
                                           block_shape, check_no_leakage, TEST)
from forestwatch.eval.metrics import pixel_metrics, polygon_metrics, block_bootstrap_f1

ROOT = Path(__file__).resolve().parents[1]
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
b, s = cfg["baseline"], cfg["split"]

H = W = 512
DEMO_BLOCK, DEMO_GROUP = 32, 4        # small image -> small blocks (real data uses config values)
grid = assign_block_splits(*block_shape(H, W, DEMO_BLOCK), tuple(s["fractions"]), s["seed"], s["buffer_blocks"], DEMO_GROUP)
assert check_no_leakage(grid, s["buffer_blocks"])
split = pixel_split_map(H, W, DEMO_BLOCK, grid)
blocks = block_id_map(H, W, DEMO_BLOCK)
test_region = split == TEST
print(f"Block grid:\n{grid}\n(0 train, 1 val, 2 test, -1 buffer)\n")

results = {}
for name, dip in [("same-season pair", 0.0), ("cross-season pair (dry-season dip)", 0.30)]:
    d = make_scene_pair(H, W, seed=7, season_dip=dip)
    pred = detect_change(d["ndvi_before"], d["ndvi_after"], d["valid_before"], d["valid_after"],
                         b["forest_ndvi_min"], b["ndvi_drop_min"], b["min_area_pixels"])
    pm = pixel_metrics(pred, d["truth"], test_region)
    gm = polygon_metrics(pred, d["truth"], test_region)
    lo, hi = block_bootstrap_f1(pred, d["truth"], split, blocks, TEST, n_boot=500)
    results[name] = (d, pred)
    print(f"== {name} ==")
    print(f"  test pixel P={pm['precision']:.3f} R={pm['recall']:.3f} F1={pm['f1']:.3f} IoU={pm['iou']:.3f}  F1 95% CI (block bootstrap) [{lo:.3f}, {hi:.3f}]")
    print(f"  test patches detected {gm['detected']}/{gm['true_patches']}; flagged blobs {gm['pred_blobs']} (correct {gm['correct_blobs']})")
    print(f"  total flagged area: {sum(c['area_ha'] for c in components_summary(pred)):.1f} ha\n")

fig, ax = plt.subplots(2, 3, figsize=(12, 8))
for r, (name, (d, pred)) in enumerate(results.items()):
    ax[r, 0].imshow(d["ndvi_before"], cmap="YlGn", vmin=0, vmax=0.9); ax[r, 0].set_title("NDVI before")
    ax[r, 1].imshow(d["ndvi_after"], cmap="YlGn", vmin=0, vmax=0.9); ax[r, 1].set_title(f"NDVI after\n{name}")
    ov = np.zeros((H, W, 3)); ov[d["truth"]] = (0, 0.6, 0); ov[pred & ~d["truth"]] = (0.9, 0, 0)
    ov[pred & d["truth"]] = (1, 1, 0); ax[r, 2].imshow(ov); ax[r, 2].set_title("yellow=hit, green=missed, red=false alarm")
    for a in ax[r]:
        a.axis("off")
        for k in range(1, H // (DEMO_BLOCK * DEMO_GROUP)):
            a.axhline(k * DEMO_BLOCK * DEMO_GROUP, color="w", lw=0.4); a.axvline(k * DEMO_BLOCK * DEMO_GROUP, color="w", lw=0.4)
out = ROOT / "outputs" / "phase1_demo.png"
out.parent.mkdir(exist_ok=True)
plt.tight_layout(); plt.savefig(out, dpi=110)
print("Saved figure:", out)
