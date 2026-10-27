"""Quick baseline run (same as predict.py --method baseline) plus scores if labels exist."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.config import load_config
from forestwatch.pipeline import run_pipeline, split_maps
from forestwatch.preprocess.splits import TEST
from forestwatch.eval.metrics import pixel_metrics, polygon_metrics

ROOT = Path(__file__).resolve().parents[1]
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
res = run_pipeline(cfg, ROOT, "baseline")
(ROOT / "outputs").mkdir(exist_ok=True)
np.save(ROOT / "outputs" / "baseline_change.npy", res["mask"])
print(f"Flagged {len(res['features'])} blobs, {sum(f['properties']['area_ha'] for f in res['features']):.1f} ha")
lp = ROOT / "data" / "labels" / "change.npy"
if lp.exists():
    truth = np.load(lp).astype(bool) & res["valid"]
    split, _ = split_maps(cfg, truth.shape)
    print("TEST pixel:", pixel_metrics(res["mask"], truth, split == TEST))
    print("TEST patch:", polygon_metrics(res["mask"], truth, split == TEST))
else:
    print("No labels yet (data/labels/change.npy): map saved, not scored.")
