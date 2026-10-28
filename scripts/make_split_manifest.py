"""Create (and freeze) the spatial split manifest: data/labels/split_manifest.csv + .sha256.
  python scripts/make_split_manifest.py            # create; refuses to overwrite a frozen manifest
  python scripts/make_split_manifest.py --verify   # check the manifest still matches its checksum"""
import argparse, csv, io, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from collections import Counter
from forestwatch.config import load_config
from forestwatch.manifest import build_manifest, COLUMNS, sha256_text

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--verify", action="store_true")
ap.add_argument("--force", action="store_true", help="overwrite a frozen manifest (invalidates earlier test results)")
args = ap.parse_args()
out = ROOT / "data" / "labels" / "split_manifest.csv"
sha = out.with_suffix(".sha256")
if args.verify:
    if not (out.exists() and sha.exists()):
        sys.exit("No frozen manifest found.")
    ok = sha256_text(out.read_text(encoding="utf-8")) == sha.read_text().strip()
    print("Manifest matches its frozen checksum." if ok else "MANIFEST CHANGED since it was frozen!")
    sys.exit(0 if ok else 1)
if out.exists() and not args.force:
    sys.exit(f"{out} already exists (frozen). Use --verify, or --force if you really mean to replace it.")
cfg = load_config(ROOT / "configs" / "aravalli.yaml")
meta = json.loads(sorted((ROOT / "data" / "stacks" / "after").glob("*.json"))[0].read_text())
try:
    rows = build_manifest(cfg["split"], meta, datetime.now(timezone.utc).isoformat())
except ValueError as e:
    sys.exit(f"Cannot build the split: {e}\nYour area is {meta['width']} x {meta['height']} pixels; the config uses "
             f"block_size_px={cfg['split']['block_size_px']} and group_blocks={cfg['split'].get('group_blocks', 1)}. "
             "Use smaller blocks or a smaller group size in configs/aravalli.yaml.")
buf = io.StringIO(newline="")
w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n"); w.writeheader(); w.writerows(rows)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(buf.getvalue(), encoding="utf-8")
sha.write_text(sha256_text(buf.getvalue()))
print(f"Wrote {len(rows)} blocks to {out}:", dict(Counter(r["split"] for r in rows)))
print("Frozen checksum saved to", sha.name, "- do not edit the manifest; tune thresholds only on 'train'/'validation'.")
