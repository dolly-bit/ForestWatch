"""Step 2 (needs network + rasterio): download scenes onto the common grid.

  python scripts/build_stacks.py                                   # everything, scaling mode 'auto'
  python scripts/build_stacks.py --scaling none --window before --date 2022-11-20 --out-root data/stacks_test
        ^ one-scene TRIAL in a separate folder (nothing in data/stacks is touched)
--scaling: auto (catalog offset if recorded, else date rule; REJECTED automatically if it gives many exact-zero red values),
           none (DN/10000, no offset: what your data needed), date_rule (the old, flawed behaviour)
Prints the share of exact-zero red values per scene: more than 20% means the scaling is probably wrong."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.config import load_config
from forestwatch.data.download import build_scene_stack

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--scaling", choices=["auto", "none", "date_rule"], default="auto")
ap.add_argument("--window", choices=["before", "after"], default=None, help="only this window")
ap.add_argument("--date", default=None, help="only scenes whose date starts with this, e.g. 2022-11-20")
ap.add_argument("--limit", type=int, default=None, help="at most this many scenes per window")
ap.add_argument("--out-root", default=str(ROOT / "data" / "stacks"))
args = ap.parse_args()
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
cfg["reflectance"] = {**(cfg.get("reflectance") or {}), "mode": args.scaling}
out_root = Path(args.out_root)
if out_root.resolve() == (ROOT / "data" / "stacks").resolve() and any(out_root.glob("*/*.npz")):
    sys.exit("data/stacks already contains stacks. Move it away first (e.g. Rename-Item data\\stacks stacks_flawed_offset) "
             "or use --out-root for a trial.")
for name in cfg["windows"]:
    if args.window and name != args.window:
        continue
    catalog = json.loads((ROOT / "data" / "raw" / f"catalog_{name}.json").read_text())
    if args.date:
        catalog = [s for s in catalog if s["datetime"].startswith(args.date)]
    for scene in catalog[: args.limit]:
        path, meta = build_scene_stack(scene, cfg, out_root / name)
        zero = meta["red_zero_fraction"]
        flag = "  <-- SUSPECT scaling (many exact-zero red values)" if zero is not None and zero > 0.20 else ""
        print(f"{name}: {meta['date']} valid={meta['valid_fraction']:.0%} red==0: "
              f"{'n/a' if zero is None else format(zero, '.1%')}  [{meta['reflectance_scaling']}]{flag}")
