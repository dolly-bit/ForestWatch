"""Which land-cover class sits under each reviewed detection? (needs data/landcover/landcover_grid.npy)"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.review import landcover_breakdown

ROOT = Path(__file__).resolve().parents[1]
NAMES = {10: "tree cover", 20: "shrubland", 30: "grassland", 40: "cropland", 50: "built-up",
         60: "bare/sparse", 80: "water", 90: "wetland", -1: "outside grid"}
grid = np.load(ROOT / "data" / "landcover" / "landcover_grid.npy")
meta = json.loads(sorted((ROOT / "data" / "stacks" / "after").glob("*.json"))[0].read_text())
res = landcover_breakdown(ROOT / "outputs" / "review" / "review.csv", grid, tuple(meta["transform"]), meta["crs"])
print(f"{'class':5s} {'name':13s} {'judged':>6s} {'real':>5s} {'not real':>8s} {'precision':>9s}")
for cls in sorted(res):
    d = res[cls]
    print(f"{cls:5d} {NAMES.get(cls, '?'):13s} {d['n']:6d} {d['real']:5d} {d['not_real']:8d} {d['real'] / d['n']:9.2f}")
print("\nArea share of each class in your study area:")
vals, counts = np.unique(grid, return_counts=True)
for v, c in zip(vals, counts):
    print(f"  {int(v):3d} {NAMES.get(int(v), '?'):13s} {c / grid.size:6.1%}")
