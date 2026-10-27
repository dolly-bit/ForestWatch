"""Rasterise QGIS change polygons onto the stack grid -> data/labels/change.npy

Usage:
  python scripts/make_labels.py data/labels/my_polygons.geojson [--src-crs EPSG:4326]

In QGIS: draw polygons around areas that CLEARLY changed from vegetation to
cleared land, then Export > Save Features As > GeoJSON. Either keep EPSG:4326
(default here) or export in the stack CRS and pass --src-crs EPSG:32643.
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.config import load_config
from forestwatch.labels.rasterize import rasterize_geojson, load_geojson

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("geojson")
ap.add_argument("--src-crs", default="EPSG:4326")
ap.add_argument("--out", default=str(ROOT / "data" / "labels" / "change.npy"))
args = ap.parse_args()

gj = Path(args.geojson)
if not gj.exists():
    found = sorted(p.name for p in (ROOT / "data" / "labels").glob("*.geojson"))
    raise SystemExit(
        f"File not found: {gj.resolve()}\n"
        "Create it first: draw polygons in QGIS, then Export > Save Features As > GeoJSON.\n"
        "(See the QGIS steps in the README / chat.) "
        + (f"GeoJSON files currently in data/labels: {found}" if found else "No .geojson files in data/labels yet."))
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
metas = sorted((ROOT / "data" / "stacks" / "before").glob("*.json"))
if not metas:
    raise SystemExit("No stacks found in data/stacks/before. Run build_stacks.py first.")
meta = json.loads(metas[0].read_text())
shape = (meta["height"], meta["width"])
mask, n = rasterize_geojson(load_geojson(args.geojson), tuple(meta["transform"]), shape,
                            args.src_crs, meta["crs"])
res = cfg["region"]["resolution_m"]
print(f"{n} polygons -> {int(mask.sum())} px = {mask.sum() * res * res / 10000:.1f} ha of {shape[0]}x{shape[1]} grid")
if mask.sum() == 0:
    print("WARNING: empty label mask. Check --src-crs and that polygons lie inside the study bbox.")
np.save(args.out, mask)
print("Saved", args.out)
