"""Step 2 (needs network + rasterio): download scenes onto the common grid.

Run a one-scene trial first:
  python scripts/build_stacks.py --window before --date 2022-10-16 --limit 1 --out-root data/stacks_test

--scaling:
  auto       use Earth Search BOA metadata and raster scale/offset; date-rule fallback
  none       DN/10000 with no offset (explicit override)
  date_rule  legacy date-based -1000 DN correction

Duplicate processing versions are filtered before download (highest version kept).
Exact-zero red share is printed as a diagnostic; it does not select calibration.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forestwatch.config import load_config
from forestwatch.data.download import build_scene_stack
from forestwatch.preprocess.scene_quality import dedupe_flags

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--scaling", choices=["auto", "none", "date_rule"], default="auto")
ap.add_argument("--window", choices=["before", "after"], default=None, help="only this window")
ap.add_argument("--date", default=None, help="only scenes whose date starts with this, e.g. 2022-10-16")
ap.add_argument("--limit", type=int, default=None, help="at most this many scenes per window after deduplication")
ap.add_argument("--out-root", default=str(ROOT / "data" / "stacks"))
args = ap.parse_args()

cfg = load_config(ROOT / "configs" / "aravalli.yaml")
cfg["reflectance"] = {**(cfg.get("reflectance") or {}), "mode": args.scaling}
out_root = Path(args.out_root)

if out_root.resolve() == (ROOT / "data" / "stacks").resolve() and any(out_root.glob("*/*.npz")):
    sys.exit(
        "data/stacks already contains stacks. Move it away first (e.g. "
        "Rename-Item data\\stacks stacks_backup) or use --out-root for a trial."
    )

for window_name in cfg["windows"]:
    if args.window and window_name != args.window:
        continue

    catalog_path = ROOT / "data" / "raw" / f"catalog_{window_name}.json"
    catalog = json.loads(catalog_path.read_text())
    if args.date:
        catalog = [scene for scene in catalog if scene["datetime"].startswith(args.date)]

    quality = cfg.get("quality") or {}
    if quality.get("dedupe_scenes", True):
        keep = dedupe_flags([scene["id"] for scene in catalog])
        dropped = [scene["id"] for scene, should_keep in zip(catalog, keep) if not should_keep]
        catalog = [scene for scene, should_keep in zip(catalog, keep) if should_keep]
        for scene_id in dropped:
            print(f"{window_name}: skipped duplicate processing version {scene_id}")

    if args.limit is not None:
        catalog = catalog[:args.limit]

    for scene in catalog:
        path, meta = build_scene_stack(scene, cfg, out_root / window_name)
        zero = meta["red_zero_fraction"]
        zero_text = "n/a" if zero is None else f"{zero:.1%}"
        print(
            f"{window_name}: {meta['date']} valid={meta['valid_fraction']:.0%} "
            f"red==0: {zero_text}  [red: {meta['reflectance_scaling']['red']}]"
        )
