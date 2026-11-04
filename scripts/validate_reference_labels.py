"""Check the labels against the protocol and the frozen blocks.  python scripts/validate_reference_labels.py --split validation"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forestwatch.reference.context import load_context, load_frozen_manifest
from forestwatch.reference.schema import read_rows, SPLITS
from forestwatch.reference.blocks import prepare_blocks, check_blocks
from forestwatch.reference.labels import validate_labels

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--split", required=True, choices=SPLITS)
args = ap.parse_args()
cfg, ref, meta, shape = load_context(ROOT)
manifest, _ = load_frozen_manifest(ROOT)
blocks = prepare_blocks(manifest, cfg["region"]["resolution_m"], shape)
rows = read_rows(ROOT / "data" / "reference" / f"labels_{args.split}.csv")
res = validate_labels(rows, blocks, shape, ref["chip_px"], cfg["split"]["block_size_px"], ref)
res["errors"] = check_blocks(blocks) + res["errors"]
out = ROOT / "reports" / "phase2"
out.mkdir(parents=True, exist_ok=True)
(out / f"label_quality_{args.split}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
print("counts:", res["counts"])
for w in res["warnings"][:25]:
    print("WARNING:", w)
for e in res["errors"][:50]:
    print("ERROR:  ", e)
print(f"{len(res['errors'])} error(s), {len(res['warnings'])} warning(s). Report: reports/phase2/label_quality_{args.split}.json")
sys.exit(1 if res["errors"] else 0)
