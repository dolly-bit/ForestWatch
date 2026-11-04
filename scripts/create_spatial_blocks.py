"""Import the FROZEN Phase 1 block split into data/splits (README format + blocks.geojson). Never re-randomises.
  python scripts/create_spatial_blocks.py"""
import argparse, json, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.reference.context import load_context, load_frozen_manifest
from forestwatch.reference.blocks import prepare_blocks, check_blocks, hash_of_test_blocks, blocks_geojson, dumps
from forestwatch.reference.schema import write_rows

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--force", action="store_true")
args = ap.parse_args()
cfg, ref, meta, shape = load_context(ROOT)
rows, sha = load_frozen_manifest(ROOT)
blocks = prepare_blocks(rows, cfg["region"]["resolution_m"], shape)
problems = check_blocks(blocks)
if problems:
    sys.exit("PROBLEMS:\n  " + "\n  ".join(problems))
out = ROOT / "data" / "splits"
write_rows(out / "split_manifest.csv", blocks, ["block_id", "split", "region", "area_km2", "stratum", "selection_method", "notes"], args.force)
(out / "blocks.geojson").write_text(dumps(blocks_geojson(blocks)), encoding="utf-8")
frozen = {"dataset_version": ref["dataset_version"], "created_utc": datetime.now(timezone.utc).isoformat(),
          "source_manifest": "data/labels/split_manifest.csv", "source_manifest_sha256": sha,
          "test_block_ids_sha256": hash_of_test_blocks(blocks), "blocks_per_split": dict(Counter(b["split"] for b in blocks)),
          "crs": meta["crs"], "grid": {"width": meta["width"], "height": meta["height"], "transform": meta["transform"]}}
fp = out / "frozen.json"
if fp.exists() and not args.force:
    sys.exit(f"{fp} exists (the test split is frozen). Use --force only if you accept creating a NEW dataset version.")
fp.write_text(dumps(frozen), encoding="utf-8")
print("Blocks per split:", frozen["blocks_per_split"])
print("Test block ids hash:", frozen["test_block_ids_sha256"][:16], "... saved in data/splits/frozen.json")
