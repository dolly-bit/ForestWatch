"""Baseline run with a traceable run folder (outputs/runs/<run_id>/), plus scores if labels exist."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.config import load_config
from forestwatch.pipeline import run_pipeline, split_maps
from forestwatch.preprocess.splits import TEST
from forestwatch.eval.metrics import pixel_metrics, polygon_metrics
from forestwatch.eval.grids import check_same_shape
from forestwatch.audit import new_run_id, write_run_manifest

ROOT = Path(__file__).resolve().parents[1]
cfg_path = ROOT / "configs" / "aravalli.yaml"
cfg = load_config(cfg_path)
res = run_pipeline(cfg, ROOT, "baseline")
run_id = new_run_id(cfg_path)
out = write_run_manifest(ROOT, cfg_path, run_id, {"method": "baseline", "n_candidates": len(res["features"])})
np.save(out / "baseline_change.npy", res["mask"])
print(f"Run {run_id}: flagged {len(res['features'])} blobs, "
      f"{sum(f['properties']['area_ha'] for f in res['features']):.1f} ha. Saved in {out}")
lp = ROOT / "data" / "labels" / "change.npy"
if lp.exists():
    labels = np.load(lp).astype(bool)
    check_same_shape("label raster", labels, "prediction", res["mask"])
    truth = labels & res["valid"]
    split, _ = split_maps(cfg, truth.shape)
    print("TEST pixel:", pixel_metrics(res["mask"], truth, split == TEST))
    print("TEST patch:", polygon_metrics(res["mask"], truth, split == TEST))
else:
    print("No labels yet (data/labels/change.npy): map saved, not scored.")
