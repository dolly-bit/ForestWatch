"""Run a method on the stacks and export GeoJSON candidate clearings (EPSG:4326).
Each run gets its own folder outputs/runs/<run_id>/ with the config used and a manifest (nothing is overwritten)."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.config import load_config
from forestwatch.pipeline import run_pipeline
from forestwatch.audit import new_run_id, write_run_manifest

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--method", choices=["baseline", "unet"], default="baseline")
ap.add_argument("--no-seasonal", action="store_true")
args = ap.parse_args()
cfg_path = ROOT / "configs" / "aravalli.yaml"
cfg = load_config(cfg_path)
res = run_pipeline(cfg, ROOT, args.method, seasonal=False if args.no_seasonal else None)
run_id = new_run_id(cfg_path)
out = write_run_manifest(ROOT, cfg_path, run_id, {"method": args.method, "seasonal": res["seasonal"],
                                                  "n_candidates": len(res["features"])})
(out / "change_events.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": res["features"]}))
np.save(out / "change_mask.npy", res["mask"])
print(f"{len(res['features'])} candidate clearings, {sum(f['properties']['area_ha'] for f in res['features']):.1f} ha "
      f"(method={res['method']}, seasonal={res['seasonal']})\nRun {run_id} saved in {out}")
