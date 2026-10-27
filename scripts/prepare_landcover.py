"""Align an ESA WorldCover (or any land-cover) GeoTIFF to your stack grid -> data/landcover/landcover_grid.npy

Usage:
  python scripts/prepare_landcover.py path\\to\\ESA_WorldCover_10m_2021_v200_N27E075_Map.tif
  python scripts/prepare_landcover.py https://...tif            (a COG URL also works; only your window is read)

Get the tile from esa-worldcover.org (Download section). Your area lies in the 3-degree tile named N27E075
(27-30 N, 75-78 E): verify on the site. WorldCover classes: 10 tree, 20 shrub, 30 grass, 40 cropland,
50 built-up, 60 bare/sparse, 80 water, 90 wetland. Needs rasterio. Check the data licence/attribution terms.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NAMES = {10: "tree cover", 20: "shrubland", 30: "grassland", 40: "cropland", 50: "built-up",
         60: "bare/sparse", 70: "snow/ice", 80: "water", 90: "wetland", 95: "mangroves", 100: "moss/lichen"}

if len(sys.argv) != 2:
    raise SystemExit(__doc__)
from rasterio.transform import Affine
from forestwatch.data.download import read_band

metas = sorted((ROOT / "data" / "stacks" / "after").glob("*.json"))
if not metas:
    raise SystemExit("No stacks in data/stacks/after. Run build_stacks.py first.")
meta = json.loads(metas[0].read_text())
grid = read_band(sys.argv[1], meta["crs"], Affine(*meta["transform"]), meta["width"], meta["height"], categorical=True)
grid = grid.astype("uint8")
out = ROOT / "data" / "landcover" / "landcover_grid.npy"
out.parent.mkdir(parents=True, exist_ok=True)
np.save(out, grid)
print("Saved", out, grid.shape)
vals, counts = np.unique(grid, return_counts=True)
for v, c in zip(vals, counts):
    print(f"  class {v:3d} {NAMES.get(int(v), '?'):12s} {c / grid.size:6.1%}")
print("\nNext: add this to configs/aravalli.yaml:\n  exclusions:\n    landcover_file: data/landcover/landcover_grid.npy\n    exclude_classes: [40]")
