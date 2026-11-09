"""Build the chip sampling frame (detections AND non-detections) from the baseline and the frozen blocks.
Records the baseline run it came from. Takes a few minutes (one detector run).
  python scripts/build_sampling_frame.py"""
import argparse, json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from forestwatch.pipeline import run_pipeline
from forestwatch.audit import new_run_id, write_run_manifest, sha256_file
from forestwatch.reference.context import load_context, load_frozen_manifest
from forestwatch.reference.frame import build_frame, stratum_table
from forestwatch.reference.sampling import allocation_for
from forestwatch.reference.schema import write_rows, FRAME_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--force", action="store_true")
args = ap.parse_args()
cfg, ref, meta, shape = load_context(ROOT)
frame_path = ROOT / "data" / "reference" / "sampling_frame.csv"
if frame_path.exists() and not args.force:
    sys.exit(f"{frame_path} exists. The frame defines inclusion probabilities, so it is not overwritten (use --force for a new version).")
manifest, manifest_sha = load_frozen_manifest(ROOT)
lc = np.load(ROOT / "data" / "landcover" / "landcover_grid.npy")
res = run_pipeline(cfg, ROOT, "baseline", seasonal=False, return_windows=True)
before, after = res["windows"]
drop = before["ndvi"] - after["ndvi"]
rows = build_frame(shape, ref["chip_px"], cfg["split"]["block_size_px"], manifest, res["mask"], drop, res["valid"], lc,
                   ref, ref["landcover_groups"])
cfg_path = ROOT / "configs" / "aravalli.yaml"
run_id = new_run_id(cfg_path)
write_run_manifest(ROOT, cfg_path, run_id, {"purpose": "phase2 sampling frame", "n_candidates": len(res["features"])})
write_rows(frame_path, rows, FRAME_COLUMNS, args.force)
info = {"baseline_run_id": run_id, "config_sha256": sha256_file(cfg_path), "reference_config_sha256": sha256_file(ROOT / "configs" / "reference.yaml"),
        "split_manifest_sha256": manifest_sha, "chip_px": ref["chip_px"], "n_chips": len(rows),
        "n_eligible": sum(r["eligible"] == "yes" for r in rows), "exclusions": dict(Counter(r["exclusion_reason"] or "none" for r in rows))}
frame_path.with_suffix(".meta.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
tab = stratum_table(rows)
print(f"Frame: {info['n_chips']} chips, {info['n_eligible']} eligible; exclusions {info['exclusions']}; baseline run {run_id}")
for split in ("train", "validation", "test"):
    print(f"\n{split}: eligible chips per stratum (baseline status | land-cover group)")
    for k, n in sorted(tab.get(split, {}).items()):
        print(f"  {k:36s} {n:5d}   planned draw {min(n, allocation_for(ref['allocation'][split], k))}")
    planned = sum(min(n, allocation_for(ref["allocation"][split], k)) for k, n in tab.get(split, {}).items())
    print(f"  -> {planned} chips to label for {split} (change 'allocation' in configs/reference.yaml before selecting)")
