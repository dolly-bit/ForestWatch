"""Run a method on the stacks and export GeoJSON candidate clearings (EPSG:4326)."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.config import load_config
from forestwatch.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--method", choices=["baseline", "unet"], default="baseline")
ap.add_argument("--no-seasonal", action="store_true")
args = ap.parse_args()
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
res = run_pipeline(cfg, ROOT, args.method, seasonal=False if args.no_seasonal else None)
out = ROOT / "outputs"; out.mkdir(exist_ok=True)
(out / "change_events.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": res["features"]}))
np.save(out / "change_mask.npy", res["mask"])
print(f"{len(res['features'])} candidate clearings, {sum(f['properties']['area_ha'] for f in res['features']):.1f} ha "
      f"(method={res['method']}, seasonal={res['seasonal']}) -> outputs/change_events.geojson")
