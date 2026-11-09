"""READ-ONLY: which scenes would be removed before compositing? Nothing is changed or saved.

Shows, per scene: clear share, median red, median NDVI and what the selection rules would do:
  DUPLICATE  the same acquisition appears twice (processing versions _0_ and _1_); the newest is kept
  HAZY?      much lower NDVI / higher red than the rest of its window (e.g. post-Diwali smog)
The rules come from the optional 'quality:' section of configs/aravalli.yaml (defaults: dedupe on, hazy dropping OFF).
  python scripts/list_hazy_scenes.py          # uses the config as it is
  python scripts/list_hazy_scenes.py --hazy   # preview with hazy dropping switched on"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.config import load_config
from forestwatch.data.stack_io import load_stack
from forestwatch.preprocess.indices import ndvi
from forestwatch.preprocess.scene_quality import scene_stats, select_scenes, settings

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--hazy", action="store_true", help="preview with drop_hazy_scenes switched on")
args = ap.parse_args()
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
q = {**(cfg.get("quality") or {}), **({"drop_hazy_scenes": True} if args.hazy else {})}
print("rules:", settings(q))
for window in ("before", "after"):
    files = sorted((ROOT / "data" / "stacks" / window).glob("*.npz"))
    ids, stats = [], []
    for f in files:
        arr, m = load_stack(f)
        ids.append(m.get("scene_id", f.stem)); stats.append({**scene_stats(arr, ndvi(arr["nir"], arr["red"])), "date": m["date"]})
    keep, decisions = select_scenes(ids, stats, q)
    why = {d["index"]: d["reason"] for d in decisions if d["index"] is not None and not d["kept"]}
    print(f"\n{window}: {len(files)} scenes\n{'date':10s} {'scene id':30s} {'clear':>6s} {'red med':>8s} {'NDVI med':>9s}  decision")
    for i, (sid, st) in enumerate(zip(ids, stats)):
        r = why.get(i, "")
        tag = "DUPLICATE (dropped)" if r.startswith("duplicate") else "HAZY? (dropped)" if r.startswith("looks hazy") else "kept"
        print(f"{st['date']:10s} {sid:30s} {st['valid_share']:6.0%} {st['red_median']:8.3f} {st['ndvi_median']:9.2f}  {tag}")
    for d in decisions:
        if d["index"] is None:
            print("NOTE:", d["reason"])
    print(f"-> {sum(keep)} of {len(files)} scenes would be used for the {window} composite")
