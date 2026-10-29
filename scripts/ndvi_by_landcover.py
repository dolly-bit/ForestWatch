"""Label-free diagnostic: how green is each land-cover class before the change, and how much of it does the
baseline flag?  Tests the idea that the detector favours irrigated cropland (it needs NDVI >= forest_ndvi_min).
Takes a few minutes (one detector run)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.config import load_config
from forestwatch.pipeline import run_pipeline
from forestwatch.landcover_diag import ndvi_by_class

ROOT = Path(__file__).resolve().parents[1]
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
grid = np.load(ROOT / "data" / "landcover" / "landcover_grid.npy")
res = run_pipeline(cfg, ROOT, "baseline", seasonal=False, return_windows=True)
before, _ = res["windows"]
thr = cfg["baseline"]["forest_ndvi_min"]
rows = ndvi_by_class(before["ndvi"], res["valid"], res["mask"], grid, thr)
print(f"Detector: forest_ndvi_min={thr}, ndvi_drop_min={cfg['baseline']['ndvi_drop_min']}  (no labels used)\n")
print(f"{'class':5s} {'name':12s} {'area':>6s} {'median NDVI':>11s} {'NDVI>=thr':>10s} {'flagged % of class':>19s} {'share of detections':>20s}")
for r in rows:
    share = "n/a" if r["share_of_all_detections"] is None else f"{r['share_of_all_detections']:.1%}"
    print(f"{r['class']:5d} {r['name']:12s} {r['area_share']:6.1%} {r['median_ndvi_before']:11.2f} "
          f"{r['share_ndvi_at_least_threshold']:10.1%} {r['flagged_share_of_class']:19.2%} {share:>20s}")
